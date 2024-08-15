# This module creates a Pythonic interface for all XISL functions

import ctypes

from pyxisl.utils.load_xisl import load_xisl
from pyxisl.utils.xisl_errors import error_message

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


def enable_logging(b : bool = True):
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


def get_next_sensor() -> int:
    desc_pos = ctypes.c_void_p()
    handle = ctypes.c_void_p()
    lib.Acquisition_GetNextSensor(ctypes.pointer(desc_pos), ctypes.pointer(handle))
    return handle.value


def set_camera_mode(detector_handle: int, dw_mode: int):
    lib.Acquisition_SetCameraMode(detector_handle, dw_mode)


def check_return(ret: int):
    if ret != 0:
        raise XISLErrorReturn(error_message(ret))


class XISLErrorReturn(Exception):
    pass
