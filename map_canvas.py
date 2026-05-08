from enum import Enum
from typing import List, Optional, Tuple

from PyQt6.QtCore import Qt, QPoint, QPointF, pyqtSignal
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QPolygonF
from PyQt6.QtWidgets import QWidget

from models import FlightPlan, Waypoint, NoFlyZone, RestrictedAltitudeZone, NoFlyReason
from geometry import polygon_centroid


class CanvasMode(Enum):
    PAN = "pan"
    ADD_WAYPOINT = "add_waypoint"
    DRAW_NO_FLY_ZONE = "draw_no_fly_zone"
    DRAW_RESTRICTED_ALTITUDE = "draw_restricted_altitude"


class MapCanvas(QWidget):
    data_changed = pyqtSignal()
    conflict_segments = []

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(600, 400)
        self.setMouseTracking(True)

        self._flight_plan: FlightPlan = FlightPlan()

        self._zoom = 1.0
        self._offset = QPointF(0, 0)

        self._mode = CanvasMode.PAN
        self._is_panning = False
        self._last_pan_pos: Optional[QPoint] = None

        self._drawing_polygon: List[Tuple[float, float]] = []
        self._temp_polygon_point: Optional[Tuple[float, float]] = None

        self._dragging_waypoint_index: Optional[int] = None

        self._conflict_segments: List[int] = []

        self._min_lon = 116.3
        self._max_lon = 116.7
        self._min_lat = 39.8
        self._max_lat = 40.2

    @property
    def flight_plan(self) -> FlightPlan:
        return self._flight_plan

    @flight_plan.setter
    def flight_plan(self, plan: FlightPlan):
        self._flight_plan = plan
        self._fit_to_bounds()
        self.update()

    def set_mode(self, mode: CanvasMode):
        self._mode = mode
        self._drawing_polygon = []
        self._temp_polygon_point = None
        self.update()

    def get_mode(self) -> CanvasMode:
        return self._mode

    def set_conflict_segments(self, segments: List[int]):
        self._conflict_segments = segments
        self.update()

    def clear_conflicts(self):
        self._conflict_segments = []
        self.update()

    def clear_waypoints(self):
        self._flight_plan.waypoints = []
        self._conflict_segments = []
        self.update()
        self.data_changed.emit()

    def _fit_to_bounds(self):
        all_points = []

        for wp in self._flight_plan.waypoints:
            all_points.append((wp.longitude, wp.latitude))

        for zone in self._flight_plan.no_fly_zones:
            all_points.extend(zone.points)

        for zone in self._flight_plan.restricted_altitude_zones:
            all_points.extend(zone.points)

        if not all_points:
            return

        lons = [p[0] for p in all_points]
        lats = [p[1] for p in all_points]

        self._min_lon = min(lons) - 0.02
        self._max_lon = max(lons) + 0.02
        self._min_lat = min(lats) - 0.02
        self._max_lat = max(lats) + 0.02

    def _geo_to_screen(self, lon: float, lat: float) -> QPointF:
        width = self.width()
        height = self.height()

        lon_range = self._max_lon - self._min_lon
        lat_range = self._max_lat - self._min_lat

        center_lon = (self._min_lon + self._max_lon) / 2
        center_lat = (self._min_lat + self._max_lat) / 2

        scale_lon = width / lon_range if lon_range > 0 else 1
        scale_lat = height / lat_range if lat_range > 0 else 1

        scale = min(scale_lon, scale_lat) * self._zoom

        screen_x = width / 2 + (lon - center_lon) * scale + self._offset.x()
        screen_y = height / 2 - (lat - center_lat) * scale + self._offset.y()

        return QPointF(screen_x, screen_y)

    def _screen_to_geo(self, screen_pos: QPointF) -> Tuple[float, float]:
        width = self.width()
        height = self.height()

        lon_range = self._max_lon - self._min_lon
        lat_range = self._max_lat - self._min_lat

        center_lon = (self._min_lon + self._max_lon) / 2
        center_lat = (self._min_lat + self._max_lat) / 2

        scale_lon = width / lon_range if lon_range > 0 else 1
        scale_lat = height / lat_range if lat_range > 0 else 1

        scale = min(scale_lon, scale_lat) * self._zoom

        lon = center_lon + (screen_pos.x() - width / 2 - self._offset.x()) / scale
        lat = center_lat - (screen_pos.y() - height / 2 - self._offset.y()) / scale

        return (lon, lat)

    def _get_waypoint_at_screen(self, screen_pos: QPointF) -> Optional[int]:
        threshold = 15

        for i, wp in enumerate(self._flight_plan.waypoints):
            wp_screen = self._geo_to_screen(wp.longitude, wp.latitude)
            dx = screen_pos.x() - wp_screen.x()
            dy = screen_pos.y() - wp_screen.y()
            dist = (dx ** 2 + dy ** 2) ** 0.5
            if dist < threshold:
                return i

        return None

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta > 0:
            self._zoom *= 1.15
        else:
            self._zoom /= 1.15

        self._zoom = max(0.1, min(self._zoom, 10.0))
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            screen_pos = event.position()

            if self._mode == CanvasMode.PAN:
                wp_index = self._get_waypoint_at_screen(screen_pos)
                if wp_index is not None:
                    self._dragging_waypoint_index = wp_index
                else:
                    self._is_panning = True
                    self._last_pan_pos = event.pos()
                    self.setCursor(Qt.CursorShape.ClosedHandCursor)

            elif self._mode == CanvasMode.ADD_WAYPOINT:
                lon, lat = self._screen_to_geo(screen_pos)
                new_id = len(self._flight_plan.waypoints) + 1
                wp = Waypoint(id=new_id, longitude=lon, latitude=lat)
                self._flight_plan.waypoints.append(wp)
                self.data_changed.emit()
                self.update()

            elif self._mode in [CanvasMode.DRAW_NO_FLY_ZONE, CanvasMode.DRAW_RESTRICTED_ALTITUDE]:
                lon, lat = self._screen_to_geo(screen_pos)
                self._drawing_polygon.append((lon, lat))
                self.update()

        elif event.button() == Qt.MouseButton.RightButton:
            if self._drawing_polygon and len(self._drawing_polygon) >= 3:
                self._finish_drawing_polygon()
            else:
                self._drawing_polygon = []
                self._temp_polygon_point = None
            self.update()

    def mouseMoveEvent(self, event):
        screen_pos = event.position()

        if self._is_panning and self._last_pan_pos is not None:
            delta = event.pos() - self._last_pan_pos
            self._offset += QPointF(delta.x(), delta.y())
            self._last_pan_pos = event.pos()
            self.update()

        elif self._dragging_waypoint_index is not None:
            lon, lat = self._screen_to_geo(screen_pos)
            self._flight_plan.waypoints[self._dragging_waypoint_index].longitude = lon
            self._flight_plan.waypoints[self._dragging_waypoint_index].latitude = lat
            self.data_changed.emit()
            self.update()

        elif self._drawing_polygon:
            lon, lat = self._screen_to_geo(screen_pos)
            self._temp_polygon_point = (lon, lat)
            self.update()

        else:
            if self._mode == CanvasMode.PAN:
                wp_index = self._get_waypoint_at_screen(screen_pos)
                if wp_index is not None:
                    self.setCursor(Qt.CursorShape.PointingHandCursor)
                else:
                    self.setCursor(Qt.CursorShape.ArrowCursor)
            elif self._mode == CanvasMode.ADD_WAYPOINT:
                self.setCursor(Qt.CursorShape.CrossCursor)
            elif self._mode in [CanvasMode.DRAW_NO_FLY_ZONE, CanvasMode.DRAW_RESTRICTED_ALTITUDE]:
                self.setCursor(Qt.CursorShape.CrossCursor)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._is_panning:
                self._is_panning = False
                self._last_pan_pos = None
                self.setCursor(Qt.CursorShape.ArrowCursor)

            if self._dragging_waypoint_index is not None:
                self._dragging_waypoint_index = None

    def _finish_drawing_polygon(self):
        if len(self._drawing_polygon) < 3:
            self._drawing_polygon = []
            self._temp_polygon_point = None
            return

        points = list(self._drawing_polygon)

        if self._mode == CanvasMode.DRAW_NO_FLY_ZONE:
            max_id = max([z.id for z in self._flight_plan.no_fly_zones], default=0) + 1
            zone = NoFlyZone(
                id=max_id,
                name=f"禁飞区{max_id}",
                reason=NoFlyReason.DENSE_POPULATION,
                points=points
            )
            self._flight_plan.no_fly_zones.append(zone)
        elif self._mode == CanvasMode.DRAW_RESTRICTED_ALTITUDE:
            max_id = max([z.id for z in self._flight_plan.restricted_altitude_zones], default=0) + 1
            zone = RestrictedAltitudeZone(
                id=max_id,
                name=f"限高区{max_id}",
                max_altitude=120.0,
                points=points
            )
            self._flight_plan.restricted_altitude_zones.append(zone)

        self._drawing_polygon = []
        self._temp_polygon_point = None
        self.data_changed.emit()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        self._draw_background(painter)
        self._draw_grid(painter)
        self._draw_restricted_altitude_zones(painter)
        self._draw_no_fly_zones(painter)
        self._draw_route(painter)
        self._draw_waypoints(painter)
        self._draw_temp_polygon(painter)

    def _draw_background(self, painter: QPainter):
        painter.fillRect(self.rect(), QColor(240, 248, 255))

    def _draw_grid(self, painter: QPainter):
        width = self.width()
        height = self.height()

        pen = QPen(QColor(200, 200, 220), 0.5)
        painter.setPen(pen)

        grid_spacing = 50

        start_x = int(self._offset.x()) % grid_spacing
        for x in range(start_x, width, grid_spacing):
            painter.drawLine(x, 0, x, height)

        start_y = int(self._offset.y()) % grid_spacing
        for y in range(start_y, height, grid_spacing):
            painter.drawLine(0, y, width, y)

        painter.setPen(QPen(QColor(150, 150, 170), 1))
        painter.drawRect(0, 0, width - 1, height - 1)

    def _draw_polygon_zone(self, painter: QPainter, points: List[Tuple[float, float]], fill_color: QColor, edge_color: QColor):
        if len(points) < 3:
            return

        screen_points = []
        for lon, lat in points:
            screen_points.append(self._geo_to_screen(lon, lat))

        polygon = QPolygonF(screen_points)

        painter.setBrush(QBrush(fill_color))
        painter.setPen(QPen(edge_color, 2))
        painter.drawPolygon(polygon)

    def _draw_no_fly_zones(self, painter: QPainter):
        fill_color = QColor(255, 0, 0, 80)
        edge_color = QColor(200, 0, 0)

        for zone in self._flight_plan.no_fly_zones:
            self._draw_polygon_zone(painter, zone.points, fill_color, edge_color)

            center = polygon_centroid(zone.points)
            center_screen = self._geo_to_screen(center[0], center[1])

            label_text = f"{zone.name}\n({zone.reason})"
            font = QFont("Microsoft YaHei", 9)
            painter.setFont(font)

            metrics = painter.fontMetrics()
            lines = label_text.split('\n')
            text_width = max(metrics.horizontalAdvance(line) for line in lines)
            text_height = metrics.height() * len(lines)

            rect_x = int(center_screen.x() - text_width / 2 - 4)
            rect_y = int(center_screen.y() - text_height / 2 - 4)

            painter.setBrush(QBrush(QColor(255, 255, 255, 230)))
            painter.setPen(QPen(QColor(200, 0, 0), 1))
            painter.drawRect(rect_x, rect_y, text_width + 8, text_height + 8)

            painter.setPen(QColor(180, 0, 0))
            for i, line in enumerate(lines):
                line_width = metrics.horizontalAdvance(line)
                painter.drawText(
                    int(center_screen.x() - line_width / 2),
                    int(center_screen.y() - text_height / 2 + metrics.ascent() + i * metrics.height()),
                    line
                )

    def _draw_restricted_altitude_zones(self, painter: QPainter):
        fill_color = QColor(255, 255, 0, 80)
        edge_color = QColor(200, 200, 0)

        for zone in self._flight_plan.restricted_altitude_zones:
            self._draw_polygon_zone(painter, zone.points, fill_color, edge_color)

            center = polygon_centroid(zone.points)
            center_screen = self._geo_to_screen(center[0], center[1])

            label_text = f"{zone.name}\n限高:{zone.max_altitude}m"
            font = QFont("Microsoft YaHei", 9)
            painter.setFont(font)

            metrics = painter.fontMetrics()
            lines = label_text.split('\n')
            text_width = max(metrics.horizontalAdvance(line) for line in lines)
            text_height = metrics.height() * len(lines)

            rect_x = int(center_screen.x() - text_width / 2 - 4)
            rect_y = int(center_screen.y() - text_height / 2 - 4)

            painter.setBrush(QBrush(QColor(255, 255, 255, 230)))
            painter.setPen(QPen(QColor(200, 150, 0), 1))
            painter.drawRect(rect_x, rect_y, text_width + 8, text_height + 8)

            painter.setPen(QColor(150, 100, 0))
            for i, line in enumerate(lines):
                line_width = metrics.horizontalAdvance(line)
                painter.drawText(
                    int(center_screen.x() - line_width / 2),
                    int(center_screen.y() - text_height / 2 + metrics.ascent() + i * metrics.height()),
                    line
                )

    def _draw_route(self, painter: QPainter):
        waypoints = self._flight_plan.waypoints
        if len(waypoints) < 2:
            return

        for i in range(len(waypoints) - 1):
            wp1 = waypoints[i]
            wp2 = waypoints[i + 1]

            p1 = self._geo_to_screen(wp1.longitude, wp1.latitude)
            p2 = self._geo_to_screen(wp2.longitude, wp2.latitude)

            if i in self._conflict_segments:
                pen = QPen(QColor(255, 0, 0), 4)
                pen.setStyle(Qt.PenStyle.DashLine)
            else:
                pen = QPen(QColor(70, 130, 180), 3)

            painter.setPen(pen)
            painter.drawLine(p1, p2)

            mid_x = (p1.x() + p2.x()) / 2
            mid_y = (p1.y() + p2.y()) / 2

            font = QFont("Microsoft YaHei", 8)
            painter.setFont(font)

            label_text = f"S{i+1}"
            metrics = painter.fontMetrics()
            text_width = metrics.horizontalAdvance(label_text)
            text_height = metrics.height()

            painter.setBrush(QBrush(QColor(255, 255, 255, 220)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(
                int(mid_x - text_width / 2 - 2),
                int(mid_y - text_height / 2 - 2),
                text_width + 4,
                text_height + 4
            )

            painter.setPen(QColor(70, 130, 180))
            painter.drawText(
                int(mid_x - text_width / 2),
                int(mid_y - text_height / 2 + metrics.ascent()),
                label_text
            )

    def _draw_waypoints(self, painter: QPainter):
        waypoints = self._flight_plan.waypoints
        if not waypoints:
            return

        font = QFont("Microsoft YaHei", 10, QFont.Weight.Bold)
        painter.setFont(font)

        for i, wp in enumerate(waypoints):
            screen_pos = self._geo_to_screen(wp.longitude, wp.latitude)

            painter.setBrush(QBrush(QColor(255, 255, 255)))
            painter.setPen(QPen(QColor(70, 130, 180), 3))
            painter.drawEllipse(screen_pos, 12, 12)

            painter.setBrush(QBrush(QColor(70, 130, 180)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(screen_pos, 6, 6)

            label_text = str(wp.id)
            metrics = painter.fontMetrics()
            text_width = metrics.horizontalAdvance(label_text)
            text_height = metrics.height()

            painter.setPen(QColor(50, 50, 50))
            painter.drawText(
                int(screen_pos.x() - text_width / 2),
                int(screen_pos.y() - 20),
                label_text
            )

            coord_text = f"{wp.longitude:.4f}, {wp.latitude:.4f}"
            small_font = QFont("Microsoft YaHei", 8)
            painter.setFont(small_font)
            coord_metrics = painter.fontMetrics()
            coord_width = coord_metrics.horizontalAdvance(coord_text)

            painter.setPen(QColor(100, 100, 100))
            painter.drawText(
                int(screen_pos.x() - coord_width / 2),
                int(screen_pos.y() + 28),
                coord_text
            )

            painter.setFont(font)

    def _draw_temp_polygon(self, painter: QPainter):
        if not self._drawing_polygon:
            return

        points = list(self._drawing_polygon)
        if self._temp_polygon_point:
            points.append(self._temp_polygon_point)

        if self._mode == CanvasMode.DRAW_NO_FLY_ZONE:
            fill_color = QColor(255, 0, 0, 50)
            edge_color = QColor(255, 0, 0)
        else:
            fill_color = QColor(255, 255, 0, 50)
            edge_color = QColor(200, 200, 0)

        screen_points = [self._geo_to_screen(lon, lat) for lon, lat in points]

        if len(screen_points) >= 2:
            painter.setPen(QPen(edge_color, 2, Qt.PenStyle.DashLine))
            painter.setBrush(QBrush(fill_color))

            if len(screen_points) >= 3:
                polygon = QPolygonF(screen_points)
                painter.drawPolygon(polygon)
            else:
                painter.drawLine(screen_points[0], screen_points[1])

        for point in screen_points:
            painter.setBrush(QBrush(edge_color))
            painter.setPen(QPen(edge_color, 2))
            painter.drawEllipse(point, 6, 6)
