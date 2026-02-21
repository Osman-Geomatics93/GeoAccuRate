<p align="center">
  <img src="geoaccurate/icons/icon.png" width="80">
</p>

<h1 align="center">GeoAccuRate</h1>

<p align="center">
  <b>Scientific Accuracy Assessment Framework for QGIS</b><br>
  Confusion Matrix &bull; Wilson CI &bull; Pontius Disagreement &bull; Olofsson Area-Weighted Estimation
</p>

<p align="center">
  <img src="https://img.shields.io/badge/QGIS-3.34%2B-brightgreen" alt="QGIS Version">
  <img src="https://img.shields.io/badge/License-GPLv2%2B-blue" alt="License">
  <img src="https://img.shields.io/badge/Tests-86%20passing-success" alt="Tests">
  <a href="https://github.com/Osman-Geomatics93/GeoAccuRate/releases/latest"><img src="https://img.shields.io/github/v/release/Osman-Geomatics93/GeoAccuRate" alt="Release"></a>
  <a href="https://github.com/Osman-Geomatics93/GeoAccuRate/actions"><img src="https://github.com/Osman-Geomatics93/GeoAccuRate/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
</p>

---

GeoAccuRate replaces ad-hoc spreadsheet-based accuracy assessment with a single, reproducible workflow inside QGIS:

**Sample Design** &rarr; **Confusion Matrix** &rarr; **Publication-Ready Report**

## Why Accuracy Assessment Matters

Most GIS workflows stop at Overall Accuracy and Kappa. However, modern remote sensing research requires:

- Proper **confidence intervals** (not Wald approximations)
- **Disagreement decomposition** into Quantity and Allocation components (Pontius & Millones, 2011)
- **Area-weighted estimation** that corrects for sampling bias (Olofsson et al., 2014)
- **ISO 19157** quality reporting for standards compliance

GeoAccuRate brings these best practices directly into QGIS — no spreadsheets, no scripts, no guesswork.

## Features

- **Stratified random sampling** with sample size calculator, proportional/equal allocation, and minimum distance constraints
- **Confusion matrix** (counts and row-normalized %) for any number of classes
- **OA, PA, UA, F1** with **Wilson confidence intervals** (clamped to logical bounds)
- **Pontius metrics** (Quantity + Allocation Disagreement) — preferred over Kappa
- **Olofsson area-weighted estimation** with class area confidence intervals
- **PDF reports** with tables, heatmaps, interpretation notes, ISO 19157 mapping, auto-generated methods text, and proper citations
- **Persistent validation warnings** for small sample sizes and under-sampled classes
- **Opinionated defaults** — scientifically defensible out of the box

## Comparison With Other Tools

| Feature | GeoAccuRate | Default QGIS | ENVI | Google Earth Engine |
|---------|:-----------:|:------------:|:----:|:-------------------:|
| Wilson confidence intervals | Yes | No | No | No |
| Pontius QD/AD decomposition | Yes | No | No | No |
| Olofsson area-weighted estimation | Yes | No | Partial | Manual |
| ISO 19157 quality mapping | Yes | No | No | No |
| Auto-generated methods text | Yes | No | No | No |
| Publication-ready PDF report | Yes | No | No | No |
| Sample size optimization | Yes | No | No | No |
| Interpretation warnings | Yes | No | No | No |

## Screenshots

<p align="center">
  <img src="docs/images/accuracy_tab.png" width="300" alt="Accuracy Tab">
  &nbsp;&nbsp;
  <img src="docs/images/report_preview.png" width="400" alt="PDF Report">
</p>

> Screenshots coming soon. Run the plugin to see it in action!

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

## Design Philosophy

GeoAccuRate is built on three principles:

1. **Statistical rigor first** — Wilson intervals over Wald, Pontius over Kappa, area-weighted over naive
2. **Reproducibility by default** — provenance JSON saved with every report, deterministic random seeds
3. **Opinionated scientific defaults** — no silent resampling, CIs clamped to logical bounds, warnings for insufficient sample sizes

The plugin avoids common pitfalls in accuracy assessment by enforcing projected CRS for area calculations, flagging under-sampled classes, and generating methods text with proper citations ready for journal submission.

## Who Should Use GeoAccuRate?

- MSc and PhD students conducting land cover validation
- Remote sensing researchers publishing accuracy assessments
- Government land cover and land use mapping programs
- NGOs and environmental monitoring agencies
- Urban planners and agricultural analysts

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

## Roadmap

Planned features for future versions:

- Change detection accuracy module
- Continuous raster validation (RMSE, MAE, NSE)
- Multi-classifier comparison dashboard
- Batch processing mode for multiple classifications
- Automated LaTeX/Word export of methods text

## References

- Congalton, R.G. and Green, K. (2019). *Assessing the Accuracy of Remotely Sensed Data*, 3rd ed. CRC Press.
- Olofsson, P. et al. (2014). Good practices for estimating area and assessing accuracy of land use change. *Remote Sensing of Environment*, 148, 42-57. [doi:10.1016/j.rse.2014.02.015](https://doi.org/10.1016/j.rse.2014.02.015)
- Pontius, R.G. Jr. and Millones, M. (2011). Death to Kappa. *International Journal of Remote Sensing*, 32(15), 4407-4429. [doi:10.1080/01431161.2011.552923](https://doi.org/10.1080/01431161.2011.552923)
- ISO (2013). ISO 19157:2013 Geographic information — Data quality. International Organization for Standardization.

## Citation

If you use GeoAccuRate in academic work, please cite:

> Ibrahim, O. (2026). GeoAccuRate: A unified accuracy assessment framework for QGIS. Version 1.1.0. https://github.com/Osman-Geomatics93/GeoAccuRate

### BibTeX

```bibtex
@software{ibrahim2026geoaccurate,
  author    = {Ibrahim, Osman},
  title     = {GeoAccuRate: A Unified Accuracy Assessment Framework for QGIS},
  year      = {2026},
  version   = {1.1.0},
  url       = {https://github.com/Osman-Geomatics93/GeoAccuRate},
  license   = {GPL-2.0-or-later}
}
```

## Contributing

Contributions are welcome!

- Open an [issue](https://github.com/Osman-Geomatics93/GeoAccuRate/issues) for bug reports or feature requests
- Submit pull requests for improvements
- Help improve documentation or translations

Please ensure tests pass before submitting: `pytest geoaccurate/test/ -k "not integration" -v`

## License

GPLv2+ — see [LICENSE](geoaccurate/LICENSE) for details.
