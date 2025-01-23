import logging
import signal

from PIL import Image


def setup_logger(log_level=logging.INFO, file_path='logger_output.log'):
    # create logger
    logger = logging.getLogger('pylad')
    logger.setLevel(log_level)

    # create formatter
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    )

    # create console handler and set level
    ch = logging.StreamHandler()
    ch.setLevel(logger.level)

    # create file handler and set level
    fh = logging.FileHandler(file_path)
    fh.setLevel(logger.level)

    # add formatter to ch
    ch.setFormatter(formatter)
    fh.setFormatter(formatter)

    # add ch to logger
    logger.addHandler(ch)
    logger.addHandler(fh)


# Kill the program when ctrl-c is used
signal.signal(signal.SIGINT, signal.SIG_DFL)

# Pillow gets lazily initialized, and we want to make sure that it does
# not get initialized during time-critical moments. So go ahead and
# initialize it here.
Image.init()
