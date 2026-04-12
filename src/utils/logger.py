import logging
import os
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path

APP_NAME = "iFakeGPS"
LOG_FILENAME = "ifakegps.log"


def get_app_data_dir() -> Path:
    """Return the per-user application data directory."""
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / APP_NAME
        return Path.home() / "AppData" / "Local" / APP_NAME
    return Path.home() / ".cache" / APP_NAME


def get_log_dir() -> Path:
    """Return log directory path and ensure it exists."""
    log_dir = get_app_data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def get_log_file_path() -> Path:
    """Return the main log file path."""
    return get_log_dir() / LOG_FILENAME


def setup_logger(name: str = APP_NAME) -> logging.Logger:
    """Configure and return the application logger."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(threadName)s | %(name)s | %(message)s"
    )

    # Console output for local/dev runs.
    c_handler = logging.StreamHandler(sys.stdout)
    c_handler.setLevel(logging.INFO)
    c_handler.setFormatter(formatter)
    logger.addHandler(c_handler)

    # Persistent rotating file logs for user bug reporting.
    f_handler = RotatingFileHandler(
        get_log_file_path(),
        maxBytes=2 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    f_handler.setLevel(logging.DEBUG)
    f_handler.setFormatter(formatter)
    logger.addHandler(f_handler)

    return logger


def install_global_exception_hooks(logger_instance: logging.Logger) -> None:
    """Capture uncaught exceptions in both main and background threads."""

    def _sys_excepthook(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            return sys.__excepthook__(exc_type, exc_value, exc_traceback)
        logger_instance.critical(
            "Uncaught exception",
            exc_info=(exc_type, exc_value, exc_traceback),
        )

    sys.excepthook = _sys_excepthook

    def _threading_excepthook(args: threading.ExceptHookArgs):
        logger_instance.critical(
            "Uncaught thread exception in %s",
            args.thread.name if args.thread else "unknown-thread",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    threading.excepthook = _threading_excepthook


# Global logger instance
logger = setup_logger()
install_global_exception_hooks(logger)
