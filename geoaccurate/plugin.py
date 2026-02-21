"""Main plugin class for GeoAccuRate."""

import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from .gui.dock_widget import GeoAccuRateDockWidget


class GeoAccuRatePlugin:
    """QGIS plugin implementation for GeoAccuRate.

    Manages the plugin lifecycle: GUI initialization, dock widget
    creation, and cleanup on unload.
    """

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.dock_widget = None
        self.action = None

    def initGui(self):
        """Called by QGIS when the plugin is loaded. Sets up GUI elements."""
        icon_path = os.path.join(
            self.plugin_dir, "resources", "icons", "plugin_icon.png"
        )
        icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()

        self.action = QAction(icon, "GeoAccuRate", self.iface.mainWindow())
        self.action.setCheckable(True)
        self.action.triggered.connect(self._toggle_dock_widget)

        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToRasterMenu("GeoAccuRate", self.action)

        self.dock_widget = GeoAccuRateDockWidget(self.iface)
        self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dock_widget)
        self.dock_widget.hide()
        self.dock_widget.visibilityChanged.connect(self.action.setChecked)

    def unload(self):
        """Called by QGIS when the plugin is unloaded. Cleans up everything."""
        if self.dock_widget is not None:
            self.iface.removeDockWidget(self.dock_widget)
            self.dock_widget.close()
            self.dock_widget = None

        if self.action is not None:
            self.iface.removeToolBarIcon(self.action)
            self.iface.removePluginRasterMenu("GeoAccuRate", self.action)
            self.action = None

    def _toggle_dock_widget(self, checked):
        """Show or hide the dock widget."""
        if self.dock_widget is not None:
            self.dock_widget.setVisible(checked)
