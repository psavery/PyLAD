import logging
from pathlib import Path

import psutil

from pylad import api, setup_logger
from pylad import constants as ct
from pylad.instrument.detector import Detector

logger = logging.getLogger(__name__)


class Instrument:
    def __init__(self, run_name: str = 'Run1',
                 save_files_path: Path | str | None = None,
                 detector_prefix: str = 'Varex'):
        self.detectors: dict[str, Detector] = {}

        self.set_run_name(run_name)
        self._experiment_name = 'experiment_name'

        if save_files_path is None:
            save_files_path = Path('.') / run_name
        else:
            save_files_path = Path(save_files_path)

        # Create the directory if it doesn't exist
        save_files_path.mkdir(parents=True, exist_ok=True)

        self.set_save_files_path(save_files_path)
        self.detector_prefix = detector_prefix

        # Setup logging after setting the save files path
        self.setup_logging()

        # Initialize the detectors
        self.initialize_detectors()

        # For "external trigger" mode, set the number of frames we will
        # skip, as well as the number of background frames before the
        # frame that contains the data.

        self.set_skip_frames(1)
        self.set_num_background_frames(10)
        self.set_num_data_frames(1)
        self.set_num_post_shot_background_frames(0)

        self.set_perform_background_median(True)

    def setup_logging(self):
        # These are the same settings Clemens used
        api.enable_logging()
        path = self.save_files_path / 'xisl_log.txt'

        # FIXME: if this is already open for reading from a previous
        # run, we get an error when we try to unlink it, so I guess
        # we'll just append to the end of it...
        # if path.exists():
        #     path.unlink()

        api.set_log_output(str(path), False)
        api.set_log_level(ct.LogLevels.TRACE)

        logging_path = self.save_files_path / 'pylad_log.txt'
        # FIXME: if this is already open for reading from a previous
        # run, we get an error when we try to unlink it, so I guess
        # we'll just append to the end of it...
        # if logging_path.exists():
        #     logging_path.unlink()

        setup_logger(logging.DEBUG, logging_path)

    def initialize_detectors(self):
        logger.info('Initializing detectors')

        # This helps us keep track of whether we have some kind of memory leak
        self.print_available_memory()

        self.detectors = {}
        num_detectors = api.initialize_sensors()

        logger.info(f'Found {num_detectors} detectors')

        pos = 0
        for i in range(num_detectors):
            pos, handle = api.get_next_sensor(pos)
            # pos was `None` for the single detector setup
            logger.info(f'Setting up detector: {pos}')
            self.detectors[pos] = Detector(
                handle,
                name=f'{self.detector_prefix}{i + 1}',
                run_name=self.run_name,
                save_files_path=self.save_files_path,
            )

        logger.info(f'Successfully initialized {num_detectors} detectors')

    def print_available_memory(self):
        mem = psutil.virtual_memory()
        available_gb = round(mem.available / 2**30, 2)
        logger.info(f'Available RAM: {available_gb} GB')

    @property
    def acquisition_finished(self) -> bool:
        return all(x.acquisition_finished for x in self.detectors.values())

    @property
    def all_expected_frames_received(self) -> bool:
        return all(
            x.all_expected_frames_received for x in self.detectors.values()
        )

    def set_exposure_time(self, milliseconds: int):
        # Exposure time is only used for internal timer.
        # 100 milliseconds means 10 Hz, for example.
        for det in self.detectors.values():
            det.exposure_time = milliseconds

    def set_gain(self, gain: int):
        # Gain goes from 1 to 7, with the background decreasing for higher gain
        for det in self.detectors.values():
            det.gain = gain

    def set_binning(self, binning: int):
        # Set the binning. Default is 1 (no binning). 2 means 2x2 binning,
        # and 3 means 3x3 binning.
        for det in self.detectors.values():
            det.binning = binning

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

    def set_num_data_frames(self, num_frames: int):
        for det in self.detectors.values():
            det.num_data_frames = num_frames

    def set_num_post_shot_background_frames(self, num_frames: int):
        for det in self.detectors.values():
            det.num_post_shot_background_frames = num_frames

    def set_statistics_only_mode(self, b: bool):
        for det in self.detectors.values():
            det.statistics_only_mode = b

    def set_statistics_only_mode_num_frames(self, num_frames: int):
        for det in self.detectors.values():
            det.statistics_only_mode_num_frames = num_frames

    def set_perform_background_median(self, b: bool):
        for det in self.detectors.values():
            det.perform_background_median = b

    @property
    def run_name(self) -> str:
        return self._run_name

    def set_run_name(self, name: str):
        self._run_name = name
        for det in self.detectors.values():
            det.run_name = name

    @property
    def experiment_name(self) -> str:
        return self._experiment_name

    def set_experiment_name(self, name: str):
        self._experiment_name = name
        for det in self.detectors.values():
            det.experiment_name = name

    @property
    def save_files_path(self) -> Path:
        return self._save_files_path

    def set_save_files_path(self, path: Path):
        self._save_files_path = Path(path)
        for det in self.detectors.values():
            det.save_files_path = self._save_files_path

    @property
    def data_paths_to_visualize(self) -> dict[str, Path | None]:
        return {
            k: det.data_path_to_visualize
            for k, det in self.detectors.items()
        }

    @property
    def saved_median_dark_subtraction_paths(self) -> dict[str, Path | None]:
        return {
            k: det.saved_median_dark_subtraction_path
            for k, det in self.detectors.items()
        }

    def shutdown_if_time_limit_exceeded(self):
        for det in self.detectors.values():
            det.shutdown_if_time_limit_exceeded()

    def resource_cleanup(self):
        # Try to clean up some resources...
        api.close_all()
