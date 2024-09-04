# This module creates a Pythonic interface for all XISL functions

import ctypes
import platform
from typing import Callable

from pylad import constants as ct
from pylad.generated.xisl_ctypes import (
    CHwHeaderInfo,
    CHwHeaderInfoEx,
)
from pylad.utils.load_xisl import load_xisl
from pylad.utils.xisl_errors import error_message

# This is the global XISL library that we will access
_lib = load_xisl()


def init():
    XIF_ALL = 0xFFFFFFFF
    lib.Acquisition_Global_Init(XIF_ALL)


def cleanup():
    lib.Acquisition_Global_Cleanup()


def enable_logging(b: bool = True):
    lib.Acquisition_EnableLogging(b)


def set_log_output(path: str, write_to_console: bool = True):
    lib.Acquisition_SetLogOutput(path, write_to_console)


def set_log_level(log_level: ct.LogLevels):
    lib.Acquisition_SetLogLevel(log_level.value)


def toggle_log_performance(b: bool):
    lib.Acquisition_TogglePerformanceLogging(b)


def get_version() -> tuple[int, int, int, int]:
    major = ctypes.c_int()
    minor = ctypes.c_int()
    release = ctypes.c_int()
    build = ctypes.c_int()

    lib.Acquisition_GetVersion(
        ctypes.byref(major),
        ctypes.byref(minor),
        ctypes.byref(release),
        ctypes.byref(build),
    )
    return (major.value, minor.value, release.value, build.value)


def initialize_sensors() -> int:
    # Initialize sensors and return the number of them.
    # After this has been called, get_next_sensor() may be called.
    num_sensors = ctypes.c_uint()
    enable_irq = True  # This argument is actually not used anymore
    always_open = False
    lib.Acquisition_EnumSensors(
        ctypes.byref(num_sensors),
        enable_irq,
        always_open,
    )
    return num_sensors.value


def get_next_sensor() -> tuple[int | None, int | None]:
    desc_pos = ctypes.c_void_p()
    handle = ctypes.c_void_p()
    lib.Acquisition_GetNextSensor(ctypes.byref(desc_pos), ctypes.byref(handle))
    return (desc_pos.value, handle.value)


def get_detector_header_info(
    detector_handle: int,
) -> tuple[CHwHeaderInfo, CHwHeaderInfoEx]:
    info = CHwHeaderInfo()
    info_ex = CHwHeaderInfoEx()
    lib.Acquisition_GetHwHeaderInfoEx(
        detector_handle, ctypes.byref(info), ctypes.byref(info_ex)
    )

    return (info, info_ex)


def get_detector_comm_channel(detector_handle: int) -> tuple[int, int]:
    channel_type = ctypes.c_uint()
    channel = ctypes.c_int()
    lib.Acquisition_GetCommChannel(
        detector_handle, ctypes.byref(channel_type), ctypes.byref(channel)
    )
    return channel_type.value, channel.value


def acquisition_abort(detector_handle: int):
    lib.Acquisition_Abort(detector_handle)


def set_exposure_time(detector_handle: int, milliseconds: int):
    # Convert to microseconds
    microseconds = ctypes.c_uint(milliseconds * 1000)
    lib.Acquisition_SetTimerSync(detector_handle, ctypes.byref(microseconds))


def set_camera_mode(detector_handle: int, dw_mode: int):
    lib.Acquisition_SetCameraMode(detector_handle, dw_mode)


def set_camera_gain(detector_handle: int, gain: int):
    lib.Acquisition_SetCameraGain(detector_handle, gain)


def get_detector_configuration(detector_handle: int) -> dict:
    c_uint = ctypes.c_uint
    c_int = ctypes.c_int

    # The order here must exactly match the order of arguments.
    args = {
        'frames': c_uint(),
        'rows': c_uint(),
        'columns': c_uint(),
        'data_type': c_uint(),
        'sort_flags': c_uint(),
        'irq_enabled': c_int(),
        'acq_type': c_uint(),
        'system_id': c_uint(),
        'sync_mode': c_uint(),
        'access': c_uint(),
    }

    lib.Acquisition_GetConfiguration(
        detector_handle,
        # We must pass pointers to all of these
        *[ctypes.byref(x) for x in args.values()],
    )

    return {k: v.value for k, v in args.items()}


