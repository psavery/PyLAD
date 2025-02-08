import logging
from pathlib import Path
import shutil
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
        self.experiment_name = 'experiment_name'

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
        self.gain = 1

        # Binning of 1 is default. 2 means 2x2, and 3 means 3x3
        self.binning = 1

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

        self.acquiring_frames = False
        self.data_paths: list[Path] = []
        self.background_subtracted_data_paths: list[Path] = []
        self.background_file_paths: list[Path] = []
        self.perform_background_median = True
        self.approximate_background_median_with_mean = True
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

        # if self.is_internal_trigger:
        #     api.set_exposure_time(self.handle, milliseconds)

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

    @property
    def binning(self):
        return self._binning

    @binning.setter
    def binning(self, v: int):
        if v == getattr(self, '_binning', None):
            # Don't set it if not necessary
            return

        api.set_binning_mode(self.handle, v)
        # Store internally
        self._binning = v

        # The frame buffer must be re-created
        self._create_frame_buffer()

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

    def _create_frame_buffer(self):
        self._config = api.get_detector_configuration(self.handle)

        # These are essential, so grab them and make sure they were
        # in the config.
        self.rows = self._config['rows']
        self.columns = self._config['columns']

        # This was fixed to 50 in Clemens' code
        # But we process the frames faster than they come in, so it
        # doesn't really matter that much...
        # In fact, Varex did not provide a way to free the memory on the C
        # side after allocating a buffer, so this is kind of a memory leak,
        # and we want the number of frames in the buffer to be as few as
        # possible so that when we reallocate several times, we don't lose
        # too much RAM.
        self.num_frames_in_buffer = 2
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

    def start_acquisition(self):
        self.acquiring_frames = True
        self._num_frames_acquired = 0
        self._last_frame_callback_time = None

        self.data_paths.clear()
        self.background_subtracted_data_paths.clear()
        self.background_file_paths.clear()
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
        self.acquiring_frames = False
        api.acquisition_abort(self.handle)

    def increment_buffer_index(self):
        self._current_buffer_idx += 1
        if self._current_buffer_idx == self.num_frames_in_buffer:
            self._current_buffer_idx = 0

    def _frame_callback(self):
        # First record the time taken to receive this callback
        prev = self._last_frame_callback_time
        time_taken = self.time_since_last_frame_or_acquisition_start
        self._last_frame_callback_time = time.time()

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

        # Transpose appears to be needed
        img = img.T

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

        # This is the event number used by SLAC
        event_number = frame_idx - self.skip_frames + 1

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
                self.acquisition_finished = True

            return

        if self.is_internal_trigger:
            # Just write out the frames to disk as they come in...
            # Always use a unique name
            self.save_internal_trigger_frame(img, event_number)
            # FIXME: temporary code to kill internal trigger after 4000 frames
            if event_number == 20:
                self.stop_acquisition()
                self.acquisition_finished = True
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
            self.save_background_frame(img, event_number)

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
            self.save_data_frame(img, event_number)
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
                event_number,
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
            logger.info(
                f'{self.name}: Performing median background subtraction...'
            )
            self.save_background_median()
            logger.info(f'{self.name}: Saving background-subtracted files...')

        self.save_background_subtracted_data_files()

        # Free up some memory
        self.background_file_paths.clear()
        self.all_expected_frames_received = True

        self.acquisition_finished = True

        # It takes like 11 seconds to stop the acquisition, so do it at the
        # end, so that the preview window from the pylad client can go ahead
        # and open up.
        self.stop_acquisition()

    @property
    def time_since_last_frame_or_acquisition_start(self) -> float:
        prev = self._last_frame_callback_time
        if prev is None:
            prev = self._acquisition_start_time

        return time.time() - prev

    def shutdown_if_time_limit_exceeded(self):
        if (
            self.acquiring_frames and
            self.time_since_last_frame_or_acquisition_start >
            self.max_seconds_between_frames
        ):
            logger.critical(f'{self.name}: Time limit exceeded. Shutting down')
            self.stop_acquisition()
            self.acquisition_finished = True

    @property
    def file_prefix(self):
        return f'Run_{self.run_name}'

    @property
    def data_path_to_visualize(self) -> Path | None:
        if self.background_subtracted_data_paths:
            return self.background_subtracted_data_paths[-1]

        if self.data_paths:
            return self.data_paths[-1]

        return None

    @property
    def saved_median_dark_subtraction_path(self) -> Path | None:
        return self._saved_median_dark_subtraction_path

    def save_frame(self, img: np.ndarray, save_path: Path):
        save_path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(img).save(save_path, 'TIFF')
        logger.info(f'{self.name}: Saved frame to: {save_path}')

    def internal_trigger_save_frame_path(self, suffix: str = '') -> Path:
        filename = f'{self.file_prefix}_{self.name}_internal_trigger_frame{suffix}.tiff'
        return Path(self.save_files_path).resolve() / filename

    def save_internal_trigger_frame(self, img: np.ndarray, suffix: str = ''):
        save_path = self.internal_trigger_save_frame_path(suffix)
        self.save_frame(img, save_path)

    def save_background_frame(self, img: np.ndarray, idx: int):
        filename = f'{self.file_prefix}_evt_{idx}_{self.name}_background.tiff'
        save_path = Path(self.save_files_path).resolve() / filename
        self.background_file_paths.append(save_path)
        self.save_frame(img, save_path)

    def save_background_median(self):
        if not self.background_file_paths:
            # Nothing to do...
            return

        background_frames = []
        for path in self.background_file_paths:
            background_frames.append(np.array(Image.open(path)))

        logger.info(f'{self.name}: Performing median on background frames...')
        if self.approximate_background_median_with_mean:
            logger.info(
                f'{self.name}: Approximating median by performing mean '
                '(which is faster and pretty close to the median). If you '
                'do not wish to do this, set '
                '"approximate_background_median_with_mean" to False.'
            )
            background = np.mean(background_frames, axis=0)
            label = 'mean'
        else:
            background = np.median(background_frames, axis=0)
            label = 'median'

        num_frames = len(background_frames)
        filename = f'{self.file_prefix}_background_{label}_of_{num_frames}_frames_{self.name}.tiff'
        save_path = Path(self.save_files_path).resolve() / filename
        self.save_frame(background, save_path)
        self._saved_median_dark_subtraction_path = save_path
        self.save_previous_median_dark()

    def save_previous_median_dark(self):
        path = self._saved_median_dark_subtraction_path
        if path is None:
            return

        write_path = self.previous_median_dark_path
        write_path.parent.mkdir(parents=True, exist_ok=True)

        shutil.copy(path, write_path)
        if self.name == 'Varex1':
            # Only save the dark number with the first detector
            self.save_previous_median_dark_run_number()

    @property
    def most_recent_backgrounds_dir(self) -> Path:
        experiment_name = self.experiment_name
        gain = self.gain
        return (
            Path.home() /
            f'.varex/most_recent_backgrounds/{experiment_name}/gain_{gain}'
        )

    @property
    def previous_median_dark_path(self) -> Path:
        return self.most_recent_backgrounds_dir / f'last_dark_{self.name}.tiff'

    def save_previous_median_dark_run_number(self):
        filepath = self.most_recent_backgrounds_dir / 'run_num.txt'
        with open(filepath, 'w') as wf:
            wf.write(self.file_prefix)

    @property
    def previous_median_dark_run_number(self) -> str | None:
        filepath = self.most_recent_backgrounds_dir / 'run_num.txt'
        if not filepath.exists():
            return

        with open(filepath, 'r') as rf:
            return rf.read()

    def save_background_subtracted_data_files(self):
        median_background_path = self.saved_median_dark_subtraction_path
        if median_background_path is None:
            median_background_path = self.previous_median_dark_path
            if median_background_path.exists():
                logger.info(
                    f'{self.name}: No median background calculated. '
                    'Re-using the last median background at: '
                    f'{median_background_path}, taken from run '
                    f'{self.previous_median_dark_run_number}'
                )
            else:
                logger.critical(
                    f'{self.name}: cannot save background subtracted files'
                )
                return

        logger.info(f'{self.name}: saving ds files...')
        background = np.array(Image.open(median_background_path), dtype=float)
        for path in self.data_paths:
            new_path = path.with_name(f'{path.stem}_ds{path.suffix}')
            data = np.array(Image.open(path), dtype=float)
            subtracted = data - background
            self.save_frame(subtracted, new_path)
            self.background_subtracted_data_paths.append(new_path)

    def save_data_frame(self, img: np.ndarray, idx: int):
        filename = f'{self.file_prefix}_evt_{idx}_{self.name}_data.tiff'
        save_path = Path(self.save_files_path).resolve() / filename
        self.save_frame(img, save_path)
        self.data_paths.append(save_path)

    def save_post_shot_background_frame(self, img: np.ndarray, idx: int):
        filename = f'{self.file_prefix}_evt_{idx}_{self.name}_post_shot_background.tiff'
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
