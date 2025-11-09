"""Utility helpers for removing Allure result artifacts."""

from __future__ import annotations

import argparse
import logging
import shutil
from collections.abc import Iterable, Sequence
from pathlib import Path


LOGGER = logging.getLogger("clean-allure")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DIRECTORIES = (
    Path("allure-results"),
    Path("allure-report"),
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Delete generated Allure result and report directories.",
    )
    parser.add_argument(
        "targets",
        nargs="*",
        type=Path,
        default=list(DEFAULT_DIRECTORIES),
        help="Directories to delete (relative to project root). Defaults to common Allure folders.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List directories that would be removed without deleting them.",
    )
    return parser.parse_args(argv)


def _resolve_targets(targets: Iterable[Path]) -> list[Path]:
    resolved: list[Path] = []
    for target in targets:
        candidate = PROJECT_ROOT / target
        if not candidate.exists():
            LOGGER.debug("Skipping %s because it does not exist", candidate)
            continue
        if not candidate.is_dir():
            LOGGER.warning("Skipping %s because it is not a directory", candidate)
            continue
        resolved.append(candidate)
    return resolved


def _delete_directories(targets: Iterable[Path], dry_run: bool) -> int:
    exit_code = 0
    for directory in targets:
        if dry_run:
            print(f"[dry-run] Would remove {directory}")
            continue
        try:
            shutil.rmtree(directory)
            print(f"Removed {directory}")
        except Exception as exc:  # pragma: no cover - defensive logging
            LOGGER.error("Failed to remove %s: %s", directory, exc)
            exit_code = 1
    return exit_code


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args(argv)
    targets = _resolve_targets(args.targets)

    if not targets:
        print("Nothing to remove; no matching Allure directories found.")
        return 0

    return _delete_directories(targets, args.dry_run)
