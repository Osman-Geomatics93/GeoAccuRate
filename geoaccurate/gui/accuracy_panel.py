"""Categorical accuracy assessment panel.

Wires GUI controls to existing QgsTask workflows for accuracy assessment,
result display, and PDF report generation.
"""

import numpy as np

from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from qgis.gui import QgsFieldComboBox, QgsMapLayerComboBox
from qgis.core import Qgis, QgsApplication, QgsMapLayerProxyModel, QgsProject

# Cross-version layer filter compatibility (3.34 vs 3.44+)
try:
    _RasterFilter = Qgis.LayerFilter.RasterLayer
    _PointFilter = Qgis.LayerFilter.PointLayer
    _PolygonFilter = Qgis.LayerFilter.PolygonLayer
except AttributeError:
    _RasterFilter = QgsMapLayerProxyModel.RasterLayer
    _PointFilter = QgsMapLayerProxyModel.PointLayer
    _PolygonFilter = QgsMapLayerProxyModel.PolygonLayer


class AccuracyPanel(QWidget):
    """Accuracy tab: categorical accuracy assessment.

    Workflow:
      1. User selects classified raster + reference layer + class field
      2. Plugin auto-detects class mapping
      3. User configures metrics (Pontius, Olofsson, Kappa)
      4. Run -> results displayed in panel
      5. Generate PDF report
    """

    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self._last_result = None
        self._last_metadata = None
        self._last_validation = None
        self._current_task = None
        self._report_task = None
        self._setup_ui()
        self._connect_signals()
        # Sync field combo with any pre-selected reference layer
        self._on_reference_changed(self.cmb_reference.currentLayer())

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # -- Input section --
        input_group = QGroupBox("Input Data")
        input_layout = QVBoxLayout(input_group)

        input_layout.addWidget(QLabel("Classified raster:"))
        self.cmb_classified = QgsMapLayerComboBox()
        self.cmb_classified.setFilters(_RasterFilter)
        input_layout.addWidget(self.cmb_classified)

        input_layout.addWidget(QLabel("Reference layer:"))
        self.cmb_reference = QgsMapLayerComboBox()
        self.cmb_reference.setFilters(_PointFilter | _PolygonFilter)
        input_layout.addWidget(self.cmb_reference)

        input_layout.addWidget(QLabel("Reference class field:"))
        self.cmb_ref_field = QgsFieldComboBox()
        input_layout.addWidget(self.cmb_ref_field)

        # Class mapping
        mapping_row = QHBoxLayout()
        self.lbl_mapping = QLabel("Class mapping: Auto-detected")
        mapping_row.addWidget(self.lbl_mapping)
        self.btn_edit_mapping = QPushButton("Edit...")
        self.btn_edit_mapping.setMaximumWidth(60)
        mapping_row.addWidget(self.btn_edit_mapping)
        input_layout.addLayout(mapping_row)

        layout.addWidget(input_group)

        # -- Metrics configuration --
        metrics_group = QGroupBox("Metrics")
        metrics_layout = QVBoxLayout(metrics_group)

        self.chk_area_weighted = QCheckBox("Area-weighted (Olofsson et al. 2014)")
        self.chk_area_weighted.setChecked(True)
        metrics_layout.addWidget(self.chk_area_weighted)

        self.chk_pontius = QCheckBox("Pontius Quantity/Allocation Disagreement")
        self.chk_pontius.setChecked(True)
        metrics_layout.addWidget(self.chk_pontius)

        self.chk_ci = QCheckBox("Confidence intervals (95%, Wilson)")
        self.chk_ci.setChecked(True)
        metrics_layout.addWidget(self.chk_ci)

        self.chk_kappa = QCheckBox("Kappa (legacy)")
        self.chk_kappa.setChecked(False)
        metrics_layout.addWidget(self.chk_kappa)

        layout.addWidget(metrics_group)

        # -- Run button --
        self.btn_run = QPushButton("Run Assessment")
        self.btn_run.setMinimumHeight(36)
        layout.addWidget(self.btn_run)

        # -- Results section --
        self.results_group = QGroupBox("Results")
        self.results_group.setVisible(False)
        results_layout = QVBoxLayout(self.results_group)

        self.lbl_oa = QLabel()
        self.lbl_qd = QLabel()
        self.lbl_ad = QLabel()
        self.lbl_kappa = QLabel()
        results_layout.addWidget(self.lbl_oa)
        results_layout.addWidget(self.lbl_qd)
        results_layout.addWidget(self.lbl_ad)
        results_layout.addWidget(self.lbl_kappa)

        btn_row = QHBoxLayout()
        self.btn_view_matrix = QPushButton("View Confusion Matrix")
        self.btn_view_matrix.setEnabled(False)
        btn_row.addWidget(self.btn_view_matrix)
        self.btn_view_details = QPushButton("View Per-Class")
        self.btn_view_details.setEnabled(False)
        btn_row.addWidget(self.btn_view_details)
        results_layout.addLayout(btn_row)

        # Persistent warnings label
        self.warnings_label = QLabel()
        self.warnings_label.setWordWrap(True)
        self.warnings_label.setStyleSheet(
            "QLabel { background-color: #FFF3CD; color: #664D03; "
            "border: 1px solid #FFECB5; border-radius: 4px; padding: 6px; }"
        )
        self.warnings_label.setVisible(False)
        results_layout.addWidget(self.warnings_label)

        layout.addWidget(self.results_group)

        # -- Report button --
        self.btn_report = QPushButton("Generate PDF Report")
        self.btn_report.setEnabled(False)
        self.btn_report.setMinimumHeight(36)
        layout.addWidget(self.btn_report)

        layout.addStretch()

    def _connect_signals(self):
        self.cmb_reference.layerChanged.connect(self._on_reference_changed)
        self.btn_edit_mapping.clicked.connect(self._on_edit_mapping)
        self.btn_run.clicked.connect(self._on_run)
        self.btn_view_matrix.clicked.connect(self._on_view_matrix)
        self.btn_view_details.clicked.connect(self._on_view_details)
        self.btn_report.clicked.connect(self._on_generate_report)

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------

    def _on_reference_changed(self, layer):
        """Update field combo when reference layer changes."""
        self.cmb_ref_field.setLayer(layer)

    def _on_edit_mapping(self):
        """Open class mapping editor dialog."""
        self.iface.messageBar().pushMessage(
            "GeoAccuRate",
            "Class mapping is auto-detected from reference data. "
            "Custom mapping editor coming in a future version.",
            level=Qgis.Info, duration=5,
        )

    def _on_run(self):
        """Launch accuracy assessment task."""
        # --- Validate inputs ---
        classified_layer = self.cmb_classified.currentLayer()
        reference_layer = self.cmb_reference.currentLayer()
        field_name = self.cmb_ref_field.currentField()

        if not classified_layer:
            self._show_warning("Please select a classified raster.")
            return
        if not reference_layer:
            self._show_warning("Please select a reference layer.")
            return
        if not field_name:
            self._show_warning("Please select a reference class field.")
            return

        # --- Extract reference data on the main thread (QGIS API) ---
        points_xy = []
        class_values = []
        skipped = 0

        for feature in reference_layer.getFeatures():
            geom = feature.geometry()
            if geom is None or geom.isEmpty():
                skipped += 1
                continue

            val = feature[field_name]
            if val is None:
                skipped += 1
                continue

            try:
                cls_val = int(val)
            except (ValueError, TypeError):
                skipped += 1
                continue

            point = geom.centroid().asPoint()
            points_xy.append([point.x(), point.y()])
            class_values.append(cls_val)

        if not points_xy:
            self._show_warning(
                "No valid reference points found. "
                "Check that the class field contains integer values."
            )
            return

        if skipped > 0:
            self.iface.messageBar().pushMessage(
                "GeoAccuRate",
                f"{skipped} reference features skipped (null geometry/value).",
                level=Qgis.Warning, duration=5,
            )

        points_xy = np.array(points_xy)
        class_values = np.array(class_values, dtype=np.int64)

        # Auto-detect class labels from reference data
        unique_labels = sorted(set(class_values.tolist()))
        class_labels = tuple(unique_labels)
        class_names = {v: str(v) for v in class_labels}

        # --- Build config dict (all data copied — thread-safe) ---
        config = {
            "classified_raster_path": classified_layer.source(),
            "reference_points_xy": points_xy,
            "reference_class_values": class_values,
            "class_labels": class_labels,
            "class_names": class_names,
            "class_mapping": None,
            "compute_kappa": self.chk_kappa.isChecked(),
            "compute_area_weighted": self.chk_area_weighted.isChecked(),
            "confidence_level": 0.95,
            "plugin_version": "1.0.0",
            "qgis_version": Qgis.QGIS_VERSION,
            "reference_layer_path": reference_layer.source(),
            "reference_layer_name": reference_layer.name(),
            "reference_field": field_name,
        }

        # --- Disable UI, launch task ---
        self.btn_run.setEnabled(False)
        self.btn_run.setText("Running...")
        self.btn_view_matrix.setEnabled(False)
        self.btn_view_details.setEnabled(False)
        self.btn_report.setEnabled(False)
        self.results_group.setVisible(False)
        self.warnings_label.setVisible(False)

        from ..tasks.accuracy_task import AccuracyTask

        task = AccuracyTask(config)
        self._current_task = task  # prevent garbage collection

        task.taskCompleted.connect(lambda: self._on_task_finished(True))
        task.taskTerminated.connect(lambda: self._on_task_finished(False))

        QgsApplication.taskManager().addTask(task)

    def _on_task_finished(self, success):
        """Handle accuracy task completion on the main thread."""
        self.btn_run.setEnabled(True)
        self.btn_run.setText("Run Assessment")

        task = self._current_task
        if task is None:
            return

        if success and task.result is not None:
            self.display_results(task.result)
            self._last_metadata = task.metadata
            self._last_validation = task.validation

            # Show validation warnings
            if task.validation and task.validation.has_warnings:
                bullets = []
                for w in task.validation.warnings:
                    self.iface.messageBar().pushMessage(
                        "GeoAccuRate", w.message,
                        level=Qgis.Warning, duration=8,
                    )
                    bullets.append(f"\u2022 {w.message}")
                self.warnings_label.setText("\n".join(bullets))
                self.warnings_label.setVisible(True)
            else:
                self.warnings_label.setVisible(False)

            self.iface.messageBar().pushMessage(
                "GeoAccuRate",
                f"Assessment complete: OA = {task.result.overall_accuracy:.1%}",
                level=Qgis.Success, duration=5,
            )
        else:
            msg = str(task.exception) if task.exception else "Task cancelled or failed."
            self._show_error(msg)

    def _on_view_matrix(self):
        """Open confusion matrix dialog."""
        if self._last_result is None:
            self._show_warning("No results available. Run assessment first.")
            return

        from .results_dialog import ConfusionMatrixDialog

        dlg = ConfusionMatrixDialog(self._last_result, parent=self)
        dlg.exec_()

    def _on_view_details(self):
        """Open per-class metrics dialog."""
        if self._last_result is None:
            self._show_warning("No results available. Run assessment first.")
            return

        from .results_dialog import PerClassMetricsDialog

        dlg = PerClassMetricsDialog(self._last_result, parent=self)
        dlg.exec_()

    def _on_generate_report(self):
        """Launch PDF report generation."""
        if self._last_result is None:
            self._show_warning("No results to report. Run assessment first.")
            return

        from ..reporting.pdf_builder import is_pdf_available

        if not is_pdf_available():
            self._show_error(
                "PDF generation requires ReportLab. "
                "Install via: pip install reportlab"
            )
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Save PDF Report", "", "PDF files (*.pdf)"
        )
        if not path:
            return

        if not path.lower().endswith(".pdf"):
            path += ".pdf"

        from pathlib import Path

        from ..domain.models import ReportContent
        from ..tasks.report_task import ReportTask

        # Auto-fill metadata from current context
        classified_layer = self.cmb_classified.currentLayer()
        layer_name = classified_layer.name() if classified_layer else "Unknown"
        title = f"{layer_name} \u2014 Accuracy Assessment"

        try:
            author = QgsApplication.instance().userProfileManager().userProfile().name()
        except Exception:
            author = ""

        project = QgsProject.instance()
        project_name = project.title()
        if not project_name:
            proj_path = project.fileName()
            project_name = Path(proj_path).stem if proj_path else ""

        validation_warnings = ()
        if self._last_validation and self._last_validation.has_warnings:
            validation_warnings = tuple(
                w.message for w in self._last_validation.warnings
            )

        content = ReportContent(
            metadata=self._last_metadata,
            result=self._last_result,
            title=title,
            author=author,
            validation_warnings=validation_warnings,
            project_name=project_name,
        )

        task = ReportTask(content, path)
        self._report_task = task  # prevent garbage collection

        self.btn_report.setEnabled(False)
        self.btn_report.setText("Generating...")

        task.taskCompleted.connect(lambda: self._on_report_finished(True))
        task.taskTerminated.connect(lambda: self._on_report_finished(False))

        QgsApplication.taskManager().addTask(task)

    def _on_report_finished(self, success):
        """Handle report task completion on the main thread."""
        self.btn_report.setEnabled(True)
        self.btn_report.setText("Generate PDF Report")

        task = self._report_task
        if task is None:
            return

        if success:
            self.iface.messageBar().pushMessage(
                "GeoAccuRate",
                f"Report saved: {task.output_path}",
                level=Qgis.Success, duration=5,
            )
        else:
            msg = str(task.exception) if task.exception else "Report generation failed."
            self._show_error(msg)

    # ------------------------------------------------------------------
    # Result display
    # ------------------------------------------------------------------

    def display_results(self, result):
        """Populate the results section from a ConfusionMatrixResult."""
        self._last_result = result
        self.results_group.setVisible(True)
        self.warnings_label.setText("")
        self.warnings_label.setVisible(False)

        ci_text = ""
        if result.overall_accuracy_ci:
            lo, hi = result.overall_accuracy_ci
            ci_text = f" [{lo:.1%} \u2013 {hi:.1%}]"
        self.lbl_oa.setText(
            f"Overall Accuracy: {result.overall_accuracy:.1%}{ci_text}"
        )

        self.lbl_qd.setText(
            f"Quantity Disagreement: {result.quantity_disagreement:.4f}"
        )
        self.lbl_ad.setText(
            f"Allocation Disagreement: {result.allocation_disagreement:.4f}"
        )

        if result.kappa is not None:
            self.lbl_kappa.setText(f"Kappa: {result.kappa:.4f}")
            self.lbl_kappa.setVisible(True)
        else:
            self.lbl_kappa.setVisible(False)

        self.btn_view_matrix.setEnabled(True)
        self.btn_view_details.setEnabled(True)
        self.btn_report.setEnabled(True)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _show_warning(self, message):
        self.iface.messageBar().pushMessage(
            "GeoAccuRate", message, level=Qgis.Warning, duration=8,
        )

    def _show_error(self, message):
        self.iface.messageBar().pushMessage(
            "GeoAccuRate", message, level=Qgis.Critical, duration=10,
        )
