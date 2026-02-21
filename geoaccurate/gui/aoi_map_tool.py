"""Map tools for drawing Areas of Interest on the QGIS canvas.

Rectangle: click-drag-release.
Circle: click center, drag radius, release.
Polygon: left-click to add vertices, right-click to finish.

Each tool draws one shape per activation, emits a signal with the resulting
QgsGeometry, then auto-deactivates so the previous map tool is restored.
"""

from math import sqrt

from qgis.PyQt.QtCore import pyqtSignal, Qt
from qgis.PyQt.QtGui import QColor
from qgis.core import QgsGeometry, QgsPointXY, QgsRectangle, QgsWkbTypes
from qgis.gui import QgsMapTool, QgsRubberBand


class RectangleDrawTool(QgsMapTool):
    """Draw a rectangle on the map canvas by click-drag-release."""

    shapeDrawn = pyqtSignal(QgsGeometry, str)

    def __init__(self, canvas):
        super().__init__(canvas)
        self._start_point = None
        self._rubber_band = None
        self.setCursor(Qt.CrossCursor)

    def canvasPressEvent(self, event):
        self._start_point = self.toMapCoordinates(event.pos())
        self._rubber_band = QgsRubberBand(self.canvas(), QgsWkbTypes.PolygonGeometry)
        self._rubber_band.setColor(QColor(0, 120, 215, 80))
        self._rubber_band.setStrokeColor(QColor(0, 120, 215))
        self._rubber_band.setWidth(2)

    def canvasMoveEvent(self, event):
        if self._start_point is None or self._rubber_band is None:
            return
        end = self.toMapCoordinates(event.pos())
        rect = QgsRectangle(self._start_point, end)
        self._rubber_band.setToGeometry(QgsGeometry.fromRect(rect), None)

    def canvasReleaseEvent(self, event):
        if self._start_point is None:
            return
        end = self.toMapCoordinates(event.pos())
        rect = QgsRectangle(self._start_point, end)

        if self._rubber_band is not None:
            self.canvas().scene().removeItem(self._rubber_band)
            self._rubber_band = None

        if rect.width() < 1e-10 and rect.height() < 1e-10:
            self._start_point = None
            return

        geom = QgsGeometry.fromRect(rect)
        self._start_point = None
        self.shapeDrawn.emit(geom, "Rect")

    def deactivate(self):
        if self._rubber_band is not None:
            self.canvas().scene().removeItem(self._rubber_band)
            self._rubber_band = None
        self._start_point = None
        super().deactivate()


class CircleDrawTool(QgsMapTool):
    """Draw a circle on the map canvas by click (center) + drag (radius) + release."""

    shapeDrawn = pyqtSignal(QgsGeometry, str)

    def __init__(self, canvas):
        super().__init__(canvas)
        self._center = None
        self._rubber_band = None
        self.setCursor(Qt.CrossCursor)

    def canvasPressEvent(self, event):
        self._center = self.toMapCoordinates(event.pos())
        self._rubber_band = QgsRubberBand(self.canvas(), QgsWkbTypes.PolygonGeometry)
        self._rubber_band.setColor(QColor(0, 120, 215, 80))
        self._rubber_band.setStrokeColor(QColor(0, 120, 215))
        self._rubber_band.setWidth(2)

    def canvasMoveEvent(self, event):
        if self._center is None or self._rubber_band is None:
            return
        edge = self.toMapCoordinates(event.pos())
        radius = sqrt(
            (edge.x() - self._center.x()) ** 2
            + (edge.y() - self._center.y()) ** 2
        )
        if radius < 1e-10:
            return
        circle_geom = QgsGeometry.fromPointXY(self._center).buffer(radius, 36)
        self._rubber_band.setToGeometry(circle_geom, None)

    def canvasReleaseEvent(self, event):
        if self._center is None:
            return
        edge = self.toMapCoordinates(event.pos())
        radius = sqrt(
            (edge.x() - self._center.x()) ** 2
            + (edge.y() - self._center.y()) ** 2
        )

        if self._rubber_band is not None:
            self.canvas().scene().removeItem(self._rubber_band)
            self._rubber_band = None

        if radius < 1e-10:
            self._center = None
            return

        geom = QgsGeometry.fromPointXY(self._center).buffer(radius, 36)
        self._center = None
        self.shapeDrawn.emit(geom, "Circle")

    def deactivate(self):
        if self._rubber_band is not None:
            self.canvas().scene().removeItem(self._rubber_band)
            self._rubber_band = None
        self._center = None
        super().deactivate()


class PolygonDrawTool(QgsMapTool):
    """Draw a free polygon: left-click to add vertices, right-click to finish."""

    shapeDrawn = pyqtSignal(QgsGeometry, str)

    def __init__(self, canvas):
        super().__init__(canvas)
        self._vertices = []
        self._rubber_band = None
        self.setCursor(Qt.CrossCursor)

    def _ensure_rubber_band(self):
        if self._rubber_band is None:
            self._rubber_band = QgsRubberBand(
                self.canvas(), QgsWkbTypes.PolygonGeometry
            )
            self._rubber_band.setColor(QColor(0, 120, 215, 80))
            self._rubber_band.setStrokeColor(QColor(0, 120, 215))
            self._rubber_band.setWidth(2)

    def canvasPressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pt = self.toMapCoordinates(event.pos())
            self._vertices.append(pt)
            self._ensure_rubber_band()
            self._update_preview(pt)

        elif event.button() == Qt.RightButton:
            self._finish_polygon()

    def canvasMoveEvent(self, event):
        if not self._vertices or self._rubber_band is None:
            return
        cursor = self.toMapCoordinates(event.pos())
        self._update_preview(cursor)

    def _update_preview(self, cursor_point):
        """Redraw the rubber band showing current polygon + line to cursor."""
        if len(self._vertices) < 1:
            return
        ring = [QgsPointXY(v) for v in self._vertices] + [cursor_point]
        # Close the ring for polygon preview
        ring.append(ring[0])
        geom = QgsGeometry.fromPolygonXY([ring])
        self._rubber_band.setToGeometry(geom, None)

    def _finish_polygon(self):
        """Complete the polygon and emit the signal."""
        if self._rubber_band is not None:
            self.canvas().scene().removeItem(self._rubber_band)
            self._rubber_band = None

        if len(self._vertices) < 3:
            self._vertices.clear()
            return

        ring = [QgsPointXY(v) for v in self._vertices]
        ring.append(ring[0])  # close the ring
        geom = QgsGeometry.fromPolygonXY([ring])

        self._vertices.clear()
        self.shapeDrawn.emit(geom, "Polygon")

    def deactivate(self):
        if self._rubber_band is not None:
            self.canvas().scene().removeItem(self._rubber_band)
            self._rubber_band = None
        self._vertices.clear()
        super().deactivate()
