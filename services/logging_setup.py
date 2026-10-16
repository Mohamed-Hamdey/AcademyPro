"""
Logging setup and the global exception handler.

Two responsibilities:

  1. setup_logging()
       Configure the root logger to write to
       %LOCALAPPDATA%\\AcademySystem\\logs\\app.log via a rotating
       file handler (5 MB x 5 files). Also mirrors the same lines to
       stderr for `python main.py` runs.

  2. install_excepthook(parent_getter=None)
       Replace sys.excepthook so that any unhandled exception is:
         - logged with a full traceback
         - shown to the user in a themed dialog (when Qt is up)
       `parent_getter` is an optional callable returning the current
       top-level widget to use as the dialog parent — needed because
       the excepthook may fire when there is no obvious active window.

Usage in main.py:

    from services.logging_setup import setup_logging, install_excepthook
    setup_logging()
    install_excepthook(lambda: QApplication.activeWindow())
    # ... rest of startup ...
"""

import logging
import os
import sys
import traceback
from logging.handlers import RotatingFileHandler

from paths import AppPaths


_LOG_FORMAT = "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_MAX_BYTES = 5 * 1024 * 1024   # 5 MB
_BACKUP_COUNT = 5

_configured = False


def setup_logging(level: int = logging.INFO) -> str:
    """
    Configure the root logger. Idempotent — safe to call twice.

    Returns the absolute path of the log file.
    """
    global _configured

    log_dir = AppPaths.logs_dir()
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "app.log")

    if _configured:
        return log_path

    root = logging.getLogger()
    root.setLevel(level)

    # Drop any handlers added by a previous (partial) call.
    for h in list(root.handlers):
        root.removeHandler(h)

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    # Rotating file handler — the durable sink.
    try:
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=_MAX_BYTES,
            backupCount=_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except Exception as e:
        # Never let logging setup crash the app.
        sys.stderr.write(f"[logging_setup] file handler failed: {e}\n")

    # Stderr handler — visible when running from a terminal.
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(formatter)
    root.addHandler(stderr_handler)

    # Silence overly chatty third-party loggers we don't care about.
    logging.getLogger("PySide6").setLevel(logging.WARNING)

    _configured = True
    logging.getLogger(__name__).info("Logging configured → %s", log_path)
    return log_path


def install_excepthook(parent_getter=None) -> None:
    """
    Install a global exception hook that logs the traceback and shows a
    themed error dialog.

    `parent_getter` — a zero-argument callable returning the widget to
    use as the dialog parent, or None. Called lazily, on crash.
    """

    def _hook(exc_type, exc_value, exc_tb):
        # Never recurse into ourselves on a KeyboardInterrupt.
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return

        tb_text = "".join(
            traceback.format_exception(exc_type, exc_value, exc_tb)
        )
        logging.getLogger("unhandled").error(
            "Unhandled exception:\n%s", tb_text
        )

        # Try to show a themed dialog. If Qt isn't ready yet, or the
        # dialog itself fails, we've still written the log.
        try:
            _show_crash_dialog(parent_getter, exc_value, tb_text)
        except Exception as dialog_err:
            sys.stderr.write(
                f"[excepthook] failed to show dialog: {dialog_err}\n"
            )

    sys.excepthook = _hook


def _show_crash_dialog(parent_getter, exc_value, tb_text):
    """Best-effort themed error dialog."""
    # Import lazily so we don't drag Qt into the app before it's ready.
    from qtpy.QtWidgets import QApplication
    from ui.message_box import error as show_error
    from ui.i18n import t

    if QApplication.instance() is None:
        return  # no Qt yet — the log line is all we can do

    parent = None
    if parent_getter is not None:
        try:
            parent = parent_getter()
        except Exception:
            parent = None

    title = t("crash.title") or "Something went wrong"
    # Show the exception type + message; the full traceback is in the log.
    short = f"{exc_value.__class__.__name__}: {exc_value}"
    body = (
        f"{t('crash.body') or 'The app hit an unexpected error.'}\n\n"
        f"{short}\n\n"
        f"{t('crash.log_hint') or 'Details were written to the log folder.'}"
    )

    show_error(parent, title, body)