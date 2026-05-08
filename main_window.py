from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QColor, QFont, QIcon, QKeySequence
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QGroupBox,
    QLabel,
    QLineEdit,
    QDoubleSpinBox,
    QTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QFileDialog,
    QMessageBox,
    QSplitter,
    QToolBar,
    QStatusBar,
    QFrame,
    QScrollArea
)

from models import BatteryConfig, FlightPlan, AnalysisResult
from map_canvas import MapCanvas, CanvasMode
from analyzer import FlightAnalyzer
from persistence import FlightPlanPersistence, get_default_flight_plan


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("无人机航线规划与禁飞区检测系统")
        self.setMinimumSize(1400, 800)

        self._persistence = FlightPlanPersistence()
        self._analyzer = FlightAnalyzer()
        self._current_file: Optional[str] = None
        self._analysis_result: Optional[AnalysisResult] = None

        self._init_ui()
        self._init_toolbar()
        self._init_status_bar()

        default_plan = get_default_flight_plan()
        self._canvas.flight_plan = default_plan

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._canvas = MapCanvas()
        self._canvas.data_changed.connect(self._on_data_changed)
        splitter.addWidget(self._canvas)

        right_panel = self._create_right_panel()
        splitter.addWidget(right_panel)

        splitter.setSizes([900, 500])

        main_layout.addWidget(splitter)

    def _create_right_panel(self) -> QWidget:
        panel = QWidget()
        panel.setMinimumWidth(400)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(5, 5, 5, 5)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)

        scroll_layout.addWidget(self._create_edit_mode_group())
        scroll_layout.addWidget(self._create_battery_group())
        scroll_layout.addWidget(self._create_analysis_group())
        scroll_layout.addWidget(self._create_waypoints_table())
        scroll_layout.addWidget(self._create_result_group())
        scroll_layout.addStretch()

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        return panel

    def _create_edit_mode_group(self) -> QGroupBox:
        group = QGroupBox("编辑模式")
        layout = QVBoxLayout(group)

        btn_layout = QHBoxLayout()

        self._btn_pan = QPushButton("平移/选择")
        self._btn_pan.setCheckable(True)
        self._btn_pan.setChecked(True)
        self._btn_pan.clicked.connect(lambda: self._set_mode(CanvasMode.PAN))

        self._btn_add_waypoint = QPushButton("添加航点")
        self._btn_add_waypoint.setCheckable(True)
        self._btn_add_waypoint.clicked.connect(lambda: self._set_mode(CanvasMode.ADD_WAYPOINT))

        btn_layout.addWidget(self._btn_pan)
        btn_layout.addWidget(self._btn_add_waypoint)

        layout.addLayout(btn_layout)

        btn_layout2 = QHBoxLayout()

        self._btn_draw_nofly = QPushButton("绘制禁飞区")
        self._btn_draw_nofly.setCheckable(True)
        self._btn_draw_nofly.clicked.connect(lambda: self._set_mode(CanvasMode.DRAW_NO_FLY_ZONE))

        self._btn_draw_restricted = QPushButton("绘制限高区")
        self._btn_draw_restricted.setCheckable(True)
        self._btn_draw_restricted.clicked.connect(lambda: self._set_mode(CanvasMode.DRAW_RESTRICTED_ALTITUDE))

        btn_layout2.addWidget(self._btn_draw_nofly)
        btn_layout2.addWidget(self._btn_draw_restricted)

        layout.addLayout(btn_layout2)

        hint_label = QLabel("提示: 绘制多边形时左键添加点，右键完成(至少3个点)")
        hint_label.setWordWrap(True)
        hint_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(hint_label)

        return group

    def _create_battery_group(self) -> QGroupBox:
        group = QGroupBox("电池与飞行参数")
        layout = QVBoxLayout(group)

        grid_layout = QVBoxLayout()

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("电池容量 (mAh):"))
        self._battery_capacity = QDoubleSpinBox()
        self._battery_capacity.setRange(100, 50000)
        self._battery_capacity.setValue(3500)
        self._battery_capacity.setSuffix(" mAh")
        row1.addWidget(self._battery_capacity)
        grid_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("电池电压 (V):"))
        self._battery_voltage = QDoubleSpinBox()
        self._battery_voltage.setRange(1, 50)
        self._battery_voltage.setValue(22.2)
        self._battery_voltage.setDecimals(1)
        self._battery_voltage.setSuffix(" V")
        row2.addWidget(self._battery_voltage)
        grid_layout.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("平均功耗 (W):"))
        self._power_w = QDoubleSpinBox()
        self._power_w.setRange(1, 500)
        self._power_w.setValue(100)
        self._power_w.setSuffix(" W")
        row3.addWidget(self._power_w)
        grid_layout.addLayout(row3)

        row4 = QHBoxLayout()
        row4.addWidget(QLabel("巡航速度 (km/h):"))
        self._flight_speed = QDoubleSpinBox()
        self._flight_speed.setRange(1, 120)
        self._flight_speed.setValue(30)
        self._flight_speed.setSuffix(" km/h")
        row4.addWidget(self._flight_speed)
        grid_layout.addLayout(row4)

        layout.addLayout(grid_layout)

        battery_info = QLabel("可用续航: -- 分钟")
        battery_info.setStyleSheet("color: #2c7a2c; font-weight: bold;")
        self._battery_info_label = battery_info
        self._update_battery_info()

        for spin in [self._battery_capacity, self._battery_voltage, self._power_w]:
            spin.valueChanged.connect(self._update_battery_info)

        layout.addWidget(battery_info)

        return group

    def _create_analysis_group(self) -> QGroupBox:
        group = QGroupBox("航线检测")
        layout = QVBoxLayout(group)

        btn_layout = QHBoxLayout()

        self._btn_analyze = QPushButton("开始检测")
        self._btn_analyze.setMinimumHeight(40)
        self._btn_analyze.setStyleSheet("""
            QPushButton {
                background-color: #4a90d9;
                color: white;
                font-size: 14px;
                font-weight: bold;
                border-radius: 4px;
                padding: 8px;
            }
            QPushButton:hover {
                background-color: #3a7bc8;
            }
        """)
        self._btn_analyze.clicked.connect(self._analyze_flight)

        btn_layout.addWidget(self._btn_analyze)
        layout.addLayout(btn_layout)

        btn_row2 = QHBoxLayout()

        self._btn_clear_waypoints = QPushButton("清除航点")
        self._btn_clear_waypoints.clicked.connect(self._clear_waypoints)
        btn_row2.addWidget(self._btn_clear_waypoints)

        layout.addLayout(btn_row2)

        return group

    def _create_waypoints_table(self) -> QGroupBox:
        group = QGroupBox("航线详情")
        layout = QVBoxLayout(group)

        self._waypoints_table = QTableWidget()
        self._waypoints_table.setColumnCount(5)
        self._waypoints_table.setHorizontalHeaderLabels(
            ["序号", "经度", "纬度", "段距离(km)", "累计(km)"]
        )
        self._waypoints_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._waypoints_table.setMinimumHeight(200)

        layout.addWidget(self._waypoints_table)

        return group

    def _create_result_group(self) -> QGroupBox:
        group = QGroupBox("检测结果")
        layout = QVBoxLayout(group)

        self._result_status = QLabel("等待检测...")
        self._result_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._result_status.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        self._result_status.setStyleSheet("padding: 10px;")
        layout.addWidget(self._result_status)

        self._result_text = QTextEdit()
        self._result_text.setReadOnly(True)
        self._result_text.setMinimumHeight(150)
        layout.addWidget(self._result_text)

        return group

    def _init_toolbar(self):
        toolbar = QToolBar("主工具栏")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        new_action = QAction("新建方案", self)
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.triggered.connect(self._new_plan)
        toolbar.addAction(new_action)

        open_action = QAction("打开方案", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self._open_plan)
        toolbar.addAction(open_action)

        save_action = QAction("保存方案", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self._save_plan)
        toolbar.addAction(save_action)

        save_as_action = QAction("另存为...", self)
        save_as_action.setShortcut(QKeySequence.StandardKey.SaveAs)
        save_as_action.triggered.connect(self._save_plan_as)
        toolbar.addAction(save_as_action)

        toolbar.addSeparator()

        self._mode_toolbar_actions = {}

        pan_action = QAction("平移模式", self)
        pan_action.setCheckable(True)
        pan_action.setChecked(True)
        pan_action.triggered.connect(lambda: self._set_mode(CanvasMode.PAN))
        toolbar.addAction(pan_action)
        self._mode_toolbar_actions[CanvasMode.PAN] = pan_action

        wp_action = QAction("添加航点", self)
        wp_action.setCheckable(True)
        wp_action.triggered.connect(lambda: self._set_mode(CanvasMode.ADD_WAYPOINT))
        toolbar.addAction(wp_action)
        self._mode_toolbar_actions[CanvasMode.ADD_WAYPOINT] = wp_action

    def _init_status_bar(self):
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("就绪")

    def _set_mode(self, mode: CanvasMode):
        self._canvas.set_mode(mode)

        self._btn_pan.setChecked(mode == CanvasMode.PAN)
        self._btn_add_waypoint.setChecked(mode == CanvasMode.ADD_WAYPOINT)
        self._btn_draw_nofly.setChecked(mode == CanvasMode.DRAW_NO_FLY_ZONE)
        self._btn_draw_restricted.setChecked(mode == CanvasMode.DRAW_RESTRICTED_ALTITUDE)

        for canvas_mode, action in self._mode_toolbar_actions.items():
            action.setChecked(canvas_mode == mode)

        mode_names = {
            CanvasMode.PAN: "平移/选择模式",
            CanvasMode.ADD_WAYPOINT: "添加航点模式",
            CanvasMode.DRAW_NO_FLY_ZONE: "绘制禁飞区模式",
            CanvasMode.DRAW_RESTRICTED_ALTITUDE: "绘制限高区模式"
        }
        self._status_bar.showMessage(f"当前: {mode_names.get(mode, '未知')}")

    def _update_battery_info(self):
        try:
            battery = BatteryConfig(
                capacity_mah=self._battery_capacity.value(),
                voltage=self._battery_voltage.value(),
                power_w=self._power_w.value()
            )
            flight_time = battery.flight_time_minutes
            self._battery_info_label.setText(f"可用续航: {flight_time:.1f} 分钟")
        except:
            self._battery_info_label.setText("可用续航: -- 分钟")

    def _on_data_changed(self):
        self._update_waypoints_table()
        self._canvas.clear_conflicts()
        self._analysis_result = None
        self._result_status.setText("等待检测...")
        self._result_status.setStyleSheet("padding: 10px;")
        self._result_text.clear()

    def _update_waypoints_table(self):
        plan = self._canvas.flight_plan
        waypoints = plan.waypoints

        self._waypoints_table.setRowCount(len(waypoints))

        cumulative = 0.0
        from geometry import haversine_distance

        for i, wp in enumerate(waypoints):
            if i > 0:
                prev_wp = waypoints[i - 1]
                dist = haversine_distance(
                    prev_wp.latitude, prev_wp.longitude,
                    wp.latitude, wp.longitude
                )
                cumulative += dist
            else:
                dist = 0.0

            self._waypoints_table.setItem(i, 0, QTableWidgetItem(str(wp.id)))
            self._waypoints_table.setItem(i, 1, QTableWidgetItem(f"{wp.longitude:.6f}"))
            self._waypoints_table.setItem(i, 2, QTableWidgetItem(f"{wp.latitude:.6f}"))
            self._waypoints_table.setItem(i, 3, QTableWidgetItem(f"{dist:.3f}" if i > 0 else "-"))
            self._waypoints_table.setItem(i, 4, QTableWidgetItem(f"{cumulative:.3f}"))

        if self._analysis_result:
            for seg in self._analysis_result.segments:
                if seg.has_conflict:
                    if seg.segment_index < self._waypoints_table.rowCount():
                        for col in range(self._waypoints_table.columnCount()):
                            item = self._waypoints_table.item(seg.segment_index, col)
                            if item:
                                item.setBackground(QColor(255, 200, 200))

    def _analyze_flight(self):
        plan = self._canvas.flight_plan

        if len(plan.waypoints) < 2:
            QMessageBox.warning(self, "提示", "请至少添加2个航点！")
            return

        battery = BatteryConfig(
            capacity_mah=self._battery_capacity.value(),
            voltage=self._battery_voltage.value(),
            power_w=self._power_w.value()
        )

        self._analysis_result = self._analyzer.analyze(
            flight_plan=plan,
            battery_config=battery,
            speed_kmh=self._flight_speed.value()
        )

        conflict_indices = [seg.segment_index for seg in self._analysis_result.conflicts]
        self._canvas.set_conflict_segments(conflict_indices)
        self._update_waypoints_table()
        self._display_result()

    def _display_result(self):
        if not self._analysis_result:
            return

        result = self._analysis_result

        if result.has_conflict:
            status_text = "检测失败 - 存在禁飞区冲突"
            status_style = "padding: 10px; background-color: #ffcccc; color: #cc0000; font-size: 14px;"
        elif not result.battery_sufficient:
            status_text = "检测失败 - 电池续航不足"
            status_style = "padding: 10px; background-color: #ffcc99; color: #cc6600; font-size: 14px;"
        else:
            status_text = "检测通过 - 航线安全"
            status_style = "padding: 10px; background-color: #ccffcc; color: #006600; font-size: 14px;"

        self._result_status.setText(status_text)
        self._result_status.setStyleSheet(status_style)

        lines = []
        lines.append("=" * 40)
        lines.append("航线分析报告")
        lines.append("=" * 40)
        lines.append(f"")
        lines.append(f"总距离: {result.total_distance_km:.3f} km")
        lines.append(f"预计飞行时间: {result.estimated_time_minutes:.1f} 分钟")
        lines.append(f"")
        lines.append(f"电池续航:")
        lines.append(f"  可用: {result.battery_available_minutes:.1f} 分钟")
        lines.append(f"  需要: {result.battery_required_minutes:.1f} 分钟")
        lines.append(f"  状态: {'充足' if result.battery_sufficient else '不足'}")
        lines.append(f"")

        if result.has_conflict:
            lines.append(f"禁飞区冲突 ({len(result.conflicts)} 处):")
            for seg in result.conflicts:
                lines.append(f"  - 航段 S{seg.segment_index + 1}")
                lines.append(f"    冲突区域: {seg.conflict_zone_name}")
            lines.append(f"")
        else:
            lines.append(f"禁飞区检测: 通过 (无冲突)")
            lines.append(f"")

        lines.append(f"航线详情:")
        for seg in result.segments:
            status = "  " if not seg.has_conflict else "**"
            lines.append(f"  {status}S{seg.segment_index + 1}: {seg.start_waypoint.id} -> {seg.end_waypoint.id}")
            lines.append(f"    距离: {seg.distance_km:.3f} km | 累计: {seg.cumulative_distance_km:.3f} km")
            if seg.has_conflict:
                lines.append(f"    *** 冲突: {seg.conflict_zone_name} ***")

        self._result_text.setText("\n".join(lines))

    def _clear_waypoints(self):
        reply = QMessageBox.question(
            self, "确认",
            "确定要清除所有航点吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._canvas.clear_waypoints()
            self._result_status.setText("等待检测...")
            self._result_status.setStyleSheet("padding: 10px;")
            self._result_text.clear()

    def _new_plan(self):
        if self._canvas.flight_plan.waypoints:
            reply = QMessageBox.question(
                self, "确认",
                "当前方案未保存，是否继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        self._canvas.flight_plan = get_default_flight_plan()
        self._current_file = None
        self._analysis_result = None
        self._result_status.setText("等待检测...")
        self._result_status.setStyleSheet("padding: 10px;")
        self._result_text.clear()
        self._status_bar.showMessage("已创建新方案")

    def _open_plan(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "打开航线方案", "",
            "JSON Files (*.json);;All Files (*)"
        )
        if not file_path:
            return

        plan = self._persistence.load(file_path)
        if plan is None:
            QMessageBox.critical(self, "错误", "无法打开文件或格式错误！")
            return

        self._canvas.flight_plan = plan
        self._current_file = file_path
        self._analysis_result = None
        self._result_status.setText("等待检测...")
        self._result_status.setStyleSheet("padding: 10px;")
        self._result_text.clear()
        self._status_bar.showMessage(f"已打开: {file_path}")

    def _save_plan(self):
        if not self._current_file:
            self._save_plan_as()
            return

        if self._persistence.save(self._canvas.flight_plan, self._current_file):
            self._status_bar.showMessage(f"已保存: {self._current_file}")
        else:
            QMessageBox.critical(self, "错误", "保存失败！")

    def _save_plan_as(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存航线方案", "flight_plan.json",
            "JSON Files (*.json);;All Files (*)"
        )
        if not file_path:
            return

        if not file_path.endswith('.json'):
            file_path += '.json'

        if self._persistence.save(self._canvas.flight_plan, file_path):
            self._current_file = file_path
            self._status_bar.showMessage(f"已保存: {file_path}")
        else:
            QMessageBox.critical(self, "错误", "保存失败！")
