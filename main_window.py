from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from file_persistence import load_route, save_route
from geometry import haversine
from map_canvas import MapCanvas
from models import (
    NO_FLY_ZONE_REASONS,
    RoutePlan,
    get_default_altitude_zones,
    get_default_no_fly_zones,
)
from route_analyzer import AnalysisResult, analyze_route


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


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("无人机航线规划与禁飞区检测系统")
        self.resize(1280, 800)
        self._init_ui()
        self._load_preset_zones()
        self._connect_signals()
        self._apply_global_style()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(8, 4, 8, 4)
        toolbar.setSpacing(4)

        self.mode_label = QLabel("当前模式: 添加航点")
        self.mode_label.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        self.mode_label.setStyleSheet("color: #e0e8f0; padding: 4px 8px;")
        toolbar.addWidget(self.mode_label)

        self.btn_waypoint = QPushButton("📌 添加航点")
        self.btn_nofly = QPushButton("🚫 绘制禁飞区")
        self.btn_altitude = QPushButton("⚠ 限高区")
        self.btn_select = QPushButton("🖱 选择/拖拽")
        self.btn_clear_wp = QPushButton("🗑 清空航点")
        self.btn_clear_zones = QPushButton("🗑 清空区域")

        mode_btns = [self.btn_waypoint, self.btn_nofly, self.btn_altitude, self.btn_select]
        for btn in mode_btns:
            btn.setCheckable(True)
            btn.setFixedHeight(30)
            btn.setStyleSheet(
                "QPushButton { background: #2a3545; color: #c0d0e0; border-radius: 4px; padding: 0 12px; }"
                "QPushButton:checked { background: #1a8cff; color: white; }"
                "QPushButton:hover { background: #3a5070; }"
            )
        self.btn_waypoint.setChecked(True)

        for btn in [self.btn_clear_wp, self.btn_clear_zones]:
            btn.setFixedHeight(30)
            btn.setStyleSheet(
                "QPushButton { background: #5a2020; color: #e0a0a0; border-radius: 4px; padding: 0 12px; }"
                "QPushButton:hover { background: #7a3030; }"
            )

        for btn in mode_btns:
            toolbar.addWidget(btn)
        toolbar.addSpacing(20)
        toolbar.addWidget(self.btn_clear_wp)
        toolbar.addWidget(self.btn_clear_zones)
        toolbar.addStretch()

        self.nofly_reason_combo = QComboBox()
        self.nofly_reason_combo.addItems(NO_FLY_ZONE_REASONS)
        self.nofly_reason_combo.setFixedWidth(100)
        self.nofly_reason_combo.setFixedHeight(30)
        self.nofly_reason_combo.setVisible(False)
        toolbar.addWidget(QLabel("禁飞原因:"))
        toolbar.addWidget(self.nofly_reason_combo)

        self.altitude_limit_spin = QDoubleSpinBox()
        self.altitude_limit_spin.setRange(0, 500)
        self.altitude_limit_spin.setValue(120)
        self.altitude_limit_spin.setSuffix(" m")
        self.altitude_limit_spin.setFixedHeight(30)
        self.altitude_limit_spin.setFixedWidth(100)
        self.altitude_limit_spin.setVisible(False)
        toolbar.addWidget(QLabel("限高值:"))
        toolbar.addWidget(self.altitude_limit_spin)

        toolbar_frame = QFrame()
        toolbar_frame.setLayout(toolbar)
        toolbar_frame.setStyleSheet("QFrame { background: #1a2030; border-bottom: 1px solid #2a3545; }")
        main_layout.addWidget(toolbar_frame)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.canvas = MapCanvas()
        self.right_panel = RightPanel()

        splitter.addWidget(self.canvas)
        splitter.addWidget(self.right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)

        main_layout.addWidget(splitter)

    def _apply_global_style(self):
        self.setStyleSheet(
            "QWidget { background: #1e2433; color: #c0d0e0; }"
            "QSplitter::handle { background: #2a3545; width: 2px; }"
            "QTableWidget { background: #1a1f2b; gridline-color: #2a3545; border: 1px solid #2a3545; }"
            "QHeaderView::section { background: #252d3d; color: #a0b0c0; padding: 4px; border: 1px solid #2a3545; }"
            "QComboBox { background: #2a3545; border: 1px solid #3a4555; border-radius: 3px; padding: 2px 6px; color: #c0d0e0; }"
            "QComboBox QAbstractItemView { background: #2a3545; color: #c0d0e0; selection-background-color: #1a8cff; }"
            "QDoubleSpinBox { background: #2a3545; border: 1px solid #3a4555; border-radius: 3px; padding: 2px; color: #c0d0e0; }"
            "QLabel { background: transparent; }"
            "QScrollArea { border: none; }"
        )

    def _load_preset_zones(self):
        self.canvas.no_fly_zones = get_default_no_fly_zones()
        self.canvas.altitude_zones = get_default_altitude_zones()
        self.canvas.update()

    def _connect_signals(self):
        self.btn_waypoint.clicked.connect(lambda: self._set_mode(MapCanvas.MODE_WAYPOINT))
        self.btn_nofly.clicked.connect(lambda: self._set_mode(MapCanvas.MODE_NOFLY))
        self.btn_altitude.clicked.connect(lambda: self._set_mode(MapCanvas.MODE_ALTITUDE))
        self.btn_select.clicked.connect(lambda: self._set_mode(MapCanvas.MODE_SELECT))
        self.btn_clear_wp.clicked.connect(self._clear_waypoints)
        self.btn_clear_zones.clicked.connect(self._clear_zones)
        self.canvas.route_changed.connect(self._on_route_changed)
        self.canvas.zone_finished.connect(self._on_zone_finished)
        self.right_panel.analyze_requested.connect(self._analyze)
        self.right_panel.save_btn.clicked.connect(self._save)
        self.right_panel.load_btn.clicked.connect(self._load)
        self.nofly_reason_combo.currentTextChanged.connect(self._update_nofly_reason)
        self.altitude_limit_spin.valueChanged.connect(self._update_altitude_limit)

    def _set_mode(self, mode: str):
        self.canvas.set_mode(mode)
        mode_names = {
            MapCanvas.MODE_WAYPOINT: "添加航点",
            MapCanvas.MODE_NOFLY: "绘制禁飞区",
            MapCanvas.MODE_ALTITUDE: "绘制限高区",
            MapCanvas.MODE_SELECT: "选择/拖拽",
        }
        self.mode_label.setText(f"当前模式: {mode_names.get(mode, mode)}")
        self.btn_waypoint.setChecked(mode == MapCanvas.MODE_WAYPOINT)
        self.btn_nofly.setChecked(mode == MapCanvas.MODE_NOFLY)
        self.btn_altitude.setChecked(mode == MapCanvas.MODE_ALTITUDE)
        self.btn_select.setChecked(mode == MapCanvas.MODE_SELECT)
        self.nofly_reason_combo.setVisible(mode == MapCanvas.MODE_NOFLY)
        self.altitude_limit_spin.setVisible(mode == MapCanvas.MODE_ALTITUDE)

    def _on_route_changed(self):
        self.canvas.conflict_segments = []
        self.right_panel.update_waypoints(self.canvas.waypoints)

    def _on_zone_finished(self):
        pass

    def _update_nofly_reason(self, text: str):
        if self.canvas.no_fly_zones:
            self.canvas.no_fly_zones[-1].reason = text
            self.canvas.update()

    def _update_altitude_limit(self, val: float):
        if self.canvas.altitude_zones:
            self.canvas.altitude_zones[-1].altitude_limit = val
            self.canvas.update()

    def _clear_waypoints(self):
        self.canvas.waypoints.clear()
        self.canvas.conflict_segments.clear()
        self.canvas._reindex_waypoints()
        self.right_panel.update_waypoints([])
        self.right_panel.result_text.clear()
        self.canvas.update()

    def _clear_zones(self):
        self.canvas.no_fly_zones.clear()
        self.canvas.altitude_zones.clear()
        self.canvas.conflict_segments.clear()
        self.canvas.update()

    def _analyze(self):
        speed, battery_mah, voltage, power_w = self.right_panel.get_flight_params()
        result = analyze_route(
            self.canvas.waypoints,
            self.canvas.no_fly_zones,
            self.canvas.altitude_zones,
            speed_mps=speed,
            battery_mah=battery_mah,
            voltage=voltage,
            power_w=power_w,
        )
        self.canvas.conflict_segments = result.conflict_segments
        self.canvas.update()
        self.right_panel.update_waypoints(self.canvas.waypoints, result)
        self.right_panel.update_analysis(result)

    def _save(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "保存航线方案", "", "JSON 文件 (*.json)"
        )
        if not path:
            return
        speed, battery_mah, voltage, power_w = self.right_panel.get_flight_params()
        plan = RoutePlan(
            waypoints=list(self.canvas.waypoints),
            no_fly_zones=list(self.canvas.no_fly_zones),
            altitude_zones=list(self.canvas.altitude_zones),
            speed_mps=speed,
            battery_mah=battery_mah,
            voltage=voltage,
            power_w=power_w,
        )
        try:
            save_route(plan, path)
            QMessageBox.information(self, "保存成功", f"航线方案已保存至:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "保存失败", str(e))

    def _load(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "加载航线方案", "", "JSON 文件 (*.json)"
        )
        if not path:
            return
        try:
            plan = load_route(path)
            if plan is None:
                QMessageBox.warning(self, "加载失败", "无法读取文件")
                return
            self.canvas.waypoints = plan.waypoints
            self.canvas.no_fly_zones = plan.no_fly_zones
            self.canvas.altitude_zones = plan.altitude_zones
            self.canvas._reindex_waypoints()
            self.canvas.conflict_segments = []
            self.right_panel.speed_spin.setValue(plan.speed_mps)
            self.right_panel.battery_spin.setValue(plan.battery_mah)
            self.right_panel.voltage_spin.setValue(plan.voltage)
            self.right_panel.power_spin.setValue(plan.power_w)
            self.right_panel.update_waypoints(plan.waypoints)
            self.canvas.update()
            QMessageBox.information(self, "加载成功", "航线方案已加载")
        except Exception as e:
            QMessageBox.critical(self, "加载失败", str(e))
