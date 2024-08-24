# This module creates a Pythonic interface for all XISL functions

import ctypes

from pylad.generated.xisl_ctypes import (
    CHwHeaderInfo,
    CHwHeaderInfoEx,
)
from pylad.utils.load_xisl import load_xisl
from pylad.utils.xisl_errors import error_message

# This is the global XISL library that we will access
_lib = load_xisl()


class CheckReturnWrapper:
    def __getattribute__(self, name):
        f = getattr(_lib, name)

        def wrapped(*args, **kwargs):
            ret = f(*args, **kwargs)
            check_return(ret)
            return ret

        return wrapped


lib = CheckReturnWrapper()


def init():
    XIF_ALL = 0xFFFFFFFF
    lib.Acquisition_Global_Init(XIF_ALL)


def cleanup():
    lib.Acquisition_Global_Cleanup()


def enable_logging(b: bool = True):
    lib.Acquisition_EnableLogging(b)


def get_version() -> tuple[int, int, int, int]:
    major = ctypes.c_int()
    minor = ctypes.c_int()
    release = ctypes.c_int()
    build = ctypes.c_int()

    lib.Acquisition_GetVersion(
        ctypes.pointer(major),
        ctypes.pointer(minor),
        ctypes.pointer(release),
        ctypes.pointer(build),
    )
    return (major.value, minor.value, release.value, build.value)


def initialize_sensors() -> int:
    # Initialize sensors and return the number of them.
    # After this has been called, get_next_sensor() may be called.
    num_sensors = ctypes.c_uint()
    enable_irq = True  # This argument is actually not used anymore
    always_open = False
    lib.Acquisition_EnumSensors(
        ctypes.pointer(num_sensors),
        enable_irq,
        always_open,
    )
    return num_sensors.value


def get_next_sensor() -> tuple[int, int]:
    desc_pos = ctypes.c_void_p()
    handle = ctypes.c_void_p()
    lib.Acquisition_GetNextSensor(
        ctypes.pointer(desc_pos), ctypes.pointer(handle)
    )
    return (desc_pos.value, handle.value)


def get_detector_header_info(
    detector_handle: int,
) -> tuple[CHwHeaderInfo, CHwHeaderInfoEx]:
    info = CHwHeaderInfo()
    info_ex = CHwHeaderInfoEx()
    lib.Acquisition_GetHwHeaderInfoEx(
        detector_handle, ctypes.pointer(info), ctypes.pointer(info_ex)
    )

    return (info, info_ex)


def get_detector_comm_channel(detector_handle: int) -> tuple[int, int]:
    channel_type = ctypes.c_uint()
    channel = ctypes.c_int()
    lib.Acquisition_GetCommChannel(
        detector_handle, ctypes.pointer(channel_type), ctypes.pointer(channel)
    )
    return channel_type, channel


def detector_abort(detector_handle: int):
    lib.Acquisition_Abort(detector_handle)


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
        *[ctypes.pointer(x) for x in args.values()],
    )

    return {k: v.value for k, v in args.items()}


def check_return(ret: int):
    if ret != 0:
        raise XISLErrorReturn(error_message(ret))


class XISLErrorReturn(Exception):
    pass
