"""Shared logging setup: timestamps, levels, and credential masking.

Per rules.md: use the built-in `logging` module with timestamps to track
scraping failures, embedding steps, and PDF compilation status.
Per autorules.md: API keys and webhook URLs must never appear in logs.
"""

import logging
import re
import sys

_SECRET_PATTERN = re.compile(
    r"(fc-[A-Za-z0-9_\-]{8,}|sk-[A-Za-z0-9_\-]{8,}|xoxb-[A-Za-z0-9_\-]{8,}|"
    r"SG\.[A-Za-z0-9_\-.]{8,}|eyJ[A-Za-z0-9_\-.]{20,})"
)
_MASK = "***REDACTED***"


class SecretMaskingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _SECRET_PATTERN.sub(_MASK, record.msg)
        if record.args:
            record.args = tuple(
                _SECRET_PATTERN.sub(_MASK, arg) if isinstance(arg, str) else arg
                for arg in record.args
            )
        return True


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s", "%Y-%m-%d %H:%M:%S")
        )
        handler.addFilter(SecretMaskingFilter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger
