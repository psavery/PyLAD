import logging
import sys
import time

from pylad.config import create_instrument_from_json_file

logger = logging.getLogger(__name__)


def main():
    if len(sys.argv) < 2:
        sys.exit('<pylad> <path_to_json_config>')

    json_path = sys.argv[1]
    instr = create_instrument_from_json_file(json_path)

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
