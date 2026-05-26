# SPDX-FileCopyrightText: 2026 Shaan Narendran <shaannaren06@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only

"""Optic: developer debug logging for the Observal CLI.

Configures loguru sinks based on --debug / --verbose flags.
Call ``setup_optic()`` once in the CLI callback.
Then use ``from loguru import logger`` in any CLI module.

By default (no flags): loguru is silent (no sinks).
--verbose: INFO+ to stderr.
--debug: DEBUG+ to stderr + file.
"""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger


def setup_optic(*, debug: bool = False, verbose: bool = False) -> None:
    """Configure loguru sinks for CLI based on verbosity flags.

    Args:
        debug: Enable DEBUG level (stderr + file).
        verbose: Enable INFO level (stderr only).
    """
    # Remove loguru's default stderr sink
    logger.remove()

    if debug:
        # Full debug to stderr
        logger.add(
            sys.stderr,
            level="DEBUG",
            colorize=True,
            format=(
                "<green>{time:HH:mm:ss.SSS}</green> | "
                "<level>{level:<7}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
                "<level>{message}</level>"
            ),
        )
        # Also write to file for post-mortem
        log_path = Path.home() / ".observal" / "logs" / "cli.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        logger.add(
            str(log_path),
            rotation="5 MB",
            retention=3,
            level="DEBUG",
            format=("{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<7} | {name}:{function}:{line} - {message}"),
        )
    elif verbose:
        # INFO+ to stderr only
        logger.add(
            sys.stderr,
            level="INFO",
            colorize=True,
            format=("<green>{time:HH:mm:ss.SSS}</green> | <level>{level:<7}</level> | <level>{message}</level>"),
        )
    # else: no sinks = silent (loguru no-ops gracefully)
