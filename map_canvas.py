from __future__ import annotations

import math
from typing import List, Optional, Tuple

from PyQt6.QtCore import Qt, QPointF, pyqtSignal
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPen,
    QPolygonF,
    QPainter,
    QWheelEvent,
    QMouseEvent,
)
from PyQt6.QtWidgets import QWidget

from models import NoFlyZone, AltitudeZone, Waypoint


class MapCanvas(QWidget):
    mode_changed = pyqtSignal(str)
    route_changed = pyqtSignal()
    zone_finished = pyqtSignal()

    MODE_WAYPOINT = "waypoint"
    MODE_NOFLY = "nofly"
    MODE_ALTITUDE = "altitude"
    MODE_SELECT = "select"

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumSize(600, 500)
        self.setMouseTracking(True)

        self.center_lon = 116.40
        self.center_lat = 39.95
        self.scale = 8000.0

        self.waypoints: List[Waypoint] = []
        self.no_fly_zones: List[NoFlyZone] = []
        self.altitude_zones: List[AltitudeZone] = []

        self.mode = self.MODE_WAYPOINT
        self._drawing_polygon: List[List[float]] = []
        self._dragging_wp_idx: Optional[int] = None
        self._panning = False
        self._pan_start = QPointF()
        self._pan_center_lon = 0.0
        self._pan_center_lat = 0.0

        self.conflict_segments: List[int] = []

        self._hover_pos: Optional[QPointF] = None

    def set_mode(self, mode: str):
        if self._drawing_polygon:
            self._drawing_polygon.clear()
        self.mode = mode
        self.mode_changed.emit(mode)
        self.update()

    def lonlat_to_pixel(self, lon: float, lat: float) -> QPointF:
        w = self.width()
        h = self.height()
        px = w / 2 + (lon - self.center_lon) * self.scale
        py = h / 2 - (lat - self.center_lat) * self.scale
        return QPointF(px, py)

    def pixel_to_lonlat(self, px: float, py: float) -> Tuple[float, float]:
        w = self.width()
        h = self.height()
        lon = self.center_lon + (px - w / 2) / self.scale
        lat = self.center_lat - (py - h / 2) / self.scale
        return lon, lat

    def _find_waypoint_at(self, pos: QPointF, radius: float = 12.0) -> Optional[int]:
        for i, wp in enumerate(self.waypoints):
            pp = self.lonlat_to_pixel(wp.lon, wp.lat)
            dx = pp.x() - pos.x()
            dy = pp.y() - pos.y()
            if dx * dx + dy * dy <= radius * radius:
                return i
        return None

    def wheelEvent(self, event: QWheelEvent):
        factor = 1.15 if event.angleDelta().y() > 0 else 1.0 / 1.15
        mouse_pos = event.position()
        lon_before, lat_before = self.pixel_to_lonlat(mouse_pos.x(), mouse_pos.y())
        self.scale *= factor
        self.center_lon = lon_before - (mouse_pos.x() - self.width() / 2) / self.scale
        self.center_lat = lat_before + (mouse_pos.y() - self.height() / 2) / self.scale
        self.update()

    def mousePressEvent(self, event: QMouseEvent):
        pos = event.position()
        if event.button() == Qt.MouseButton.RightButton:
            self._panning = True
            self._pan_start = pos
            self._pan_center_lon = self.center_lon
            self._pan_center_lat = self.center_lat
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return

        if event.button() != Qt.MouseButton.LeftButton:
            return

        lon, lat = self.pixel_to_lonlat(pos.x(), pos.y())

        if self.mode == self.MODE_WAYPOINT or self.mode == self.MODE_SELECT:
            idx = self._find_waypoint_at(pos)
            if idx is not None:
                self._dragging_wp_idx = idx
                self.setCursor(Qt.CursorShape.SizeAllCursor)
                return
            if self.mode == self.MODE_WAYPOINT:
                wp = Waypoint(lon=lon, lat=lat, index=len(self.waypoints))
                self.waypoints.append(wp)
                self._reindex_waypoints()
                self.route_changed.emit()
                self.update()

        elif self.mode == self.MODE_NOFLY:
            self._drawing_polygon.append([lon, lat])
            self.update()

        elif self.mode == self.MODE_ALTITUDE:
            self._drawing_polygon.append([lon, lat])
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent):
        pos = event.position()
        self._hover_pos = pos

        if self._panning:
            dx = pos.x() - self._pan_start.x()
            dy = pos.y() - self._pan_start.y()
            self.center_lon = self._pan_center_lon - dx / self.scale
            self.center_lat = self._pan_center_lat + dy / self.scale
            self.update()
            return

        if self._dragging_wp_idx is not None:
            lon, lat = self.pixel_to_lonlat(pos.x(), pos.y())
            wp = self.waypoints[self._dragging_wp_idx]
            wp.lon = lon
            wp.lat = lat
            self.route_changed.emit()
            self.update()
            return

        if self._drawing_polygon:
            self.update()

        idx = self._find_waypoint_at(pos)
        if idx is not None:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.setCursor(Qt.CursorShape.CrossCursor)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.RightButton:
            self._panning = False
            self.setCursor(Qt.CursorShape.CrossCursor)
            return
        if event.button() == Qt.MouseButton.LeftButton and self._dragging_wp_idx is not None:
            self._dragging_wp_idx = None
            self.setCursor(Qt.CursorShape.CrossCursor)
            self.route_changed.emit()

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self.mode in (self.MODE_NOFLY, self.MODE_ALTITUDE) and len(self._drawing_polygon) >= 3:
            self._finish_polygon()
            self.update()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Return and len(self._drawing_polygon) >= 3:
            self._finish_polygon()
            self.update()
        elif event.key() == Qt.Key.Key_Escape:
            self._drawing_polygon.clear()
            self.update()
        elif event.key() == Qt.Key.Key_Delete:
            if self._dragging_wp_idx is not None:
                self.waypoints.pop(self._dragging_wp_idx)
                self._dragging_wp_idx = None
                self._reindex_waypoints()
                self.route_changed.emit()
                self.update()

    def _finish_polygon(self):
        if self.mode == self.MODE_NOFLY:
            zone = NoFlyZone(
                name=f"禁飞区{len(self.no_fly_zones) + 1}",
                reason="机场",
                points=list(self._drawing_polygon),
            )
            self.no_fly_zones.append(zone)
        elif self.mode == self.MODE_ALTITUDE:
            zone = AltitudeZone(
                name=f"限高区{len(self.altitude_zones) + 1}",
                altitude_limit=120.0,
                points=list(self._drawing_polygon),
            )
            self.altitude_zones.append(zone)
        self._drawing_polygon.clear()
        self.zone_finished.emit()

    def _reindex_waypoints(self):
        for i, wp in enumerate(self.waypoints):
            wp.index = i

    def delete_waypoint(self, index: int):
        if 0 <= index < len(self.waypoints):
            self.waypoints.pop(index)
            self._reindex_waypoints()
            self.route_changed.emit()
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._draw_background(painter)
        self._draw_grid(painter)
        self._draw_zones(painter)
        self._draw_drawing_polygon(painter)
        self._draw_route(painter)
        self._draw_waypoints(painter)
        self._draw_crosshair(painter)
        painter.end()

    def _draw_background(self, painter: QPainter):
        painter.fillRect(self.rect(), QColor(30, 35, 45))

    def _draw_grid(self, painter: QPainter):
        pen = QPen(QColor(50, 55, 70), 1, Qt.PenStyle.DotLine)
        painter.setPen(pen)

        left_lon, top_lat = self.pixel_to_lonlat(0, 0)
        right_lon, bottom_lat = self.pixel_to_lonlat(self.width(), self.height())

        grid_step = self._calc_grid_step()
        start_lon = math.floor(left_lon / grid_step) * grid_step
        start_lat = math.floor(bottom_lat / grid_step) * grid_step

        lon = start_lon
        while lon <= right_lon:
            p1 = self.lonlat_to_pixel(lon, top_lat)
            p2 = self.lonlat_to_pixel(lon, bottom_lat)
            painter.drawLine(int(p1.x()), int(p1.y()), int(p2.x()), int(p2.y()))
            lon += grid_step

        lat = start_lat
        while lat <= top_lat:
            p1 = self.lonlat_to_pixel(left_lon, lat)
            p2 = self.lonlat_to_pixel(right_lon, lat)
            painter.drawLine(int(p1.x()), int(p1.y()), int(p2.x()), int(p2.y()))
            lat += grid_step

        label_pen = QPen(QColor(120, 130, 150))
        painter.setPen(label_pen)
        font = QFont("Consolas", 8)
        painter.setFont(font)
        lon = start_lon
        while lon <= right_lon:
            p = self.lonlat_to_pixel(lon, bottom_lat)
            painter.drawText(int(p.x()) + 2, int(p.y()) - 4, f"{lon:.4f}°E")
            lon += grid_step
        lat = start_lat
        while lat <= top_lat:
            p = self.lonlat_to_pixel(left_lon, lat)
            painter.drawText(int(p.x()) + 2, int(p.y()) - 4, f"{lat:.4f}°N")
            lat += grid_step

    def _calc_grid_step(self) -> float:
        pixels_per_degree = self.scale
        if pixels_per_degree > 50000:
            return 0.001
        elif pixels_per_degree > 10000:
            return 0.005
        elif pixels_per_degree > 3000:
            return 0.01
        elif pixels_per_degree > 800:
            return 0.05
        else:
            return 0.1

    def _draw_zones(self, painter: QPainter):
        for zone in self.no_fly_zones:
            self._draw_polygon_zone(painter, zone.points, QColor(220, 40, 40, 60), QColor(220, 40, 40, 180), zone.name + f" ({zone.reason})")

        for zone in self.altitude_zones:
            self._draw_polygon_zone(painter, zone.points, QColor(230, 200, 40, 50), QColor(230, 200, 40, 180), zone.name + f" (限高{zone.altitude_limit:.0f}m)")

    def _draw_polygon_zone(self, painter: QPainter, points: List[List[float]], fill: QColor, stroke: QColor, label: str):
        if len(points) < 3:
            return
        poly = QPolygonF()
        cx, cy = 0.0, 0.0
        for p in points:
            pp = self.lonlat_to_pixel(p[0], p[1])
            poly.append(pp)
            cx += pp.x()
            cy += pp.y()
        cx /= len(points)
        cy /= len(points)

        painter.setBrush(QBrush(fill))
        painter.setPen(QPen(stroke, 2))
        painter.drawPolygon(poly)

        painter.setPen(QPen(stroke))
        font = QFont("Microsoft YaHei", 9, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(int(cx) - 60, int(cy) - 6, 120, 20, Qt.AlignmentFlag.AlignCenter, label)

    def _draw_drawing_polygon(self, painter: QPainter):
        if not self._drawing_polygon:
            return
        color = QColor(220, 40, 40, 150) if self.mode == self.MODE_NOFLY else QColor(230, 200, 40, 150)
        pen = QPen(color, 2, Qt.PenStyle.DashLine)
        painter.setPen(pen)

        pts = []
        for p in self._drawing_polygon:
            pts.append(self.lonlat_to_pixel(p[0], p[1]))

        if self._hover_pos and len(pts) > 0:
            pts.append(self._hover_pos)

        for i in range(len(pts) - 1):
            painter.drawLine(int(pts[i].x()), int(pts[i].y()), int(pts[i + 1].x()), int(pts[i + 1].y()))

        painter.setBrush(QBrush(color))
        for pt in pts:
            painter.drawEllipse(pt, 4, 4)

    def _draw_route(self, painter: QPainter):
        if len(self.waypoints) < 2:
            return
        for i in range(len(self.waypoints) - 1):
            wp1 = self.waypoints[i]
            wp2 = self.waypoints[i + 1]
            p1 = self.lonlat_to_pixel(wp1.lon, wp1.lat)
            p2 = self.lonlat_to_pixel(wp2.lon, wp2.lat)

            if i in self.conflict_segments:
                pen = QPen(QColor(255, 50, 50), 3)
            else:
                pen = QPen(QColor(0, 200, 255), 2.5)
            painter.setPen(pen)
            painter.drawLine(int(p1.x()), int(p1.y()), int(p2.x()), int(p2.y()))

    def _draw_waypoints(self, painter: QPainter):
        for i, wp in enumerate(self.waypoints):
            p = self.lonlat_to_pixel(wp.lon, wp.lat)

            is_conflict = False
            if i < len(self.waypoints) - 1 and i in self.conflict_segments:
                is_conflict = True
            if i > 0 and (i - 1) in self.conflict_segments:
                is_conflict = True

            outer_color = QColor(255, 60, 60) if is_conflict else QColor(0, 220, 255)
            inner_color = QColor(255, 120, 120) if is_conflict else QColor(100, 240, 255)

            painter.setPen(QPen(outer_color, 2))
            painter.setBrush(QBrush(inner_color))
            painter.drawEllipse(p, 8, 8)

            painter.setPen(QPen(QColor(255, 255, 255)))
            font = QFont("Consolas", 8, QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(int(p.x()) - 4, int(p.y()) + 4, str(i))

            label = f"WP{i}\n{wp.lon:.5f}, {wp.lat:.5f}"
            painter.setPen(QPen(QColor(200, 210, 230)))
            font2 = QFont("Consolas", 7)
            painter.setFont(font2)
            painter.drawText(int(p.x()) + 12, int(p.y()) - 8, label)

    def _draw_crosshair(self, painter: QPainter):
        if self._hover_pos is None:
            return
        lon, lat = self.pixel_to_lonlat(self._hover_pos.x(), self._hover_pos.y())
        pen = QPen(QColor(100, 110, 130, 100), 1, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawLine(int(self._hover_pos.x()), 0, int(self._hover_pos.x()), self.height())
        painter.drawLine(0, int(self._hover_pos.y()), self.width(), int(self._hover_pos.y()))

        painter.setPen(QPen(QColor(180, 190, 210)))
        font = QFont("Consolas", 8)
        painter.setFont(font)
        painter.drawText(8, self.height() - 8, f"Cursor: {lon:.6f}°E  {lat:.6f}°N")
