import os
from pathlib import Path
from sys import platform


# The name of the environment variable we are expecting.
# This should point to the root level of the compiled XISL path
# On Linux, it should have 'include/Acq.h' and 'lib/libxisl.so' inside.
# On Windows, it should have 'xisl.dll' and 'Acq.h' directly inside.
xisl_path_env_name = 'PYLAD_XISL_PATH'

if platform == 'linux':
    paths = {
        'header': 'include/Acq.h',
        'library': 'lib/libxisl.so',
    }
else:
    # Assume windows
    paths = {
        'header': 'Acq.h',
        'library': 'xisl.dll',
    }

def path_to_xisl_header() -> Path:
    return xisl_path() / paths['header']


def path_to_xisl_library() -> Path:
    return xisl_path() / paths['library']


def xisl_path() -> Path:
    if xisl_path_env_name not in os.environ:
        raise XISLPathNotFound(
            f'Environment variable "{xisl_path_env_name}" must point to the '
            'root of the XISL libraries'
        )

    return Path(os.environ[xisl_path_env_name])


class XISLPathNotFound(Exception):
    pass
