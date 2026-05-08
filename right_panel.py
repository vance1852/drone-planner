from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWidgets import (
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from geometry import haversine
from route_analyzer import AnalysisResult


class RightPanel(QWidget):
    analyze_requested = pyqtSignal()
    delete_waypoint_requested = pyqtSignal(int)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedWidth(360)
        self._analysis: Optional[AnalysisResult] = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        title = QLabel("航线详情")
        title.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        title.setStyleSheet("color: #e0e8f0;")
        layout.addWidget(title)

        self.wp_table = QTableWidget(0, 4)
        self.wp_table.setHorizontalHeaderLabels(["序号", "经度", "纬度", "段距离km"])
        self.wp_table.horizontalHeader().setStretchLastSection(True)
        self.wp_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.wp_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.wp_table.verticalHeader().setVisible(False)
        self.wp_table.setMaximumHeight(220)
        layout.addWidget(self.wp_table)

        self.dist_label = QLabel("总距离: -- km")
        self.dist_label.setFont(QFont("Microsoft YaHei", 10))
        self.dist_label.setStyleSheet("color: #b0c0d0;")
        layout.addWidget(self.dist_label)

        param_frame = QFrame()
        param_frame.setFrameShape(QFrame.Shape.StyledPanel)
        param_layout = QGridLayout(param_frame)
        param_layout.setSpacing(4)

        labels = ["飞行速度(m/s):", "电池容量(mAh):", "电压(V):", "功耗(W):"]
        self.speed_spin = QDoubleSpinBox()
        self.speed_spin.setRange(1, 100)
        self.speed_spin.setValue(10.0)
        self.battery_spin = QDoubleSpinBox()
        self.battery_spin.setRange(100, 100000)
        self.battery_spin.setValue(5000.0)
        self.voltage_spin = QDoubleSpinBox()
        self.voltage_spin.setRange(1, 100)
        self.voltage_spin.setValue(14.8)
        self.power_spin = QDoubleSpinBox()
        self.power_spin.setRange(1, 2000)
        self.power_spin.setValue(200.0)

        spins = [self.speed_spin, self.battery_spin, self.voltage_spin, self.power_spin]
        for i, (lbl, spin) in enumerate(zip(labels, spins)):
            l = QLabel(lbl)
            l.setStyleSheet("color: #a0b0c0; font-size: 11px;")
            param_layout.addWidget(l, i, 0)
            param_layout.addWidget(spin, i, 1)

        layout.addWidget(param_frame)

        self.detect_btn = QPushButton("🔍 检测航线")
        self.detect_btn.setFixedHeight(36)
        self.detect_btn.setStyleSheet(
            "QPushButton { background: #1a8cff; color: white; font-weight: bold; "
            "border-radius: 4px; font-size: 13px; }"
            "QPushButton:hover { background: #0077e6; }"
            "QPushButton:pressed { background: #005bb5; }"
        )
        self.detect_btn.clicked.connect(self.analyze_requested.emit)
        layout.addWidget(self.detect_btn)

        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setMaximumHeight(200)
        self.result_text.setFont(QFont("Consolas", 9))
        self.result_text.setStyleSheet(
            "QTextEdit { background: #1a1f2b; color: #c0d0e0; border: 1px solid #2a3545; border-radius: 4px; }"
        )
        layout.addWidget(self.result_text)

        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("💾 保存方案")
        self.load_btn = QPushButton("📂 加载方案")
        for btn in [self.save_btn, self.load_btn]:
            btn.setFixedHeight(30)
            btn.setStyleSheet(
                "QPushButton { background: #2a3545; color: #c0d0e0; border-radius: 4px; }"
                "QPushButton:hover { background: #3a4555; }"
            )
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.load_btn)
        layout.addLayout(btn_layout)

        layout.addStretch()

    def get_flight_params(self):
        return (
            self.speed_spin.value(),
            self.battery_spin.value(),
            self.voltage_spin.value(),
            self.power_spin.value(),
        )

    def update_waypoints(self, waypoints, analysis: Optional[AnalysisResult] = None):
        self.wp_table.setRowCount(len(waypoints))
        cumulative = 0.0
        conflict_set = set()
        if analysis:
            conflict_set = set(analysis.conflict_segments)

        for i, wp in enumerate(waypoints):
            idx_item = QTableWidgetItem(str(i))
            idx_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            lon_item = QTableWidgetItem(f"{wp.lon:.6f}")
            lon_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            lat_item = QTableWidgetItem(f"{wp.lat:.6f}")
            lat_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            if i > 0:
                seg_dist = haversine(waypoints[i - 1].lon, waypoints[i - 1].lat, wp.lon, wp.lat)
                cumulative += seg_dist
                dist_item = QTableWidgetItem(f"{seg_dist:.3f}")
            else:
                dist_item = QTableWidgetItem("--")
            dist_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            is_conflict = (i - 1) in conflict_set or i in conflict_set
            if is_conflict:
                red_bg = QColor(180, 40, 40, 80)
                for item in [idx_item, lon_item, lat_item, dist_item]:
                    item.setBackground(red_bg)

            self.wp_table.setItem(i, 0, idx_item)
            self.wp_table.setItem(i, 1, lon_item)
            self.wp_table.setItem(i, 2, lat_item)
            self.wp_table.setItem(i, 3, dist_item)

        self.dist_label.setText(f"总距离: {cumulative:.3f} km")

    def update_analysis(self, result: AnalysisResult):
        self._analysis = result
        lines = []
        if result.passed:
            lines.append("✅ 航线检测通过")
        else:
            lines.append("❌ 航线检测未通过")

        lines.append(f"\n📏 总距离: {result.total_distance_km:.3f} km")
        lines.append(f"⏱ 预计飞行时间: {result.flight_time_min:.1f} min")
        lines.append(f"🔋 电池续航时间: {result.battery_time_min:.1f} min")
        if result.battery_sufficient:
            lines.append("✅ 电池续航充足")
        else:
            lines.append("❌ 电池续航不足")

        if result.conflict_segments:
            lines.append(f"\n🔴 冲突航段: {', '.join(str(s) for s in result.conflict_segments)}")
            for seg in result.segments:
                if seg.conflicts:
                    lines.append(f"  航段{seg.index}: {', '.join(seg.conflicts)}")

        for seg in result.segments:
            if seg.altitude_limits:
                lines.append(f"⚠ 航段{seg.index} 限高: {', '.join(seg.altitude_limits)}")

        for w in result.warnings:
            lines.append(f"⚠ {w}")

        self.result_text.setPlainText("\n".join(lines))

        color = "#1a3a1a" if result.passed else "#3a1a1a"
        self.result_text.setStyleSheet(
            f"QTextEdit {{ background: {color}; color: #c0d0e0; "
            "border: 1px solid #2a3545; border-radius: 4px; }}"
        )
