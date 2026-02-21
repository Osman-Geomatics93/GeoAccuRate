"""Main dock widget for GeoAccuRate plugin."""

from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtWidgets import QDockWidget, QTabWidget, QVBoxLayout, QWidget


class GeoAccuRateDockWidget(QDockWidget):
    """Primary UI container — docks to the right side of QGIS.

    Contains two tabs for MVP:
      - Samples: sample design and generation
      - Accuracy: categorical accuracy assessment
    """

    closed = pyqtSignal()

    def __init__(self, iface, parent=None):
        super().__init__("GeoAccuRate", parent)
        self.iface = iface
        self._setup_ui()

    def _setup_ui(self):
        """Build the dock widget contents."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)

        self.tab_widget = QTabWidget()

        # Import panels here to avoid circular imports at module level
        from .sample_panel import SamplePanel
        from .accuracy_panel import AccuracyPanel

        self.sample_panel = SamplePanel(self.iface)
        self.accuracy_panel = AccuracyPanel(self.iface)

        self.tab_widget.addTab(self.sample_panel, "Samples")
        self.tab_widget.addTab(self.accuracy_panel, "Accuracy")

        layout.addWidget(self.tab_widget)
        self.setWidget(container)

    def closeEvent(self, event):
        self.closed.emit()
        event.accept()
