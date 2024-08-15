from ctypes import (
    c_char,
    c_double,
    c_int,
    c_long,
    c_size_t,
    c_ubyte,
    c_uint,
    c_ulong,
    c_ushort,
    POINTER,
    String,
)


def wrap_xisl_library(lib):
    # This adds ctypes wrappers (argtypes and restype) for any functions we
    # plan to use. These wrappers are safeguards that help prevent us from
    # causing a segmentation fault when calling the C functions.

    # To determine what a wrapper should look like, try using the `ctypesgen`
    # library (see `pyxisl/scripts/generate_ctypes_wrappers`) and use whatever
    # it generates as a start.
    BOOL = c_int
    INT = c_int
    WORD = c_ushort
    DWORD = c_uint
    CHAR = c_char
    BYTE = c_ubyte
    HANDLE = POINTER(None)
    HWND = HANDLE
    UINT = c_uint
    ACQDESCPOS = POINTER(None)
    HACQDESC = HANDLE
    HIS_RETURN = UINT



    lib.Acquisition_Global_Init.argtypes = [INT]
    lib.Acquisition_Global_Init.restype = UINT


