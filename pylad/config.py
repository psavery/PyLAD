import json
from pathlib import Path

from pylad.instrument import Instrument


def set_instrument_settings_from_config(instr: Instrument, config: dict):
    settings_mapping = {
        'run_name': 'set_run_name',
        'num_skip_frames': 'set_skip_frames',
        'num_background_frames': 'set_num_background_frames',
        'num_data_frames': 'set_num_data_frames',
        'num_post_background_frames': 'set_num_post_shot_background_frames',  # noqa
        'save_files_path': 'set_save_files_path',
    }

    # Set the settings
    for k, func_name in settings_mapping.items():
        if k in config:
            getattr(instr, func_name)(config[k])


def create_instrument_from_config(config: dict) -> Instrument:
    # Initialize the instrument
    # Set the save files path immediately so the loggers get set up correctly
    save_files_path = config.get('save_files_path')
    instr = Instrument(save_files_path=save_files_path)

    set_instrument_settings_from_config(instr, config)

    return instr


def create_instrument_from_json_file(json_path: Path) -> Instrument:
    with open(json_path, 'r') as rf:
        config = json.load(rf)

    # Set up the save files path initially so that log files can
    # be written there.
    if config.get('save_files_path') is None:
        # Set the path to the json file as the save files path
        config['save_files_path'] = str(Path(json_path).parent)

    return create_instrument_from_config(config)
