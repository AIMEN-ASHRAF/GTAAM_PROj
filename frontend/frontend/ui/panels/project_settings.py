"""Project Settings window (File > Project). The settings are saved inside the project file."""
from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QSpinBox,
                             QVBoxLayout)

from ui.panels.icon_generator import pixmap

RESAMPLING = [("Bilinear  (smooth, best for slope)", "bilinear"),
              ("Nearest  (keeps the original heights)", "nearest"),
              ("Cubic  (sharper than bilinear)", "cubic")]


class ProjectSettingsDialog(QDialog):
    """Analyze in UTM, UTM zone and resampling. `preview(zone)` asks the backend which zone would be used."""

    STYLE = """
        QDialog#projectSettings { background: #eef1f4; }
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
        self.setMinimumWidth(500)
        self.setStyleSheet(self.STYLE)
        self._preview, self._layer_name = preview, layer_name

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

        card = QFrame()
        card.setObjectName("psCard")
        c = QVBoxLayout(card)
        c.setContentsMargins(16, 14, 16, 16)
        c.setSpacing(10)
        sec = QLabel("ANALYSIS")
        sec.setObjectName("psSection")
        c.addWidget(sec)

        self.switch = QCheckBox("Analyze in UTM")
        self.switch.setObjectName("psSwitch")
        self.switch.setChecked(bool(settings.get("analyze_in_utm")))
        c.addWidget(self.switch)
        h = QLabel("On: a degree DEM is first moved to UTM (metres), then Hillshade, Slope, Aspect, Curvature, "
                   "Roughness, TPI and Ruggedness are computed on that copy. Off: they use the DEM as loaded. "
                   "Your DEM is never changed.")
        h.setObjectName("psHelp")
        h.setWordWrap(True)
        c.addWidget(h)

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

        row2 = QHBoxLayout()
        n2 = QLabel("Resampling")
        n2.setObjectName("psName")
        self.resampling = QComboBox()
        for label, key in RESAMPLING:
            self.resampling.addItem(label, key)
        self.resampling.setCurrentIndex(max(0, self.resampling.findData(settings.get("resampling", "bilinear"))))
        row2.addWidget(n2)
        row2.addStretch(1)
        row2.addWidget(self.resampling)
        c.addLayout(row2)

        self.hint = QLabel("")
        self.hint.setWordWrap(True)
        c.addWidget(self.hint)
        root.addWidget(card)

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

    # ---- values ----
    def zone_text(self) -> str:
        if self.zone_mode.currentIndex() == 0:
            return "auto"
        return f"{self.zone_num.value()}{'N' if self.zone_hemi.currentIndex() == 0 else 'S'}"

    def values(self) -> dict:
        return {"analyze_in_utm": self.switch.isChecked(), "utm_zone": self.zone_text(),
                "resampling": self.resampling.currentData()}

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
