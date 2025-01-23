import json
import logging
from pathlib import Path
import sys
import time

from pylad.instrument import Instrument

logger = logging.getLogger(__name__)


def main():
    if len(sys.argv) < 2:
        sys.exit('<pylad> <path_to_json_config>')

    json_path = sys.argv[1]
    with open(json_path, 'r') as rf:
        config = json.load(rf)

    settings_mapping = {
        'run_name': 'set_run_name',
        'num_skip_frames': 'set_skip_frames',
        'num_background_frames': 'set_num_background_frames',
        'num_data_frames': 'set_num_data_frames',
        'num_post_shot_background_frames': 'set_num_post_shot_background_frames',  # noqa
        'save_files_path': 'set_save_files_path',
    }

    save_files_path = config.get('save_files_path', None)
    if save_files_path is None:
        # Set the path to the json file as the save files path
        save_files_path = Path(json_path).parent

    # Initialize the instrument
    # Set the save files path immediately so the loggers get set up correctly
    instr = Instrument(save_files_path=save_files_path)

    # Set the settings
    for k, func_name in settings_mapping.items():
        if k in config:
            getattr(instr, func_name)(config[k])

    # Start the acquisition right away
    instr.start_acquisition()

    # Timeout time. If there are 20 seconds since the last frame, the detectors
    # go into idle mode. We'll just shut them down before that.
    while not instr.acquisition_finished:
        time.sleep(1)
        instr.shutdown_if_time_limit_exceeded()

    if instr.all_expected_frames_received:
        logger.info('Success! All frames received!')
    else:
        logger.info('Not every frame was received...')
