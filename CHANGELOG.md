# Changelog

All notable changes to GeoAccuRate will be documented in this file.

## [1.2.0] - 2026-02-21

### Added
- Validation Philosophy section framing accuracy assessment as statistical inference
- Reproducibility & Scientific Integrity section with guarantees table and Mermaid diagram
- Technical Highlights section showcasing architecture decisions
- Known Limitations section for transparency and trust
- Coverage badge (92% on statistical core via pytest-cov)
- Versioning policy (Semantic Versioning) with examples table
- Vision statement positioning GeoAccuRate as standard open-source framework
- Mathematical Foundation section with LaTeX equations (Cochran, Wilson, Pontius, Olofsson)
- Mermaid diagrams: workflow pipeline, sequence diagram, architecture graph, mindmap, gitGraph
- Collapsible FAQ (6 questions) and installation troubleshooting section
- Tech stack badges (Python, NumPy, SciPy, Qt, Matplotlib, ReportLab)
- Acknowledgements section crediting foundational researchers
- Contributors section with auto-generated avatars
- Star History chart with dark/light mode support
- Table of Contents with back-to-top navigation
- Cochran (1977) added to references

### Changed
- Comparison table now uses emoji icons
- Badges upgraded to for-the-badge style
- Contributing section enhanced with gitGraph diagram

## [1.1.0] - 2026-02-21

### Added
- Row-normalized confusion matrix table (Table B) in PDF reports
- ISO 19157 quality element mapping table with informational disclaimer
- Interpretation notes section with sample-size and per-class warnings
- Persistent amber warnings widget in the accuracy panel
- Auto-filled report metadata (title from layer name, author from QGIS profile, project name)
- Confidence interval clamping to logical bounds with explanatory footnote
- "Not specified" fallback when author is blank
- ISO 19157:2013 citation in references section
- 6 new unit tests for confusion matrix normalization

### Changed
- Provenance section renumbered to section 9 (after new ISO 19157 section 8)
- Result buttons (View Matrix, View Per-Class, Generate PDF) now disable during assessment runs
- Improved vertical spacing between PDF report sections
- Interpretation Notes styled with italic heading and grey background
- Warnings deduplicated with class name enrichment and consistent bullet symbols

## [1.0.0] - 2026-02-21

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
