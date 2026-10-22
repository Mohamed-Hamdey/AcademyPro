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


def get_date_range(range_key: str) -> tuple[str, str]:
    """Returns (date_from, date_to) in YYYY-MM-DD format based on the range key."""
    from datetime import date, timedelta
    import calendar
    
    today = date.today()
    
    if range_key == "this_month":
        first = date(today.year, today.month, 1)
        last = date(today.year, today.month, calendar.monthrange(today.year, today.month)[1])
    elif range_key == "last_30_days":
        first = today - timedelta(days=30)
        last = today
    elif range_key == "last_3_months":
        first = today - timedelta(days=90)
        last = today
    elif range_key == "this_year":
        first = date(today.year, 1, 1)
        last = date(today.year, 12, 31)
    else: # Default to this month
        first = date(today.year, today.month, 1)
        last = date(today.year, today.month, calendar.monthrange(today.year, today.month)[1])
        
    return first.isoformat(), last.isoformat()