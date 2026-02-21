"""Vector I/O for GeoAccuRate.

Reads reference data from vector layers and exports sample points
to GeoPackage or Shapefile.

Depends on: GDAL/OGR, numpy.
"""

from typing import Dict, List, Optional, Tuple

import numpy as np

from osgeo import ogr, osr

from ..domain.models import SamplePoint


def read_reference_points(
    vector_path: str,
    class_field: str,
    layer_index: int = 0,
) -> Tuple[np.ndarray, np.ndarray, int]:
    """Read reference point locations and class values.

    Args:
        vector_path: Path to vector file (GeoPackage, Shapefile, etc.).
        class_field: Name of the attribute containing class values.
        layer_index: Layer index within the file.

    Returns:
        (points_xy, class_values, epsg):
          points_xy: Nx2 array of (x, y) coordinates.
          class_values: 1D array of integer class values.
          epsg: CRS EPSG code.
    """
    ds = ogr.Open(vector_path, 0)
    if ds is None:
        raise FileNotFoundError(f"Cannot open vector: {vector_path}")

    layer = ds.GetLayer(layer_index)
    if layer is None:
        raise ValueError(f"No layer at index {layer_index} in {vector_path}")

    srs = layer.GetSpatialRef()
    epsg = int(srs.GetAuthorityCode(None)) if srs else 0

    # Verify field exists
    layer_defn = layer.GetLayerDefn()
    field_idx = layer_defn.GetFieldIndex(class_field)
    if field_idx < 0:
        available = [
            layer_defn.GetFieldDefn(i).GetName()
            for i in range(layer_defn.GetFieldCount())
        ]
        raise ValueError(
            f"Field '{class_field}' not found. "
            f"Available fields: {available}"
        )

    xs, ys, vals = [], [], []
    layer.ResetReading()
    for feature in layer:
        geom = feature.GetGeometryRef()
        if geom is None:
            continue

        # Get point coordinates (centroid for polygons)
        if geom.GetGeometryType() in (ogr.wkbPoint, ogr.wkbPoint25D):
            x, y = geom.GetX(), geom.GetY()
        else:
            centroid = geom.Centroid()
            x, y = centroid.GetX(), centroid.GetY()

        val = feature.GetField(class_field)
        if val is None:
            continue

        xs.append(x)
        ys.append(y)
        vals.append(int(val))

    ds = None

    points_xy = np.column_stack([xs, ys]) if xs else np.empty((0, 2))
    class_values = np.array(vals, dtype=np.int64) if vals else np.empty(0, dtype=np.int64)

    return points_xy, class_values, epsg


def export_sample_points(
    points: List[SamplePoint],
    output_path: str,
    epsg: int,
    class_names: Optional[Dict[int, str]] = None,
    driver_name: str = "GPKG",
) -> str:
    """Export sample points to a vector file.

    Args:
        points: List of SamplePoint objects.
        output_path: Output file path.
        epsg: CRS EPSG code.
        class_names: Optional {class_value: name} for the stratum_name field.
        driver_name: OGR driver name ("GPKG" or "ESRI Shapefile").

    Returns:
        Output file path.
    """
    driver = ogr.GetDriverByName(driver_name)
    if driver is None:
        raise RuntimeError(f"OGR driver '{driver_name}' not available")

    ds = driver.CreateDataSource(output_path)
    if ds is None:
        raise RuntimeError(f"Cannot create output: {output_path}")

    srs = osr.SpatialReference()
    srs.ImportFromEPSG(epsg)

    layer = ds.CreateLayer("samples", srs, ogr.wkbPoint)

    # Define fields
    layer.CreateField(ogr.FieldDefn("point_id", ogr.OFTInteger))
    layer.CreateField(ogr.FieldDefn("map_class", ogr.OFTInteger))

    fld_label = ogr.FieldDefn("map_label", ogr.OFTString)
    fld_label.SetWidth(50)
    layer.CreateField(fld_label)

    fld_gt = ogr.FieldDefn("ground_truth", ogr.OFTString)
    fld_gt.SetWidth(50)
    layer.CreateField(fld_gt)

    fld_notes = ogr.FieldDefn("notes", ogr.OFTString)
    fld_notes.SetWidth(200)
    layer.CreateField(fld_notes)

    for pt in points:
        feature = ogr.Feature(layer.GetLayerDefn())
        feature.SetField("point_id", pt.id)
        feature.SetField("map_class", pt.stratum_class)
        if class_names and pt.stratum_class in class_names:
            feature.SetField("map_label", class_names[pt.stratum_class])

        geom = ogr.Geometry(ogr.wkbPoint)
        geom.AddPoint(pt.x, pt.y)
        feature.SetGeometry(geom)
        layer.CreateFeature(feature)

    ds.FlushCache()
    ds = None

    return output_path
