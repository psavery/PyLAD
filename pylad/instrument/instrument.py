import logging

from pylad import api
from pylad import constants as ct
from pylad.instrument.detector import Detector

logger = logging.getLogger(__name__)


class Instrument:
    def __init__(self):
        api.init()

        self.setup_logging()

        # Initialize the detectors
        self.initialize_detectors()

    def setup_logging(self):
        # These are the same settings Clemens used
        api.enable_logging()
        api.set_log_output('log.txt', False)
        api.set_log_level(ct.LogLevels.TRACE)

    def initialize_detectors(self):
        logger.info('Initializing detectors')

        self.detectors = {}
        num_detectors = api.initialize_sensors()

        logger.info(f'Found {num_detectors} detectors')

        for i in range(num_detectors):
            pos, handle = api.get_next_sensor()
            logger.info(f'Setting up detector: {pos}')
            self.detectors[pos] = Detector(handle)

        logger.info(f'Successfully initialized {num_detectors} detectors')

    def set_exposure_time(self, milliseconds: int):
        for det in self.detectors.values():
            det.set_exposure_time(milliseconds)

    def set_gain(self, gain: int):
        for det in self.detectors.values():
            det.set_gain(gain)

    def enable_internal_trigger(self):
        for det in self.detectors.values():
            det.enable_internal_trigger()

    def enable_external_trigger(self):
        for det in self.detectors.values():
            det.enable_external_trigger()

    def start_acquisition(self):
        for det in self.detectors.values():
            det.start_acquisition()

    def stop_acquisition(self):
        for det in self.detectors.values():
            det.stop_acquisition()
