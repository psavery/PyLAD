import importlib.resources
import json


ERRORS_DICT = json.loads(
    importlib.resources.files(
        'pyxisl.resources'
    ).joinpath('xisl_errors.json').read_text()
)
# Keys should be interpreted as integers
ERRORS_DICT = {int(k): v for k, v in ERRORS_DICT.items()}


def error_string(i: int) -> str:
    return ERRORS_DICT[i]


def error_message(i: int) -> str:
    return f'Error {i}: {error_string(i)}'
