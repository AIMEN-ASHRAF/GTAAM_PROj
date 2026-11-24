"""Project Settings window (File > Project). The settings are saved inside the project file.

Five pages, like the proposal: Coordinate System, Units & Analysis, Display, Project, Performance.
`ProjectSettingsDialog(parent, settings, layer_name, preview)`; `values()` returns the full settings dict.
"""
from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFrame, QHBoxLayout, QLabel, QLineEdit,
                             QListWidget, QPushButton, QSpinBox, QStackedWidget, QVBoxLayout, QWidget)

from ui.panels.icon_generator import pixmap

RESAMPLING = [("Bilinear  (smooth, best for slope)", "bilinear"),
              ("Nearest  (keeps the original heights)", "nearest"),
              ("Cubic  (sharper than bilinear)", "cubic")]
DISTANCE = [("Metres", "metres"), ("Kilometres", "kilometres"), ("Feet", "feet"), ("Miles", "miles")]
AREA = [("Square metres", "square_metres"), ("Hectares", "hectares"), ("Square kilometres", "square_kilometres"),
        ("Acres", "acres")]
HEIGHT = [("Metres", "metres"), ("Feet", "feet")]
SLOPE_UNIT = [("Degrees", "degrees"), ("Percent", "percent")]
SLOPE_METHOD = [("Planar  (like ArcMap Slope)", "planar"), ("Geodesic  (true ground distances)", "geodesic")]
COORD_FORMAT = [("Decimal degrees", "decimal"), ("Degrees, minutes, seconds", "dms")]
AUTOSAVE = [("Off", 0), ("Every 1 minute", 1), ("Every 5 minutes", 5), ("Every 10 minutes", 10),
            ("Every 30 minutes", 30)]
PREVIEW = [("Low (fastest)", "low"), ("Medium", "medium"), ("High", "high"), ("Full resolution", "full")]
MEMORY = [("No limit", 0), ("512 MB", 512), ("1 GB", 1024), ("2 GB", 2048), ("4 GB", 4096)]

PAGES = ["Coordinate System", "Units & Analysis", "Display", "Project", "Performance"]


def _combo(options, current) -> QComboBox:
    box = QComboBox()
    for label, key in options:
        box.addItem(label, key)
    box.setCurrentIndex(max(0, box.findData(current)))
    return box


