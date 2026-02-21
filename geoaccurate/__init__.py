"""
GeoAccuRate — Accuracy Assessment Done Right

A QGIS plugin for rigorous accuracy assessment of classified maps,
implementing Olofsson et al. (2014) area-weighted estimation,
Pontius & Millones (2011) disagreement metrics, and publication-ready
PDF reporting.
"""


def classFactory(iface):
    """QGIS plugin entry point. Called by QGIS to load the plugin.

    Args:
        iface: QgisInterface reference providing access to the QGIS GUI.

    Returns:
        GeoAccuRatePlugin instance.
    """
    from .plugin import GeoAccuRatePlugin
    return GeoAccuRatePlugin(iface)
