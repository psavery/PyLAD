import logging
from pathlib import Path

from pylad import api
from pylad import constants as ct
from pylad.instrument.detector import Detector

logger = logging.getLogger(__name__)


class Instrument:
    def __init__(self, run_name: str = 'Run1',
                 save_files_path: Path | None = None):
        self.setup_logging()
        self.run_name = run_name

        if save_files_path is None:
            save_files_path = Path('.') / run_name

        self.save_files_path = save_files_path

        # Initialize the detectors
        self.initialize_detectors()

        # For "external trigger" mode, set the number of frames we will
        # skip, as well as the number of background frames before the
        # frame that contains the data.
        self.set_skip_frames(1)
        self.set_num_background_frames(10)

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
            # pos was `None` for the single detector setup
            logger.info(f'Setting up detector: {pos}')
            self.detectors[pos] = Detector(
                handle,
                name=pos,
                run_name=self.run_name,
                save_files_path=self.save_files_path,
            )

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

    def set_skip_frames(self, num_frames: int):
        for det in self.detectors.values():
            det.skip_frames = num_frames

    def set_num_background_frames(self, num_frames: int):
        for det in self.detectors.values():
            det.num_background_frames = num_frames

    @property
    def run_name(self) -> str:
        return self._run_name

    @run_name.setter
    def run_name(self, name: str):
        self._run_name = name
        for det in self.detectors.values():
            det.run_name = name

    @property
    def save_files_path(self) -> Path:
        return self._save_files_path

    @save_files_path.setter
    def save_files_path(self, path: Path):
        self._save_files_path = Path(path)
        for det in self.detectors.values():
            det.save_files_path = self._save_files_path
