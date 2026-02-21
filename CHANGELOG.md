# Changelog

All notable changes to GeoAccuRate will be documented in this file.

## [1.0.0] - Unreleased

### Added
- Stratified random sampling with sample size calculator
- Proportional and equal allocation strategies
- Minimum distance constraint between sample points
- Export samples to GeoPackage and Shapefile
- Confusion matrix for N classes
- Overall, Producer's, and User's Accuracy with Wilson confidence intervals
- F1 / Precision / Recall per class
- Pontius Quantity and Allocation Disagreement (preferred over Kappa)
- Cohen's Kappa (optional, off by default)
- Area-weighted accuracy estimation (Olofsson et al. 2014)
- Publication-ready PDF reports with tables, charts, and auto-generated methods text
- Provenance JSON saved alongside reports for reproducibility
- Opinionated defaults: Pontius ON, Kappa OFF, Wilson CI 95%, projected CRS enforced
- Active warnings for under-sampled classes, nodata exclusions, CRS mismatches
