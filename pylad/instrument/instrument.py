import logging

from pylad import api
from pylad.instrument.detector import Detector

logger = logging.getLogger(__name__)


class Instrument:
    def __init__(self):
        api.init()

        # Initialize the detectors
        logger.info('Initializing detectors')
        self.detectors = {}
        num_detectors = api.initialize_sensors()
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
