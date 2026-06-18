"""Shared stdout/stderr-split logging config for the api and worker services.

A flat helper module (deliberately not a package) imported by both services so
the INFO→stdout / WARNING+→stderr routing they rely on for log-capture testing
stays identical and can't drift. It lives at the repo root and is put on
sys.path by each service's run command: the worker runs as `python -m
worker.main` from the root, and the api is launched with `PYTHONPATH=.`.
"""

import logging
import sys


class _MaxLevelFilter(logging.Filter):
    """Pass only records strictly below a given level."""

    def __init__(self, max_level: int):
        super().__init__()
        self._max_level = max_level

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno < self._max_level


def configure_logging() -> None:
    """Route INFO/DEBUG to stdout and WARNING+ to stderr, line-buffered.

    Splitting by stream keeps INFO/DEBUG and WARNING+ separable downstream.
    The format uses %(name)s so each service is identified by its logger name.
    """
    fmt = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
    datefmt = "%Y-%m-%dT%H:%M:%S"

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.DEBUG)
    stdout_handler.addFilter(_MaxLevelFilter(logging.WARNING))
    stdout_handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.WARNING)
    stderr_handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    root.addHandler(stdout_handler)
    root.addHandler(stderr_handler)

    # Flush each line immediately so captured logs stay live.
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
