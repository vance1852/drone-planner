from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from file_persistence import load_route, save_route
from map_canvas import MapCanvas
from models import (
    NO_FLY_ZONE_REASONS,
    RoutePlan,
    get_default_altitude_zones,
    get_default_no_fly_zones,
)
from right_panel import RightPanel
from route_analyzer import analyze_route


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

        self.nofly_reason_label = QLabel("禁飞原因:")
        self.nofly_reason_combo = QComboBox()
        self.nofly_reason_combo.addItems(NO_FLY_ZONE_REASONS)
        self.nofly_reason_combo.setFixedWidth(100)
        self.nofly_reason_combo.setFixedHeight(30)
        self.nofly_reason_label.setVisible(False)
        self.nofly_reason_combo.setVisible(False)
        toolbar.addWidget(self.nofly_reason_label)
        toolbar.addWidget(self.nofly_reason_combo)

        self.altitude_limit_label = QLabel("限高值:")
        self.altitude_limit_spin = QDoubleSpinBox()
        self.altitude_limit_spin.setRange(0, 500)
        self.altitude_limit_spin.setValue(120)
        self.altitude_limit_spin.setSuffix(" m")
        self.altitude_limit_spin.setFixedHeight(30)
        self.altitude_limit_spin.setFixedWidth(100)
        self.altitude_limit_label.setVisible(False)
        self.altitude_limit_spin.setVisible(False)
        toolbar.addWidget(self.altitude_limit_label)
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
        self.nofly_reason_label.setVisible(mode == MapCanvas.MODE_NOFLY)
        self.nofly_reason_combo.setVisible(mode == MapCanvas.MODE_NOFLY)
        self.altitude_limit_label.setVisible(mode == MapCanvas.MODE_ALTITUDE)
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
