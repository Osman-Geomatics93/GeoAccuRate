"""Raster alignment checks for GeoAccuRate.

Detects CRS, resolution, and extent mismatches between rasters.
NEVER performs automatic resampling — only reports issues.

Depends on: GDAL.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .raster_reader import get_raster_info


@dataclass
class AlignmentIssue:
    severity: str     # 'FATAL' | 'WARNING'
    message: str
    suggestion: str


@dataclass
class AlignmentReport:
    issues: List[AlignmentIssue] = field(default_factory=list)
    overlap_extent: Optional[Tuple[float, float, float, float]] = None

    @property
    def is_aligned(self) -> bool:
        return not any(i.severity == "FATAL" for i in self.issues)


def check_alignment(
    raster_a_path: str,
    raster_b_path: str,
) -> AlignmentReport:
    """Check alignment between two rasters.

    Reports CRS, resolution, and extent issues.
    NEVER resamples — the user must resolve issues manually.

    Args:
        raster_a_path: First raster (typically the classified map).
        raster_b_path: Second raster (typically the reference raster).

    Returns:
        AlignmentReport with issues and overlap extent.
    """
    info_a = get_raster_info(raster_a_path)
    info_b = get_raster_info(raster_b_path)
    issues = []

    # 1. CRS check
    if info_a["crs_epsg"] != info_b["crs_epsg"]:
        issues.append(AlignmentIssue(
            severity="FATAL",
            message=(
                f"CRS mismatch: EPSG:{info_a['crs_epsg']} "
                f"vs EPSG:{info_b['crs_epsg']}"
            ),
            suggestion=(
                "Reproject one raster to match the other before "
                "running the assessment."
            ),
        ))

    # 2. Resolution check
    res_a = (info_a["pixel_size_x"], info_a["pixel_size_y"])
    res_b = (info_b["pixel_size_x"], info_b["pixel_size_y"])
    if abs(res_a[0] - res_b[0]) > 1e-6 or abs(res_a[1] - res_b[1]) > 1e-6:
        issues.append(AlignmentIssue(
            severity="WARNING",
            message=(
                f"Resolution mismatch: {res_a[0]:.4f} x {res_a[1]:.4f} "
                f"vs {res_b[0]:.4f} x {res_b[1]:.4f}"
            ),
            suggestion=(
                "For categorical data: resample using nearest neighbor. "
                "For continuous data: use bilinear interpolation. "
                "Resample BEFORE running the assessment — this plugin "
                "will not resample automatically."
            ),
        ))

    # 3. Extent overlap
    ext_a = info_a["extent"]  # (xmin, ymin, xmax, ymax)
    ext_b = info_b["extent"]

    overlap_xmin = max(ext_a[0], ext_b[0])
    overlap_ymin = max(ext_a[1], ext_b[1])
    overlap_xmax = min(ext_a[2], ext_b[2])
    overlap_ymax = min(ext_a[3], ext_b[3])

    if overlap_xmin >= overlap_xmax or overlap_ymin >= overlap_ymax:
        issues.append(AlignmentIssue(
            severity="FATAL",
            message="No spatial overlap between rasters.",
            suggestion="Check that both rasters cover the same area.",
        ))
        return AlignmentReport(issues=issues, overlap_extent=None)

    overlap_extent = (overlap_xmin, overlap_ymin, overlap_xmax, overlap_ymax)

    # Check overlap percentage
    area_a = (ext_a[2] - ext_a[0]) * (ext_a[3] - ext_a[1])
    area_overlap = (overlap_xmax - overlap_xmin) * (overlap_ymax - overlap_ymin)
    if area_a > 0:
        pct = area_overlap / area_a * 100
        if pct < 90:
            issues.append(AlignmentIssue(
                severity="WARNING",
                message=f"Only {pct:.1f}% spatial overlap between rasters.",
                suggestion="Assessment will use only the overlapping area.",
            ))

    return AlignmentReport(issues=issues, overlap_extent=overlap_extent)
