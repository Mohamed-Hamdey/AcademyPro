"""
Small UI helpers that don't fit in any other module.
"""

from qtpy.QtCore import QTimer, QObject


class Debouncer(QObject):
    """
    Delays a callable until a quiet period elapses.

    Usage:

        self._search_debouncer = Debouncer(250, self.refresh, parent=self)

        # Connect the signal to debounce(), not to refresh() directly.
        self.search_input.textChanged.connect(self._search_debouncer.trigger)

    Every time `trigger()` is called, the timer restarts. The wrapped
    callable only fires once 250ms have passed without another trigger.
    """

    def __init__(self, delay_ms: int, callback, parent=None):
        super().__init__(parent)
        self._callback = callback
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(delay_ms)
        self._timer.timeout.connect(self._fire)

    def trigger(self, *_args, **_kwargs):
        """Call this from a signal; restarts the countdown."""
        self._timer.start()

    def _fire(self):
        try:
            self._callback()
        except Exception:
            import logging
            logging.getLogger(__name__).exception(
                "Debounced callback failed"
            )

    def cancel(self):
        """Stop any pending trigger without firing."""
        self._timer.stop()