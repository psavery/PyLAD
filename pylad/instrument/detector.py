import logging
from pathlib import Path
import time

import numpy as np
from PIL import Image

from pylad import api
from pylad import constants as ct
from pylad.instrument.frame_buffer import FrameBufferAllocator

logger = logging.getLogger(__name__)


class Detector:
    def __init__(self, detector_handle: int, name: str, run_name: str = '',
                 save_files_path: Path | None = None):
        self.handle = detector_handle
        self.name = name
        self.run_name = run_name

        if save_files_path is None:
            save_files_path = Path('.').resolve()

        # The path to save files
        self.save_files_path = save_files_path

        # We are following along the same kinds of calls that happened
        # in Clemens' code.
        info, info_ex = api.get_detector_header_info(self.handle)
        self._header_info = info
        self._header_info_ex = info_ex

        channel_type, channel = api.get_detector_comm_channel(self.handle)
        self._channel_type = channel_type
        self._channel = channel

        # Ensure any previous acquisitions are aborted
        api.acquisition_abort(self.handle)
        # Not sure what a camera mode of 0 is, but that's what Clemens did.
        api.set_camera_mode(self.handle, 0)

        self._config = api.get_detector_configuration(self.handle)

        # These are essential, so grab them and make sure they were
        # in the config.
        self.rows = self._config['rows']
        self.columns = self._config['columns']

        # This was fixed to 50 in Clemens' code
        self.num_frames_in_buffer = 50
        self._current_buffer_idx = 0

        allocator = FrameBufferAllocator(
            self.rows,
            self.columns,
            self.num_frames_in_buffer,
        )
        # This is a special numpy array that points to the
        # memory-aligned frame buffer.
        self.frame_buffer = allocator.allocate()

        # Define destination buffers
        api.define_destination_buffers(
            self.handle,
            self.frame_buffer_pointer,
            self.num_frames_in_buffer,
            self.rows,
            self.columns,
        )

        # Reset frame count
        api.reset_frame_count(self.handle)

        # Set the frame callback
        api.set_callbacks_and_messages(
            self.handle,
            0,
            0,
            0,
            self._frame_callback,
            None,
        )

        # Set some default values for exposure time, gain, etc.
        # These don't all have getters in the API. Several of them
        # only have setters, so we must cache the setting internally.

        # Exposure time is only used for internal trigger mode
        self._exposure_time = 100
        self.gain = 4

        # We default to external trigger mode, since that is what will
        # be most commonly used
        self.enable_external_trigger()

        # This just collects statistics to save
        self.statistics_only_mode = False
        self.statistics_only_mode_num_frames = 1000
        self.frame_statistics: list[dict[str, np.ndarray]] = []

        # These settings are used in external trigger mode
        # "skip_frames" is the number of frames to skip (usually 1)
        # "num_background_frames" is how many frames will be background (after
        # the "skip_frames" frames have been skipped).
        # "num_data_frames" is how many data frames will be taken (after the
        # background frames)
        # "num_post_shot_background_frames" is how many background frames will
        # be taken (after the data frames)
        self.skip_frames = 1
        self.num_background_frames = 0
        self.num_data_frames = 1
        self.num_post_shot_background_frames = 0

        # "background_frames" is the list of background frames we have acquired
        # It is only used if `self.perform_background_median` is `True`
        self.background_frames: list[np.ndarray] = []
        self.perform_background_median = True
        self._last_saved_data_frame_path: Path | None = None
        self._saved_median_dark_subtraction_path: Path | None = None

        self.max_seconds_between_frames = 15

        self._num_frames_acquired = 0
        self.all_expected_frames_received = False
        self.acquisition_finished = False

        self._last_frame_callback_time = None
        self._acquisition_start_time = None

    def __del__(self):
        # When this object is deleted, ensure that callbacks are deregistered
        api.deregister_callbacks(self.handle)

    @property
    def frame_buffer_pointer(self) -> int:
        return self.frame_buffer.ctypes.data

    @property
    def exposure_time(self):
        return self._exposure_time

    @exposure_time.setter
    def exposure_time(self, milliseconds: int):
        if milliseconds == getattr(self, '_exposure_time', None):
            # Don't set it if not necessary
            return

        api.set_exposure_time(self.handle, milliseconds)
        # The API doesn't have a getter, so we must store internally
        self._exposure_time = milliseconds

    @property
    def gain(self):
        return self._gain

    @gain.setter
    def gain(self, v: int):
        if v == getattr(self, '_gain', None):
            # Don't set it if not necessary
            return

        api.set_camera_gain(self.handle, v)
        # The API doesn't have a getter, so we must store internally
        self._gain = v

    def enable_external_trigger(self):
        self.set_frame_sync_mode(ct.Triggers.HIS_SYNCMODE_EXTERNAL_TRIGGER)

    def enable_internal_trigger(self):
        self.set_frame_sync_mode(ct.Triggers.HIS_SYNCMODE_INTERNAL_TIMER)

    def activate_frame_sync_mode(self):
        api.set_frame_sync_mode(self.handle, self._frame_sync_mode)
        if self.is_internal_trigger:
            api.set_exposure_time(self.handle, self._exposure_time)

    def set_frame_sync_mode(self, mode: ct.Triggers):
        self._frame_sync_mode = mode

    def get_trigger_mode(self) -> ct.Triggers:
        return self._frame_sync_mode

    @property
    def is_external_trigger(self):
        mode = ct.Triggers.HIS_SYNCMODE_EXTERNAL_TRIGGER
        return self.get_trigger_mode() == mode

    @property
    def is_internal_trigger(self):
        mode = ct.Triggers.HIS_SYNCMODE_INTERNAL_TIMER
        return self.get_trigger_mode() == mode

    def start_acquisition(self):
        self._num_frames_acquired = 0
        self._last_frame_callback_time = None

        self.background_frames.clear()
        self.frame_statistics.clear()

        # Only activate the frame sync mode immediately before acquisition,
        # because otherwise the detector may enter into idle mode.
        self.activate_frame_sync_mode()

        self.start_continuous_acquisition()
        self._acquisition_start_time = time.time()

    def start_continuous_acquisition(self):
        # Begin a continuous acquisition stream, where the frames in
        # the buffer are used as a ring buffer.
        api.acquire_images(
            self.handle,
            self.num_frames_in_buffer,
            0,
            ct.SequenceAcquisitionOptions.HIS_SEQ_CONTINUOUS,
        )

    def stop_acquisition(self):
        api.acquisition_abort(self.handle)
        self.acquisition_finished = True

    def increment_buffer_index(self):
        self._current_buffer_idx += 1
        if self._current_buffer_idx == self.num_frames_in_buffer:
            self._current_buffer_idx = 0

    def _frame_callback(self):
        # First record the time taken to receive this callback
        prev = self._last_frame_callback_time
        self._last_frame_callback_time = time.time()
        time_taken = self.time_since_last_frame_or_acquisition_start

        if prev is not None:
            logger.info(f'{self.name}: Time since last frame: {time_taken}')
        else:
            logger.info(
                f'{self.name}: Frame received after start acquisition: '
                f'{time_taken}'
            )

        buffer_idx = self._current_buffer_idx
        logger.info(
            f'\n{self.name}: Frame callback with buffer index: {buffer_idx}'
        )
        # info, info_ex = api.get_latest_frame_header(self.handle)

        # act_frame, sec_frame = api.get_act_frame(self.handle)

        img = self.frame_buffer[buffer_idx]  # noqa

        self._handle_frame(img)

        self._num_frames_acquired += 1
        self.increment_buffer_index()

        api.set_ready(self.handle, True)

        frame_handling_time = time.time() - self._last_frame_callback_time
        logger.info(f'{self.name}: Frame handling time: {frame_handling_time}')
        if not self.acquisition_finished and frame_handling_time > 0.075:
            logger.critical(
                f'{self.name}: WARNING, frame handling time '
                f'({frame_handling_time}) exceeded 75 milliseconds. '
                'A trigger could have been missed!'
            )

    def _handle_frame(self, img: np.ndarray):
        frame_idx = self._num_frames_acquired

        stats = {
            'collection_time': time.time(),
            'max': img.max(),
            'min': img.min(),
            'mean': img.mean(),
        }
        if self.statistics_only_mode:
            # Only record median and stdev in statistics-only mode,
            # since they taken time to record.
            stats = {
                **stats,
                'median': np.median(img),
                'stdev': np.std(img),
            }

        msg = (
            f'{self.name}: Frame info:\n  ' +
            '  \n'.join([
                f'{k:<6s} {stats[k]}' for k in stats
            ])
        )
        logger.info(msg)

        if self.statistics_only_mode:
            self.frame_statistics.append(stats)
            if (
                len(self.frame_statistics) ==
                self.statistics_only_mode_num_frames
            ):
                self.write_statistics()
                self.stop_acquisition()

            return

        if self.is_internal_trigger:
            # Just write out the frames to disk as they come in...
            # Always use a unique name
            counter = 1
            path = self.internal_trigger_save_frame_path(str(counter))
            while path.exists():
                counter += 1
                path = self.internal_trigger_save_frame_path(str(counter))
            self.save_internal_trigger_frame(img, str(counter))
            return
        elif not self.is_external_trigger:
            raise NotImplementedError(
                f'Unexpected trigger mode: {self.get_trigger_mode()}'
            )

        # This is external trigger mode. Proceed.
        if frame_idx < self.skip_frames:
            logger.info(f'{self.name}: Encountered skip frame. Skipping...')
            if (
                frame_idx == self.skip_frames - 1 and
                self.num_background_frames == 0 and
                self.num_data_frames == 0
            ):
                self.on_acquisition_complete()
            return

        background_frame_idx = frame_idx - self.skip_frames
        if background_frame_idx < self.num_background_frames:
            logger.info(
                f'{self.name}: Encountered background frame. Storing...'
            )
            self.save_background_frame(img, background_frame_idx + 1)
            if self.perform_background_median:
                self.background_frames.append(img)

            if (
                background_frame_idx == self.num_background_frames - 1 and
                self.num_data_frames == 0
            ):
                self.on_acquisition_complete()
            return

        data_frame_idx = (
            frame_idx - self.skip_frames - self.num_background_frames
        )
        if data_frame_idx < self.num_data_frames:
            logger.info(f'{self.name}: Encountered data frame. Storing...')
            self.save_data_frame(img, data_frame_idx + 1)
            if (
                data_frame_idx == self.num_data_frames - 1 and
                self.num_post_shot_background_frames == 0
            ):
                self.on_acquisition_complete()
            return

        post_shot_background_idx = (
            frame_idx - self.skip_frames - self.num_background_frames -
            self.num_data_frames
        )
        if post_shot_background_idx < self.num_post_shot_background_frames:
            logger.info(
                f'{self.name}: Encountered post shot background frame. '
                'Storing...'
            )
            self.save_post_shot_background_frame(
                img,
                post_shot_background_idx + 1,
            )
            if (
                post_shot_background_idx ==
                self.num_post_shot_background_frames - 1
            ):
                self.on_acquisition_complete()
            return

        # Making it to this point is unexpected behavior. We must
        # have collected more frames than the number of data frames.
        logger.critical(
            f'{self.name}: Received unexpected frame: {frame_idx}. Dropping.'
        )

    def on_acquisition_complete(self):
        logger.info(f'{self.name}: Received all frames. Finalizing...')

        if self.perform_background_median:
            self.save_background_median()

        self.stop_acquisition()

        # Free up some memory
        self.background_frames.clear()
        self.all_expected_frames_received = True

    @property
    def time_since_last_frame_or_acquisition_start(self) -> float:
        prev = self._last_frame_callback_time
        if prev is None:
            prev = self._acquisition_start_time

        return time.time() - prev

    def shutdown_if_time_limit_exceeded(self):
        if (
            self.time_since_last_frame_or_acquisition_start >
            self.max_seconds_between_frames
        ):
            logger.critical(f'{self.name}: Time limit exceeded. Shutting down')
            self.stop_acquisition()

    @property
    def file_prefix(self):
        return f'{self.run_name}_{self.name}'

    @property
    def last_saved_data_frame_path(self) -> Path | None:
        return self._last_saved_data_frame_path

    @property
    def saved_median_dark_subtraction_path(self) -> Path | None:
        return self._saved_median_dark_subtraction_path

    def internal_trigger_save_frame_path(self, suffix: str = '') -> Path:
        filename = f'{self.file_prefix}_internal_trigger_frame{suffix}.tiff'
        return Path(self.save_files_path).resolve() / filename

    def save_frame(self, img: np.ndarray, save_path: Path):
        save_path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(img).save(save_path, 'TIFF')
        logger.info(f'{self.name}: Saved frame to: {save_path}')

    def save_internal_trigger_frame(self, img: np.ndarray, suffix: str = ''):
        save_path = self.internal_trigger_save_frame_path(suffix)
        self.save_frame(img, save_path)

    def save_background_frame(self, img: np.ndarray, idx: int):
        filename = f'{self.file_prefix}_background_{idx}.tiff'
        save_path = Path(self.save_files_path).resolve() / filename
        self.save_frame(img, save_path)

    def save_background_median(self):
        if not self.background_frames:
            # Nothing to do...
            return

        logger.info(f'{self.name}: Performing median on background frames...')
        background = np.median(self.background_frames, axis=0)

        num_frames = len(self.background_frames)
        prefix = self.file_prefix
        filename = f'{prefix}_background_median_of_{num_frames}_frames.tiff'
        save_path = Path(self.save_files_path).resolve() / filename
        self.save_frame(background, save_path)
        self._saved_median_dark_subtraction_path = save_path

    def save_data_frame(self, img: np.ndarray, idx: int):
        filename = f'{self.file_prefix}_data_{idx}.tiff'
        save_path = Path(self.save_files_path).resolve() / filename
        self.save_frame(img, save_path)
        self._last_saved_data_frame_path = save_path

    def save_post_shot_background_frame(self, img: np.ndarray, idx: int):
        filename = f'{self.file_prefix}_post_shot_background_{idx}.tiff'
        save_path = Path(self.save_files_path).resolve() / filename
        self.save_frame(img, save_path)

    def write_statistics(self):
        if not self.frame_statistics:
            # Nothing to do
            return

        save_dir = Path(self.save_files_path).resolve()
        save_dir.mkdir(parents=True, exist_ok=True)

        prefix = self.file_prefix

        stat_keys = list(self.frame_statistics[0])
        for key in stat_keys:
            values = np.array([x[key] for x in self.frame_statistics])

            filename = f'{prefix}_{key}_stats.npy'
            save_path = save_dir / filename

            np.save(save_path, values)
