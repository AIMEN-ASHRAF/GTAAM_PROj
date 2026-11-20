"""Attribute table window: the rows of a vector layer, like ArcMap's table.

The backend sends the rows (GET /file/add-data/layers/{id}/attributes). Clicking a column
header sorts by that field; the sorting itself is done by the backend.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView, QDialog, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

MAX_ROWS = 5000                      # one page; a bigger layer shows its first 5,000 rows


class AttributeTableWindow(QDialog):
    closed = pyqtSignal()

    STYLE = """
        QDialog#attributeWindow { background: #e4e7ea; }
        QLabel#attributeTitle { color: #252a2f; font-size: 13px; font-weight: 700; }
        QLabel#attributeInfo { color: #6b737b; font-size: 11px; }
        QTableWidget { background: #ffffff; border: 1px solid #c5cbd1; gridline-color: #e3e6e9;
                       alternate-background-color: #f4f6f8; font-size: 12px; }
        QHeaderView::section { background: #eef0f2; color: #343a40; border: none;
                               border-right: 1px solid #d0d4d8; border-bottom: 1px solid #c5cbd1;
                               padding: 4px 8px; font-weight: 700; }
        QPushButton { background: #ffffff; border: 1px solid #c5cbd1; border-radius: 6px; padding: 4px 12px; }
        QPushButton:hover { background: #f1f4f6; }
    """

    def __init__(self, parent: QWidget, api_get) -> None:
        super().__init__(parent)
        self._api_get = api_get
        self._layer_id: str | None = None
        self._sort: str | None = None
        self._descending = False
        self.setObjectName("attributeWindow")
        self.setWindowTitle("Attribute Table")
        self.setWindowFlag(Qt.WindowType.Tool, True)
        self.setModal(False)
        self.resize(560, 360)
        self.setStyleSheet(self.STYLE)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 10)
        outer.setSpacing(8)
        self.title = QLabel("")
        self.title.setObjectName("attributeTitle")
        outer.addWidget(self.title)

        self.table = QTableWidget(0, 0)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)          # FID is already the first column
        self.table.verticalHeader().setDefaultSectionSize(24)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionsClickable(True)
        self.table.horizontalHeader().sectionClicked.connect(self._header_clicked)
        outer.addWidget(self.table, 1)

        foot = QHBoxLayout()
        self.info = QLabel("")
        self.info.setObjectName("attributeInfo")
        foot.addWidget(self.info, 1)
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        foot.addWidget(close)
        outer.addLayout(foot)

    # ----- data ----------------------------------------------------------------
    def show_layer(self, layer_id: str, name: str) -> None:
        self._layer_id = layer_id
        self._sort = None
        self._descending = False
        self.title.setText(f"Attributes of {name}")
        self.load()

    def load(self) -> None:
        if not self._layer_id:
            return
        params = {"offset": 0, "limit": MAX_ROWS}
        if self._sort:
            params["sort"] = self._sort
            params["descending"] = "true" if self._descending else "false"
        data = self._api_get(f"/file/add-data/layers/{self._layer_id}/attributes", params)
        fields = list(data.get("fields", []))
        rows = data.get("rows", [])
        total = int(data.get("total", len(rows)))

        columns = ["FID"] + fields
        self.table.setSortingEnabled(False)
        self.table.clear()
        self.table.setColumnCount(len(columns))
        self.table.setRowCount(len(rows))
        self.table.setHorizontalHeaderLabels(columns)
        for r, row in enumerate(rows):
            self._cell(r, 0, row["fid"])
            for c, name in enumerate(fields, start=1):
                self._cell(r, c, row["values"].get(name))
        self.table.resizeColumnsToContents()
        arrow = ("  ▼" if self._descending else "  ▲") if self._sort else ""
        if self._sort in fields:
            idx = fields.index(self._sort) + 1
            self.table.horizontalHeaderItem(idx).setText(self._sort + arrow)
        if not fields:
            self.info.setText(f"{total} features · this layer has no attribute fields")
        elif total > len(rows):
            self.info.setText(f"Showing the first {len(rows):,} of {total:,} features")
        else:
            self.info.setText(f"{total:,} features · {len(fields)} fields · click a column name to sort")

    def _cell(self, r: int, c: int, value) -> None:
        if value is None:
            text, align = "", Qt.AlignmentFlag.AlignLeft
        elif isinstance(value, bool):
            text, align = str(value), Qt.AlignmentFlag.AlignLeft
        elif isinstance(value, (int, float)):
            text = f"{value:,.6f}".rstrip("0").rstrip(".") if isinstance(value, float) else str(value)
            align = Qt.AlignmentFlag.AlignRight
        else:
            text, align = str(value), Qt.AlignmentFlag.AlignLeft
        item = QTableWidgetItem(text)
        item.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
        self.table.setItem(r, c, item)

    def _header_clicked(self, section: int) -> None:
        if section == 0:                                   # FID: back to file order
            self._sort, self._descending = None, False
        else:
            name = self.table.horizontalHeaderItem(section).text().split("  ")[0]
            if self._sort == name:
                self._descending = not self._descending
            else:
                self._sort, self._descending = name, False
        self.load()

    def closeEvent(self, e) -> None:
        self.closed.emit()
        super().closeEvent(e)
