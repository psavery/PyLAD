from ctypes import CDLL

from pylad.generated.xisl_ctypes import add_xisl_ctypes
from pylad.utils.xisl_paths import path_to_xisl_library


def load_xisl() -> CDLL:
    # First, load the DLL
    path = path_to_xisl_library()
    lib = CDLL(str(path.resolve()))

    # Now load all other DLLs in that directory
    # This allows us to run the program in another directory, and
    # the xisl DLL will still find the other DLLs
    for file_path in path.parent.iterdir():
        if (
            file_path.is_file() and
            file_path.suffix == '.dll' and
            file_path != path
        ):
            CDLL(str(file_path.resolve()))

    # Add the ctypes wrappers
    # These add some safety features to the ctypes accesses, including checking
    # the number of arguments, checking the types, and allocating the correct
    # space for the return type.
    add_xisl_ctypes(lib)

    return lib