def acquire_images(
    detector_handle: int,
    num_frames: int,
    skip_frames: int,
    option: ct.SequenceAcquisitionOptions,
    pw_offset_data: int = 0,
    pdw_gain_data: int = 0,
    pdw_pxl_corr_list: int = 0,
):
    lib.Acquisition_Acquire_Image(
        detector_handle,
        num_frames,
        skip_frames,
        option.value,
        pw_offset_data,
        pdw_gain_data,
        pdw_pxl_corr_list,
    )


def set_ready(detector_handle: int, redraw_ready: bool):
    lib.Acquisition_SetReady(detector_handle, redraw_ready)


def set_frame_sync_mode(detector_handle: int, mode: ct.Triggers):
    lib.Acquisition_SetFrameSyncMode(detector_handle, mode.value)


def define_destination_buffers(
    detector_handle: int,
    frame_buffer_pointer: int,
    num_frames_in_buffer: int,
    num_rows: int,
    num_columns: int,
):
    lib.Acquisition_DefineDestBuffers(
        detector_handle,
        frame_buffer_pointer,
        num_frames_in_buffer,
        num_rows,
        num_columns,
    )


def reset_frame_count(detector_handle: int):
    lib.Acquisition_ResetFrameCnt(detector_handle)


def set_callbacks_and_messages(
    detector_handle: int,
    h_wnd: int,
    dw_error_msg: int,
    dw_loosing_frames_msg: int,
    frame_callback: Callable[[], None] | None,
    end_acquisition_callback: Callable[[], None] | None,
):
    # First, make sure these callbacks are deregistered
    deregister_callbacks(detector_handle)

    # Register these with global handlers.
    # The global level functions will actually get called from C.
    if frame_callback is not None:
        C_FRAME_CALLBACKS[detector_handle] = frame_callback

    if end_acquisition_callback is not None:
        C_END_ACQUISITION_CALLBACKS[detector_handle] = end_acquisition_callback

    lib.Acquisition_SetCallbacksAndMessages(
        detector_handle,
        h_wnd,
        dw_error_msg,
        dw_loosing_frames_msg,
        c_frame_callback if frame_callback else 0,
        c_end_acquisition_callback if end_acquisition_callback else 0,
    )


C_FRAME_CALLBACKS = {}
C_END_ACQUISITION_CALLBACKS = {}


def deregister_callbacks(detector_handle: int):
    if detector_handle in C_FRAME_CALLBACKS:
        del C_FRAME_CALLBACKS[detector_handle]

    if detector_handle in C_END_ACQUISITION_CALLBACKS:
        del C_END_ACQUISITION_CALLBACKS[detector_handle]


if platform.system() == 'Windows':
    # On Windows only, stdcall is used for callbacks in XISL, so we must
    # use the WINFUNCTYPE callback decorator instead
    FUNC_TYPE = ctypes.WINFUNCTYPE
else:
    # Everything else uses cdecl
    FUNC_TYPE = ctypes.CFUNCTYPE


# These are the C callbacks for the XISL functions
@FUNC_TYPE(None, ctypes.c_void_p)
def c_frame_callback(detector_handle: int):
    if detector_handle not in C_FRAME_CALLBACKS:
        raise Exception(f'Unknown detector handle: {detector_handle}')

    C_FRAME_CALLBACKS[detector_handle]()


@FUNC_TYPE(None, ctypes.c_void_p)
def c_end_acquisition_callback(detector_handle: int):
    if detector_handle not in C_END_ACQUISITION_CALLBACKS:
        raise Exception(f'Unknown detector handle: {detector_handle}')

    C_END_ACQUISITION_CALLBACKS[detector_handle]()


class CheckReturnWrapper:
    def __getattribute__(self, name):
        f = getattr(_lib, name)

        def wrapped(*args, **kwargs):
            ret = f(*args, **kwargs)
            check_return(ret)
            return ret

        return wrapped


def check_return(ret: int):
    if ret != 0:
        raise XISLErrorReturn(error_message(ret))


class XISLErrorReturn(Exception):
    pass


# All XISL calls return a status code. We can wrap every call
# to verify that no error occurred, and raise an exception if
# one did occur.
lib = CheckReturnWrapper()
