import logging

from pylad import api
from pylad import constants as ct
from pylad.instrument.frame_buffer import FrameBufferAllocator

logger = logging.getLogger(__name__)


class Detector:
    def __init__(self, detector_handle: int):
        self.handle = detector_handle

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
        self.enable_internal_trigger()
        self.exposure_time = 100
        self.gain = 4

        self.start_acquisition()

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
        self._set_frame_sync_mode(ct.Triggers.HIS_SYNCMODE_EXTERNAL_TRIGGER)

    def enable_internal_trigger(self):
        self._set_frame_sync_mode(ct.Triggers.HIS_SYNCMODE_INTERNAL_TIMER)

    def set_frame_sync_mode(self, mode: ct.Triggers):
        api.set_frame_sync_mode(self.handle, mode)
        self._frame_sync_mode = mode

    def get_trigger_mode(self) -> ct.Triggers:
        return self._frame_sync_mode

    def start_acquisition(self):
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
        logger.info(f'Frame callback with buffer index: {buffer_idx}')
        info, info_ex = api.get_latest_frame_header(self.handle)

        act_frame, sec_frame = api.get_act_frame(self.handle)

        # FIXME: Let's do whatever we need to do with the image
        img = self.frame_buffer[buffer_idx]  # noqa

        self.increment_buffer_index()
        api.set_ready(self.handle, True)
