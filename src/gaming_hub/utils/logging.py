"""Logging bootstrap.

Configures application-wide logging based on settings. Supports both human-
readable and JSON structured output. Logging is intentionally not a service:
every module uses the standard library logger so the project has no runtime
dependency on a custom logging class.
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from gaming_hub.config.models import Settings


class _ColoredFormatter(logging.Formatter):
    """Simple colored formatter for local development."""

    COLORS: ClassVar[dict[str, str]] = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[35m",
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """Apply level color and return formatted log line."""
        level_color = self.COLORS.get(record.levelname, "")
        record.levelname = f"{level_color}{record.levelname}{self.RESET}"
        return super().format(record)


def configure_logging(settings: Settings) -> None:
    """Configure root logger from application settings.

    Args:
        settings: Validated application settings.
    """
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    handlers: list[logging.Handler] = []

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(level)

    if settings.log_json:
        formatter = logging.Formatter(
            fmt='{"timestamp":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}',
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    else:
        formatter = _ColoredFormatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    stdout_handler.setFormatter(formatter)
    handlers.append(stdout_handler)

    if settings.log_file_path:
        if settings.log_rotation:
            file_handler: logging.Handler = logging.handlers.RotatingFileHandler(
                settings.log_file_path,
                maxBytes=5_000_000,
                backupCount=3,
            )
        else:
            file_handler = logging.FileHandler(settings.log_file_path)
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)

    logging.basicConfig(
        level=level,
        handlers=handlers,
        force=True,
    )

    # Quiet down noisy third-party loggers by default.
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
