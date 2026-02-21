"""Raster reading utilities for GeoAccuRate.

Handles windowed reading, pixel extraction at points, and class
pixel counting. Never loads a full raster into memory.

Depends on: GDAL, numpy.
"""

from typing import Dict, Optional, Tuple

import numpy as np

from osgeo import gdal, osr

# Suppress GDAL error popups — log instead
gdal.UseExceptions()


def get_raster_info(raster_path: str) -> dict:
    """Read basic raster metadata without loading pixel data.

    Returns:
        dict with keys: width, height, crs_epsg, pixel_size_x, pixel_size_y,
        extent (xmin, ymin, xmax, ymax), nodata, n_bands, dtype
    """
    ds = gdal.Open(raster_path, gdal.GA_ReadOnly)
    if ds is None:
        raise FileNotFoundError(f"Cannot open raster: {raster_path}")

    gt = ds.GetGeoTransform()
    band = ds.GetRasterBand(1)
    srs = osr.SpatialReference()
    srs.ImportFromWkt(ds.GetProjection())

    try:
        epsg = int(srs.GetAuthorityCode(None))
    except (TypeError, ValueError):
        epsg = 0  # Unknown CRS

    info = {
        "width": ds.RasterXSize,
        "height": ds.RasterYSize,
        "crs_epsg": epsg,
        "crs_is_geographic": bool(srs.IsGeographic()),
        "pixel_size_x": abs(gt[1]),
        "pixel_size_y": abs(gt[5]),
        "extent": (
            gt[0],                              # xmin
            gt[3] + gt[5] * ds.RasterYSize,     # ymin
            gt[0] + gt[1] * ds.RasterXSize,     # xmax
            gt[3],                              # ymax
        ),
        "nodata": band.GetNoDataValue(),
        "n_bands": ds.RasterCount,
        "dtype": gdal.GetDataTypeName(band.DataType),
        "geotransform": gt,
    }

    ds = None  # close
    return info


def extract_values_at_points(
    raster_path: str,
    points_xy: np.ndarray,
    band_index: int = 1,
    nodata_value: Optional[float] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """Extract raster values at point locations.

    Uses single-pixel GDAL reads — O(n_points) memory.

    Args:
        raster_path: Path to raster file.
        points_xy: Nx2 array of (x, y) coordinates in raster CRS.
        band_index: Band to read (1-based).
        nodata_value: Override nodata. If None, read from raster metadata.

    Returns:
        (values, valid_mask): values array and boolean mask (True=valid).
    """
    ds = gdal.Open(raster_path, gdal.GA_ReadOnly)
    if ds is None:
        raise FileNotFoundError(f"Cannot open raster: {raster_path}")

    band = ds.GetRasterBand(band_index)
    gt = ds.GetGeoTransform()

    if nodata_value is None:
        nodata_value = band.GetNoDataValue()

    n = len(points_xy)
    values = np.full(n, np.nan, dtype=np.float64)
    valid = np.zeros(n, dtype=bool)

    inv_gt = gdal.InvGeoTransform(gt)

    for i in range(n):
        x, y = points_xy[i, 0], points_xy[i, 1]

        # World to pixel
        px = int(inv_gt[0] + inv_gt[1] * x + inv_gt[2] * y)
        py = int(inv_gt[3] + inv_gt[4] * x + inv_gt[5] * y)

        if 0 <= px < ds.RasterXSize and 0 <= py < ds.RasterYSize:
            val = band.ReadAsArray(px, py, 1, 1)
            if val is not None:
                v = float(val[0, 0])
                if nodata_value is not None and v == nodata_value:
                    continue
                values[i] = v
                valid[i] = True

    ds = None
    return values, valid


def count_pixels_per_class(
    raster_path: str,
    band_index: int = 1,
    block_size: int = 256,
) -> Dict[int, int]:
    """Count pixels per unique value using block-by-block reading.

    Memory: O(block_size^2) — never loads full raster.

    Args:
        raster_path: Path to classified raster.
        band_index: Band to read (1-based).
        block_size: Read block size in pixels.

    Returns:
        {class_value: pixel_count}
    """
    ds = gdal.Open(raster_path, gdal.GA_ReadOnly)
    if ds is None:
        raise FileNotFoundError(f"Cannot open raster: {raster_path}")

    band = ds.GetRasterBand(band_index)
    nodata = band.GetNoDataValue()
    width = ds.RasterXSize
    height = ds.RasterYSize

    counts: Dict[int, int] = {}

    for y_off in range(0, height, block_size):
        y_size = min(block_size, height - y_off)
        for x_off in range(0, width, block_size):
            x_size = min(block_size, width - x_off)
            block = band.ReadAsArray(x_off, y_off, x_size, y_size)
            if block is None:
                continue

            unique, cnts = np.unique(block, return_counts=True)
            for val, cnt in zip(unique, cnts):
                val_int = int(val)
                if nodata is not None and val_int == int(nodata):
                    continue
                counts[val_int] = counts.get(val_int, 0) + int(cnt)

    ds = None
    return counts


def extract_candidate_pixels(
    raster_path: str,
    target_class: int,
    band_index: int = 1,
    subsample_rate: float = 1.0,
    seed: int = 42,
    block_size: int = 256,
) -> np.ndarray:
    """Extract pixel center coordinates for a given class value.

    For large rasters, use subsample_rate < 1.0 to randomly keep only
    a fraction of candidates (reduces memory usage).

    Args:
        raster_path: Path to classified raster.
        target_class: Class value to extract.
        band_index: Band to read.
        subsample_rate: Fraction of candidates to keep (0-1). 1.0 = all.
        seed: Random seed for subsampling.
        block_size: Read block size.

    Returns:
        Nx2 array of (x, y) coordinates (pixel centers in map CRS).
    """
    ds = gdal.Open(raster_path, gdal.GA_ReadOnly)
    if ds is None:
        raise FileNotFoundError(f"Cannot open raster: {raster_path}")

    band = ds.GetRasterBand(band_index)
    gt = ds.GetGeoTransform()
    width = ds.RasterXSize
    height = ds.RasterYSize

    rng = np.random.RandomState(seed)
    coords = []

    for y_off in range(0, height, block_size):
        y_size = min(block_size, height - y_off)
        for x_off in range(0, width, block_size):
            x_size = min(block_size, width - x_off)
            block = band.ReadAsArray(x_off, y_off, x_size, y_size)
            if block is None:
                continue

            rows, cols = np.where(block == target_class)
            if len(rows) == 0:
                continue

            # Subsample if needed
            if subsample_rate < 1.0:
                mask = rng.random(len(rows)) < subsample_rate
                rows = rows[mask]
                cols = cols[mask]

            # Convert pixel indices to map coordinates (pixel center)
            xs = gt[0] + (x_off + cols + 0.5) * gt[1]
            ys = gt[3] + (y_off + rows + 0.5) * gt[5]

            block_coords = np.column_stack([xs, ys])
            coords.append(block_coords)

    ds = None

    if coords:
        return np.vstack(coords)
    return np.empty((0, 2), dtype=float)
