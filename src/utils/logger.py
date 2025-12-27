import logging
import sys


def setup_logger(name="iFakeGPS"):
    """Configure and return the application logger."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Console handler
    c_handler = logging.StreamHandler(sys.stdout)
    c_handler.setLevel(logging.INFO)
    c_format = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    c_handler.setFormatter(c_format)
    logger.addHandler(c_handler)

    # File handler (optional, but good practice)
    # f_handler = logging.FileHandler('ifakegps.log')
    # f_handler.setLevel(logging.DEBUG)
    # logger.addHandler(f_handler)

    return logger


# Global logger instance
logger = setup_logger()
