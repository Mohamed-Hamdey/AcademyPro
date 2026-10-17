"""
Table widget factory.

Standard QTableWidget setup used by every table in the app:
- headers from a list of strings
- per-column resize modes (from a list)
- selection by row
- read-only cells
- alternating row colors
- no grid lines

Usage:

    from ui.table_helpers import make_standard_table

    table = make_standard_table(
        headers=[t("players.col.id"), ...],
        column_modes=[("resize", ), ("stretch", ), ...],
        parent=self,
    )
    table.cellDoubleClicked.connect(self._on_row_double_clicked)
"""

from typing import Iterable, Optional

from qtpy.QtWidgets import QTableWidget, QHeaderView, QWidget
from qtpy.QtCore import Qt


_RESIZE = QHeaderView.ResizeMode.ResizeToContents
_STRETCH = QHeaderView.ResizeMode.Stretch


def make_standard_table(
    headers: list[str],
    column_modes: Optional[Iterable[str]] = None,
    parent: Optional[QWidget] = None,
    stretch_last: bool = False,
) -> QTableWidget:
    """
    Build a QTableWidget with the app's standard look.

    Args:
        headers:
            List of header labels (from `t(...)`).
        column_modes:
            Optional list, one entry per column, of "resize", "stretch",
            or "fixed". If omitted, all columns use "resize".
        parent:
            Optional parent widget. Pass `self` from the calling screen.
        stretch_last:
            If True, the final column will stretch to fill remaining
            space (equivalent to `column_modes[-1] == "stretch"`).
    """
    n = len(headers)
    table = QTableWidget(0, n, parent)

    table.setHorizontalHeaderLabels(headers)

    if column_modes is None:
        column_modes = ["resize"] * n

    hdr = table.horizontalHeader()
    for i, mode in enumerate(column_modes):
        if mode == "stretch":
            hdr.setSectionResizeMode(i, _STRETCH)
        elif mode == "fixed":
            hdr.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
        else:
            hdr.setSectionResizeMode(i, _RESIZE)

    if stretch_last and column_modes[-1] != "stretch":
        hdr.setSectionResizeMode(n - 1, _STRETCH)

    table.verticalHeader().setVisible(False)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setAlternatingRowColors(True)
    table.setShowGrid(False)
    table.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    return table