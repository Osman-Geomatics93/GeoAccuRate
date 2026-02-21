# GeoAccuRate

**Accuracy Assessment Done Right** — a QGIS plugin for rigorous, reproducible accuracy assessment of classified maps.

## What It Does

GeoAccuRate replaces ad-hoc spreadsheet-based accuracy assessment with a single workflow inside QGIS:

**Sample Design** -> **Confusion Matrix** -> **Publication-Ready Report**

### Key Features

- **Stratified random sampling** with sample size calculator, proportional/equal allocation, and minimum distance constraints
- **Confusion matrix** (counts and row-normalized %) for any number of classes with OA, PA, UA, F1, and Wilson confidence intervals
- **Pontius metrics** (Quantity + Allocation Disagreement) — preferred over Kappa
- **Olofsson area-weighted estimation** — corrects for sampling bias using mapped area proportions
- **PDF reports** with tables, charts, interpretation notes, ISO 19157 quality mapping, auto-generated methods text, and proper citations
- **Persistent validation warnings** — amber widget for small sample sizes and under-sampled classes
- **Opinionated defaults** — scientifically defensible out of the box

### What Makes It Different

Most tools stop at OA + Kappa. GeoAccuRate implements:

- **Olofsson et al. (2014)** area-weighted accuracy and area estimation with confidence intervals
- **Pontius & Millones (2011)** disagreement decomposition (Quantity vs Allocation)
- **Wilson score intervals** instead of Wald (accurate even for small samples)
- **ISO 19157** quality element mapping for standards compliance
- **Automatic methods text** suitable for journal publication, with citations

## Installation

### From QGIS Plugin Repository (Recommended)

1. In QGIS: **Plugins** > **Manage and Install Plugins**
2. Search for **GeoAccuRate**
3. Click **Install Plugin**

### From ZIP

1. Download the latest release ZIP from [Releases](https://github.com/Osman-Geomatics93/GeoAccuRate/releases)
2. In QGIS: **Plugins** > **Manage and Install Plugins** > **Install from ZIP**
3. Enable GeoAccuRate in the plugin manager

### Dependencies

- **numpy** and **scipy** (bundled with QGIS)
- **matplotlib** (bundled with recent QGIS versions)
- **ReportLab** (for PDF reports): `pip install reportlab` in the QGIS Python console

## Quick Start

1. Load your classified raster and reference point layer into QGIS
2. Open GeoAccuRate (toolbar icon or Raster menu)
3. Go to the **Accuracy** tab
4. Select your classified raster, reference layer, and class field
5. Click **Run Assessment**
6. Click **Generate PDF Report**

## Architecture

```
geoaccurate/
├── domain/     # Pure math (numpy only, zero QGIS imports)
├── core/       # Geospatial I/O, validation, workflow orchestration
├── gui/        # Qt widgets, dock panel, dialogs
├── tasks/      # QgsTask background execution
└── reporting/  # PDF generation, charts, methods text
```

The `domain/` layer is independently testable with plain pytest — no QGIS required.

## Testing

```bash
# Domain tests (fast, no QGIS needed)
pytest geoaccurate/test/ -k "not integration" -v

# Full tests (requires QGIS environment)
pytest geoaccurate/test/ -v
```

86 unit tests covering confusion matrix, normalization, Pontius, Olofsson, Wilson CI, Kappa, sampling, and edge cases.

## References

- Congalton, R.G. and Green, K. (2019). *Assessing the Accuracy of Remotely Sensed Data*, 3rd ed. CRC Press.
- Olofsson, P. et al. (2014). Good practices for estimating area and assessing accuracy of land use change. *Remote Sensing of Environment*, 148, 42-57.
- Pontius, R.G. Jr. and Millones, M. (2011). Death to Kappa. *International Journal of Remote Sensing*, 32(15), 4407-4429.
- ISO (2013). ISO 19157:2013 Geographic information — Data quality. International Organization for Standardization.

## Citation

If you use GeoAccuRate in academic work, please cite:

> Ibrahim, O. (2026). GeoAccuRate: A unified accuracy assessment framework for QGIS. Version 1.1.0. https://github.com/Osman-Geomatics93/GeoAccuRate

## License

GPLv2+
