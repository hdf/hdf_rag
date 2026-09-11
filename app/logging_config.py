"""Console and rotating file logging for application events."""

import logging
from contextlib import contextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path


@contextmanager
def application_logging(path: str):
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        log_path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    console_handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    app_logger = logging.getLogger("app")
    previous_level, previous_propagate = app_logger.level, app_logger.propagate
    app_logger.setLevel(logging.INFO)
    app_logger.propagate = False
    handlers = (file_handler, console_handler)
    for handler in handlers:
        handler.setFormatter(formatter)
        app_logger.addHandler(handler)
    try:
        yield
    except Exception as exc:
        app_logger.error("Application lifecycle failed: error_type=%s", type(exc).__name__)
        raise
    finally:
        for handler in handlers:
            app_logger.removeHandler(handler)
            handler.close()
        app_logger.setLevel(previous_level)
        app_logger.propagate = previous_propagate
