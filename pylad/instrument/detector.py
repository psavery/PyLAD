import logging
from pathlib import Path

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

        # These settings are used in external trigger mode
        # "skip_frames" is the number of frames to skip (usually 1)
        # "num_background_frames" is how many frames will be background (after
        # the "skip_frames" frames have been skipped). It is assumed that the
        # next frame after the last background frame will contain data.
        # "background_frames" is the list of background frames we have acquired
        self.skip_frames = 1
        self.num_background_frames = 0
        self.background_frames: list[np.ndarray] = []

        self.num_data_frames = 1
        self.data_frames: list[np.ndarray] = []
        self._num_frames_acquired = 0

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
        api.set_exposure_time(self.handle, self._exposure_time)

    def set_frame_sync_mode(self, mode: ct.Triggers):
        api.set_frame_sync_mode(self.handle, mode)
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
        self.background_frames.clear()
        self.data_frames.clear()

        self.start_continuous_acquisition()

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

    def increment_buffer_index(self):
        self._current_buffer_idx += 1
        if self._current_buffer_idx == self.num_frames_in_buffer:
            self._current_buffer_idx = 0

    def _frame_callback(self):
        buffer_idx = self._current_buffer_idx
        logger.info(
            f'\n{self.name}: Frame callback with buffer index: {buffer_idx}'
        )
        # info, info_ex = api.get_latest_frame_header(self.handle)

        # act_frame, sec_frame = api.get_act_frame(self.handle)

        # FIXME: Let's do whatever we need to do with the image
        img = self.frame_buffer[buffer_idx]  # noqa

        self._handle_frame(img)

        self._num_frames_acquired += 1
        self.increment_buffer_index()
        api.set_ready(self.handle, True)

    def _handle_frame(self, img: np.ndarray):
        frame_idx = self._num_frames_acquired

        logger.info(
            f'{self.name}: Frame info:\n'
            f'  max    {np.max(img)}\n'
            f'  mean   {np.mean(img)}\n'
            f'  median {np.median(img)}\n'
            f'  stdev  {np.std(img)}\n'
        )
        if self.is_internal_trigger:
            # Just write out the frames to disk as they come in...
            # Always use a unique name
            counter = 1
            path = self.data_frame_save_path(str(counter))
            while path.exists():
                counter += 1
                path = self.frame_save_path(str(counter))
            self.save_frame(img, str(counter))
            return
        elif not self.is_external_trigger:
            raise NotImplementedError(
                f'Unexpected trigger mode: {self.get_trigger_mode()}'
            )

        # This is external trigger mode. Proceed.
        if frame_idx < self.skip_frames:
            logger.info(f'{self.name}: Encountered skip frame. Skipping...')
            return

        if frame_idx - self.skip_frames < self.num_background_frames:
            logger.info(
                f'{self.name}: Encountered background frame. Storing...'
            )
            self.background_frames.append(img)
            return

        if (
            frame_idx - self.skip_frames - self.num_background_frames <
            self.num_data_frames
        ):
            logger.info(f'{self.name}: Encountered data frame. Storing...')
            self.data_frames.append(img)

            if (
                frame_idx - self.skip_frames - self.num_background_frames ==
                self.num_data_frames - 1
            ):
                logger.info(
                    f'{self.name}: Received final data frame. '
                    'Writing and exiting...'
                )
                self.save_background()
                self.save_data_frames()
                self.stop_acquisition()

                # Free up some memory
                self.background_frames.clear()
                self.data_frames.clear()
                return

        # Making it to this point is unexpected behavior. We must
        # have collected more frames than the number of data frames.
        logger.critical(
            f'{self.name}: Received unexpected frame: {frame_idx}. Dropping.'
        )

    @property
    def file_prefix(self):
        return f'{self.run_name}_{self.name}'

    def frame_save_path(self, suffix: str = '') -> Path:
        filename = f'{self.file_prefix}_frame{suffix}.tiff'
        return Path(self.save_files_path).resolve() / filename

    def save_frame(self, img: np.ndarray, suffix: str = ''):
        save_path = self.frame_save_path(suffix)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(img).save(save_path, 'TIFF')
        logger.info(f'{self.name}: Saved data to: {save_path}')

    def save_background(self):
        background = np.median(self.background_frames, axis=0)

        num_frames = len(self.background_frames)
        prefix = self.file_prefix
        filename = f'{prefix}_background_median_of_{num_frames}_frames.tiff'
        save_path = Path(self.save_files_path).resolve() / filename
        save_path.parent.mkdir(parents=True, exist_ok=True)

        Image.fromarray(background).save(save_path, 'TIFF')
        logger.info(f'{self.name}: Saved background to: {save_path}')

    def save_data_frames(self):
        save_dir = Path(self.save_files_path).resolve()
        save_dir.mkdir(parents=True, exist_ok=True)

        prefix = self.file_prefix

        for i in range(len(self.data_frames)):
            img = self.data_frames[i]
            filename = f'{prefix}_data{i + 1}.tiff'
            save_path = save_dir / filename
            Image.fromarray(img).save(save_path, 'TIFF')
            logger.info(f'{self.name}: Saved data to: {save_path}')
