"""CRS-aware area calculation for GeoAccuRate.

Computes mapped area per class in hectares from a classified raster.
Requires projected CRS — rejects geographic CRS.

Depends on: GDAL, numpy, core.raster_reader.
"""

from typing import Dict, List, Tuple

from .raster_reader import count_pixels_per_class, get_raster_info


class GeographicCRSError(Exception):
    """Raised when area calculation is attempted with geographic CRS."""
    pass


def compute_class_areas_ha(
    raster_path: str,
    class_labels: List[int] = None,
) -> Tuple[Dict[int, float], Dict[int, int]]:
    """Compute area per class in hectares.

    Args:
        raster_path: Path to classified raster.
        class_labels: If provided, only compute for these classes.

    Returns:
        (area_ha, pixel_counts):
          area_ha: {class_value: area in hectares}
          pixel_counts: {class_value: pixel count}

    Raises:
        GeographicCRSError: If raster CRS is geographic (degrees).
    """
    info = get_raster_info(raster_path)

    if info["crs_is_geographic"]:
        raise GeographicCRSError(
            f"Raster CRS (EPSG:{info['crs_epsg']}) is geographic (degrees). "
            f"Area calculation requires a projected CRS. "
            f"Reproject the raster to a projected CRS (e.g., UTM) "
            f"before running area-weighted analysis."
        )

    # Pixel area in CRS units (typically meters for projected CRS)
    pixel_area_crs_units = info["pixel_size_x"] * info["pixel_size_y"]

    # Convert to hectares (1 ha = 10,000 m²)
    # Assume CRS linear units are meters (most projected CRS)
    pixel_area_ha = pixel_area_crs_units / 10000.0

    # Count pixels per class
    pixel_counts = count_pixels_per_class(raster_path)

    if class_labels is not None:
        pixel_counts = {
            k: v for k, v in pixel_counts.items() if k in class_labels
        }

    area_ha = {
        cls: count * pixel_area_ha
        for cls, count in pixel_counts.items()
    }

    return area_ha, pixel_counts
