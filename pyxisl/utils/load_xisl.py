from ctypes import CDLL

from pyxisl.generated.xisl_ctypes import add_xisl_ctypes
from pyxisl.utils.xisl_paths import path_to_xisl_library


def load_xisl() -> CDLL:
    # First, load the DLL
    path = path_to_xisl_library()
    lib = CDLL(str(path.resolve()))

    # Add the ctypes wrappers
    # These add some safety features to the ctypes accesses, including checking
    # the number of arguments, checking the types, and allocating the correct
    # space for the return type.
    add_xisl_ctypes(lib)

    return lib