class ProjectSettingsDialog(QDialog):
    STYLE = """
        QDialog#projectSettings { background: #eef1f4; }
        QListWidget#psNav { background: #e4e9ee; border: none; border-radius: 10px; padding: 6px; outline: none; }
        QListWidget#psNav::item { color: #34404c; padding: 9px 12px; border-radius: 7px; font-size: 13px; }
        QListWidget#psNav::item:selected { background: #ffffff; color: #1f6f9a; font-weight: 700; }
        QFrame#psCard { background: #ffffff; border: 1px solid #dde2e7; border-radius: 12px; }
        QLabel#psTitle { color: #1b2530; font-size: 17px; font-weight: 700; }
        QLabel#psSub { color: #6b737b; font-size: 12px; }
        QLabel#psSection { color: #6b737b; font-size: 10px; font-weight: 700; letter-spacing: 1px; }
        QLabel#psName { color: #1b2530; font-size: 13px; font-weight: 600; }
        QLabel#psHelp { color: #8a949c; font-size: 11px; }
        QLabel#psHint { color: #2f6585; font-size: 12px; background: #eaf3f8; border-radius: 7px; padding: 8px 10px; }
        QLabel#psWarn { color: #7a5a1a; font-size: 12px; background: #fbf3df; border-radius: 7px; padding: 8px 10px; }
        QCheckBox#psSwitch { color: #1b2530; font-size: 14px; font-weight: 700; spacing: 8px; }
        QFrame#psRule { background: #edf0f3; max-height: 1px; min-height: 1px; border: none; }
    """

    def __init__(self, parent, settings: dict, layer_name: str | None,
                 preview: Callable[[str], dict | None]) -> None:
        super().__init__(parent)
        self.setObjectName("projectSettings")
        self.setWindowTitle("Project Settings")
        self.setModal(True)
        self.setMinimumSize(760, 520)
        self.setStyleSheet(self.STYLE)
        self._preview, self._layer_name = preview, layer_name
        self._keep = dict(settings)            # fields this window does not edit stay as they were

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)
        head = QHBoxLayout()
        ic = QLabel()
        ic.setPixmap(pixmap("sliders", "#1f6f9a", 26))
        titles = QVBoxLayout()
        titles.setSpacing(0)
        t = QLabel("Project Settings")
        t.setObjectName("psTitle")
        s = QLabel("Saved with this project. A new project starts with the defaults.")
        s.setObjectName("psSub")
        titles.addWidget(t)
        titles.addWidget(s)
        head.addWidget(ic)
        head.addLayout(titles, 1)
        root.addLayout(head)

        body = QHBoxLayout()
        body.setSpacing(14)
        self.nav = QListWidget()
        self.nav.setObjectName("psNav")
        self.nav.setFixedWidth(190)
        self.nav.addItems(PAGES)
        self.stack = QStackedWidget()
        body.addWidget(self.nav)
        body.addWidget(self.stack, 1)
        root.addLayout(body, 1)

        self.stack.addWidget(self._page_coordinates(settings))
        self.stack.addWidget(self._page_units(settings))
        self.stack.addWidget(self._page_display(settings))
        self.stack.addWidget(self._page_project(settings))
        self.stack.addWidget(self._page_performance(settings))
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.setObjectName("secondaryButton")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("Apply")
        ok.setObjectName("primaryButton")
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(ok)
        root.addLayout(buttons)

        for w in (self.switch, self.zone_mode, self.zone_num, self.zone_hemi, self.resampling):
            sig = w.toggled if isinstance(w, QCheckBox) else (w.valueChanged if isinstance(w, QSpinBox) else w.currentIndexChanged)
            sig.connect(self._refresh)
        self._refresh()

    # ---- building blocks ----
    def _card(self, section: str) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        card = QFrame()
        card.setObjectName("psCard")
        c = QVBoxLayout(card)
        c.setContentsMargins(16, 14, 16, 16)
        c.setSpacing(10)
        sec = QLabel(section.upper())
        sec.setObjectName("psSection")
        c.addWidget(sec)
        outer.addWidget(card)
        outer.addStretch(1)
        return page, c

    @staticmethod
    def _row(layout: QVBoxLayout, name: str, widget: QWidget, help_text: str = "") -> None:
        row = QHBoxLayout()
        n = QLabel(name)
        n.setObjectName("psName")
        row.addWidget(n)
        row.addStretch(1)
        row.addWidget(widget)
        layout.addLayout(row)
        if help_text:
            h = QLabel(help_text)
            h.setObjectName("psHelp")
            h.setWordWrap(True)
            layout.addWidget(h)

    @staticmethod
    def _note(layout: QVBoxLayout, text: str) -> None:
        h = QLabel(text)
        h.setObjectName("psHelp")
        h.setWordWrap(True)
        layout.addWidget(h)

    # ---- pages ----
    def _page_coordinates(self, settings: dict) -> QWidget:
        page, c = self._card("Analysis coordinate system")
        self.switch = QCheckBox("Analyze in UTM")
        self.switch.setObjectName("psSwitch")
        self.switch.setChecked(bool(settings.get("analyze_in_utm")))
        c.addWidget(self.switch)
        self._note(c, "On: a degree DEM is first moved to UTM (metres), then Hillshade, Slope, Aspect, Curvature, "
                      "Roughness, TPI and Ruggedness are computed on that copy. Off: they use the DEM as loaded. "
                      "Your DEM is never changed.")
        rule = QFrame()
        rule.setObjectName("psRule")
        c.addWidget(rule)

        zone = str(settings.get("utm_zone", "auto")).upper()
        row = QHBoxLayout()
        n = QLabel("UTM zone")
        n.setObjectName("psName")
        self.zone_mode = QComboBox()
        self.zone_mode.addItems(["Automatic (from the DEM)", "Choose zone"])
        self.zone_num = QSpinBox()
        self.zone_num.setRange(1, 60)
        self.zone_num.setValue(43)
        self.zone_hemi = QComboBox()
        self.zone_hemi.addItems(["North", "South"])
        if zone != "AUTO" and len(zone) >= 2 and zone[:-1].isdigit():
            self.zone_mode.setCurrentIndex(1)
            self.zone_num.setValue(int(zone[:-1]))
            self.zone_hemi.setCurrentIndex(0 if zone[-1] == "N" else 1)
        row.addWidget(n)
        row.addStretch(1)
        row.addWidget(self.zone_mode)
        row.addWidget(self.zone_num)
        row.addWidget(self.zone_hemi)
        c.addLayout(row)

        self.resampling = _combo(RESAMPLING, settings.get("resampling", "bilinear"))
        self._row(c, "Resampling", self.resampling)
        self.hint = QLabel("")
        self.hint.setWordWrap(True)
        c.addWidget(self.hint)
        return page

    def _page_units(self, settings: dict) -> QWidget:
        page, c = self._card("Units")
        self.distance = _combo(DISTANCE, settings.get("distance_unit", "metres"))
        self.area = _combo(AREA, settings.get("area_unit", "hectares"))
        self.height = _combo(HEIGHT, settings.get("height_unit", "metres"))
        self.slope_unit = _combo(SLOPE_UNIT, settings.get("slope_unit", "degrees"))
        self._row(c, "Distance", self.distance)
        self._row(c, "Area", self.area)
        self._row(c, "Height", self.height)
        self._row(c, "Slope", self.slope_unit)
        rule = QFrame()
        rule.setObjectName("psRule")
        c.addWidget(rule)
        sec = QLabel("ANALYSIS DEFAULTS")
        sec.setObjectName("psSection")
        c.addWidget(sec)
        self.match = QCheckBox("Match ArcMap behaviour")
        self.match.setObjectName("psSwitch")
        self.match.setChecked(bool(settings.get("match_arcmap", True)))
        c.addWidget(self.match)
        self.method = _combo(SLOPE_METHOD, settings.get("slope_method", "planar"))
        self._row(c, "Slope / aspect method", self.method)
        self.azimuth = QDoubleSpinBox()
        self.azimuth.setRange(0, 360)
        self.azimuth.setDecimals(0)
        self.azimuth.setSuffix("°")
        self.azimuth.setValue(float(settings.get("hillshade_azimuth", 315)))
        self.altitude = QDoubleSpinBox()
        self.altitude.setRange(0, 90)
        self.altitude.setDecimals(0)
        self.altitude.setSuffix("°")
        self.altitude.setValue(float(settings.get("hillshade_altitude", 45)))
        self.interval = QDoubleSpinBox()
        self.interval.setRange(0.01, 100000)
        self.interval.setDecimals(2)
        self.interval.setSuffix(" m")
        self.interval.setValue(float(settings.get("contour_interval", 100)))
        self._row(c, "Hillshade azimuth", self.azimuth)
        self._row(c, "Hillshade altitude", self.altitude)
        self._row(c, "Contour interval", self.interval)
        self._note(c, "Match ArcMap fixes the method to Planar and the hillshade to 315° / 45°, like ArcMap's own "
                      "defaults. Untick it to choose your own. Each tool can still override these defaults.")
        self.match.toggled.connect(self._arcmap_lock)
        self._arcmap_lock(self.match.isChecked())
        return page

    def _arcmap_lock(self, on: bool) -> None:
        """With Match ArcMap on, the settings ArcMap fixes are shown as ArcMap's values and cannot be edited."""
        for widget in (self.method, self.azimuth, self.altitude):
            widget.setEnabled(not on)
        if on:
            self.method.setCurrentIndex(max(0, self.method.findData("planar")))
            self.azimuth.setValue(315)
            self.altitude.setValue(45)

    def _page_display(self, settings: dict) -> QWidget:
        page, c = self._card("Display")
        self.decimals = QSpinBox()
        self.decimals.setRange(0, 8)
        self.decimals.setValue(int(settings.get("decimal_places", 4)))
        self._row(c, "Decimal places", self.decimals, "How many decimals results and statistics are shown with.")
        self.scale_bar = QCheckBox("Show scale bar on the map")
        self.scale_bar.setObjectName("psSwitch")
        self.scale_bar.setChecked(bool(settings.get("scale_bar", True)))
        c.addWidget(self.scale_bar)
        self.coord_format = _combo(COORD_FORMAT, settings.get("coordinate_format", "decimal"))
        self._row(c, "Coordinate format", self.coord_format)
        return page

    def _page_project(self, settings: dict) -> QWidget:
        page, c = self._card("Project")
        self.author = QLineEdit(str(settings.get("author", "")))
        self.author.setMinimumWidth(240)
        self.author.setMaxLength(120)
        self.author.setPlaceholderText("Your name")
        self._row(c, "Author", self.author)
        self.autosave = _combo(AUTOSAVE, int(settings.get("auto_save_minutes", 0)))
        self._row(c, "Auto-save", self.autosave, "Saves the project to its file at this interval (the project must "
                                                 "have been saved once).")
        return page

    def _page_performance(self, settings: dict) -> QWidget:
        page, c = self._card("Performance")
        self.preview_res = _combo(PREVIEW, settings.get("preview_resolution", "high"))
        self._row(c, "Preview resolution", self.preview_res, "Lower is faster on large DEMs. Results are always "
                                                              "computed at full resolution.")
        self.memory = _combo(MEMORY, int(settings.get("memory_limit_mb", 0)))
        self._row(c, "Memory limit", self.memory)
        return page

    # ---- values ----
    def zone_text(self) -> str:
        if self.zone_mode.currentIndex() == 0:
            return "auto"
        return f"{self.zone_num.value()}{'N' if self.zone_hemi.currentIndex() == 0 else 'S'}"

    def values(self) -> dict:
        return {**self._keep,
                "analyze_in_utm": self.switch.isChecked(), "utm_zone": self.zone_text(),
                "resampling": self.resampling.currentData(),
                "distance_unit": self.distance.currentData(), "area_unit": self.area.currentData(),
                "height_unit": self.height.currentData(), "slope_unit": self.slope_unit.currentData(),
                "match_arcmap": self.match.isChecked(), "slope_method": self.method.currentData(),
                "hillshade_azimuth": float(self.azimuth.value()), "hillshade_altitude": float(self.altitude.value()),
                "contour_interval": float(self.interval.value()),
                "decimal_places": int(self.decimals.value()), "scale_bar": self.scale_bar.isChecked(),
                "coordinate_format": self.coord_format.currentData(),
                "author": self.author.text().strip(), "auto_save_minutes": int(self.autosave.currentData()),
                "preview_resolution": self.preview_res.currentData(),
                "memory_limit_mb": int(self.memory.currentData())}

    # ---- what is enabled, and the preview line ----
    def _refresh(self) -> None:
        on = self.switch.isChecked()
        choose = self.zone_mode.currentIndex() == 1
        self.zone_mode.setEnabled(on)
        self.zone_num.setEnabled(on and choose)
        self.zone_hemi.setEnabled(on and choose)
        self.zone_num.setVisible(choose)
        self.zone_hemi.setVisible(choose)
        self.resampling.setEnabled(on)
        if not on:
            self._say("Analyze in UTM is off: terrain tools use the DEM as loaded (degrees are converted to metres "
                      "cell by cell).", warn=False)
            return
        if not self._layer_name:
            self._say("Load a DEM to see which UTM zone will be used.", warn=False)
            return
        try:
            p = self._preview(self.zone_text())
        except Exception:
            p = None
        if not p:
            self._say("Could not check the zone right now.", warn=True)
        elif p.get("applies"):
            self._say(f"Will use UTM {p['zone']} (EPSG:{p['epsg']}) for {self._layer_name}. Results are saved as new "
                      f"layers in UTM.", warn=False)
        else:
            self._say(p.get("reason") or "UTM does not apply to this layer.", warn=True)

    def _say(self, text: str, warn: bool) -> None:
        self.hint.setObjectName("psWarn" if warn else "psHint")
        self.hint.setStyleSheet(self.STYLE)          # re-read the style for the new object name
        self.hint.setText(text)
