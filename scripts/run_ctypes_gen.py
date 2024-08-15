from pathlib import Path
import subprocess

from pyxisl.utils import xisl_paths

header_path = xisl_paths.path_to_xisl_header()
library_path = xisl_paths.path_to_xisl_library()
output_file = 'xisl_ctypes.py'

cmd = [
    'ctypesgen',
    str(header_path),
    '-l',
    str(library_path),
    '-o',
    str(output_file),
    '--no-embed-preamble',
]

subprocess.run(cmd)

# Remove these files that we will not use
Path('ctypes_preamble.py').unlink()
Path('ctypes_loader.py').unlink()

print('Output written to:', output_file)
