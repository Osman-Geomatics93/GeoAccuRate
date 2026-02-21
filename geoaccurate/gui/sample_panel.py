"""Sample design and generation panel.

Wires GUI controls to existing QgsTask workflows for sample size
calculation, stratified random sampling, and export.
"""

import random

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qgis.gui import QgsMapLayerComboBox
from qgis.core import Qgis, QgsApplication, QgsMapLayerProxyModel

# Cross-version layer filter compatibility (3.34 vs 3.44+)
try:
    _RasterFilter = Qgis.LayerFilter.RasterLayer
except AttributeError:
    _RasterFilter = QgsMapLayerProxyModel.RasterLayer


class SamplePanel(QWidget):
    """Samples tab: sample design, size calculation, and generation.

    Workflow:
      1. User selects classified raster
      2. Plugin detects classes and pixel counts
      3. User configures sample size calculator
      4. User generates samples -> exported as vector layer
    """

    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self._pixel_counts = {}
        self._recommended_n = 0
        self._allocation = {}
        self._sample_result = None
        self._sampling_task = None
        self._setup_ui()
        self._connect_signals()
        # Trigger initial class detection for any pre-selected raster
        self._on_raster_changed(self.cmb_raster.currentLayer())

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # -- Input section --
        input_group = QGroupBox("Input")
        input_layout = QVBoxLayout(input_group)

        lbl = QLabel("Classified raster:")
        self.cmb_raster = QgsMapLayerComboBox()
        self.cmb_raster.setFilters(_RasterFilter)
        input_layout.addWidget(lbl)
        input_layout.addWidget(self.cmb_raster)

        self.lbl_raster_status = QLabel("")
        self.lbl_raster_status.setWordWrap(True)
        input_layout.addWidget(self.lbl_raster_status)

        self.lbl_classes = QLabel("Classes detected: \u2014")
        input_layout.addWidget(self.lbl_classes)

        self.tbl_strata = QTableWidget(0, 3)
        self.tbl_strata.setHorizontalHeaderLabels(["Class", "Pixels", "%"])
        self.tbl_strata.setMaximumHeight(150)
        input_layout.addWidget(self.tbl_strata)

        layout.addWidget(input_group)

        # -- Sample size calculator --
        calc_group = QGroupBox("Sample Size Calculator")
        calc_layout = QVBoxLayout(calc_group)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Confidence level:"))
        self.spn_confidence = QDoubleSpinBox()
        self.spn_confidence.setRange(80.0, 99.9)
        self.spn_confidence.setValue(95.0)
        self.spn_confidence.setSuffix("%")
        row1.addWidget(self.spn_confidence)
        calc_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Expected accuracy:"))
        self.spn_expected_acc = QDoubleSpinBox()
        self.spn_expected_acc.setRange(50.0, 99.9)
        self.spn_expected_acc.setValue(85.0)
        self.spn_expected_acc.setSuffix("%")
        row2.addWidget(self.spn_expected_acc)
        calc_layout.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Margin of error:"))
        self.spn_margin = QDoubleSpinBox()
        self.spn_margin.setRange(1.0, 20.0)
        self.spn_margin.setValue(5.0)
        self.spn_margin.setSuffix("%")
        row3.addWidget(self.spn_margin)
        calc_layout.addLayout(row3)

        self.lbl_recommended_n = QLabel("Recommended: \u2014")
        self.lbl_recommended_n.setStyleSheet("font-weight: bold;")
        calc_layout.addWidget(self.lbl_recommended_n)

        total_row = QHBoxLayout()
        total_row.addWidget(QLabel("Total samples:"))
        self.spn_total_n = QSpinBox()
        self.spn_total_n.setRange(1, 1000000)
        self.spn_total_n.setValue(196)
        total_row.addWidget(self.spn_total_n)
        calc_layout.addLayout(total_row)

        layout.addWidget(calc_group)

        # -- Allocation --
        alloc_group = QGroupBox("Allocation")
        alloc_layout = QVBoxLayout(alloc_group)

        self.rdo_proportional = QRadioButton("Proportional")
        self.rdo_proportional.setChecked(True)
        self.rdo_equal = QRadioButton("Equal")
        alloc_row = QHBoxLayout()
        alloc_row.addWidget(self.rdo_proportional)
        alloc_row.addWidget(self.rdo_equal)
        alloc_layout.addLayout(alloc_row)

        self.tbl_allocation = QTableWidget(0, 2)
        self.tbl_allocation.setHorizontalHeaderLabels(["Class", "Samples"])
        self.tbl_allocation.setMaximumHeight(120)
        alloc_layout.addWidget(self.tbl_allocation)

        layout.addWidget(alloc_group)

        # -- Constraints --
        constraint_row = QHBoxLayout()
        constraint_row.addWidget(QLabel("Min. distance (m):"))
        self.spn_min_distance = QDoubleSpinBox()
        self.spn_min_distance.setRange(0, 100000)
        self.spn_min_distance.setValue(0)
        constraint_row.addWidget(self.spn_min_distance)

        constraint_row.addWidget(QLabel("Seed:"))
        self.txt_seed = QLineEdit("42")
        self.txt_seed.setMaximumWidth(80)
        constraint_row.addWidget(self.txt_seed)
        self.btn_random_seed = QPushButton("Random")
        self.btn_random_seed.setMaximumWidth(60)
        constraint_row.addWidget(self.btn_random_seed)
        layout.addLayout(constraint_row)

        # -- Generate button --
        self.btn_generate = QPushButton("Generate Reference Sample Points")
        self.btn_generate.setToolTip(
            "Generate stratified random points for ground truth collection.\n"
            "Visit these locations in the field (or check against high-res imagery)\n"
            "to record the actual land cover class for accuracy assessment."
        )
        self.btn_generate.setMinimumHeight(36)
        layout.addWidget(self.btn_generate)

        # -- Export --
        export_row = QHBoxLayout()
        self.cmb_export_format = QComboBox()
        self.cmb_export_format.addItems(["GeoPackage", "Shapefile"])
        export_row.addWidget(self.cmb_export_format)
        self.btn_export = QPushButton("Save")
        self.btn_export.setEnabled(False)
        export_row.addWidget(self.btn_export)
        layout.addLayout(export_row)

        layout.addStretch()

    def _connect_signals(self):
        self.cmb_raster.layerChanged.connect(self._on_raster_changed)
        self.spn_confidence.valueChanged.connect(self._update_sample_size)
        self.spn_expected_acc.valueChanged.connect(self._update_sample_size)
        self.spn_margin.valueChanged.connect(self._update_sample_size)
        self.spn_total_n.valueChanged.connect(self._update_allocation)
        self.rdo_proportional.toggled.connect(self._update_allocation)
        self.rdo_equal.toggled.connect(self._update_allocation)
        self.tbl_allocation.cellChanged.connect(self._on_allocation_edited)
        self.btn_generate.clicked.connect(self._on_generate)
        self.btn_export.clicked.connect(self._on_export)
        self.btn_random_seed.clicked.connect(self._on_random_seed)

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------

    def _on_raster_changed(self, layer):
        """Detect classes and pixel counts when raster selection changes."""
        self.lbl_raster_status.setText("")

        if layer is None:
            self.lbl_classes.setText("Classes detected: \u2014")
            self.tbl_strata.setRowCount(0)
            self._pixel_counts = {}
            self._update_sample_size()
            return

        # --- Check if raster looks like a classified map ---
        from ..core.raster_reader import count_pixels_per_class, get_raster_info
        from qgis.PyQt.QtWidgets import QApplication

        try:
            info = get_raster_info(layer.source())
        except Exception as e:
            self._show_warning(f"Cannot read raster: {e}")
            self._pixel_counts = {}
            self._update_sample_size()
            return

        dtype = info.get("dtype", "").lower()
        is_float = "float" in dtype

        if is_float:
            self.lbl_raster_status.setText(
                "\u26a0 This looks like a raw/continuous raster (float dtype). "
                "Sampling requires a classified raster with integer class values."
            )
            self.lbl_raster_status.setStyleSheet("color: red;")
            self._pixel_counts = {}
            self.lbl_classes.setText("Classes detected: \u2014")
            self.tbl_strata.setRowCount(0)
            self._update_sample_size()
            return

        # Read pixel counts on main thread with wait cursor.
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self._pixel_counts = count_pixels_per_class(layer.source())
        except Exception as e:
            QApplication.restoreOverrideCursor()
            self._show_warning(f"Failed to read raster classes: {e}")
            self._pixel_counts = {}
            self._update_sample_size()
            return
        QApplication.restoreOverrideCursor()

        classes = sorted(self._pixel_counts.keys())
        n_classes = len(classes)

        # Warn if too many unique values (probably not a classification)
        if n_classes > 100:
            self.lbl_raster_status.setText(
                f"\u26a0 {n_classes} unique values detected. This looks like "
                "a raw raster, not a classification. Expected < 50 classes."
            )
            self.lbl_raster_status.setStyleSheet("color: red;")
            self._pixel_counts = {}
            self.lbl_classes.setText("Classes detected: \u2014")
            self.tbl_strata.setRowCount(0)
            self._update_sample_size()
            return

        if n_classes > 30:
            self.lbl_raster_status.setText(
                f"\u26a0 {n_classes} classes detected \u2014 unusually high. "
                "Verify this is a classified raster."
            )
            self.lbl_raster_status.setStyleSheet("color: orange;")
        else:
            self.lbl_raster_status.setText(
                f"\u2713 Classification raster ({info.get('dtype', '?')}, "
                f"{info['width']}\u00d7{info['height']}, "
                f"EPSG:{info['crs_epsg']})"
            )
            self.lbl_raster_status.setStyleSheet("color: green;")

        # Populate strata table
        total = sum(self._pixel_counts.values())

        self.lbl_classes.setText(f"Classes detected: {n_classes}")
        self.tbl_strata.setRowCount(n_classes)

        for i, cls in enumerate(classes):
            count = self._pixel_counts[cls]
            pct = count / total * 100 if total > 0 else 0

            item_cls = QTableWidgetItem(str(cls))
            item_cls.setFlags(item_cls.flags() & ~Qt.ItemIsEditable)
            self.tbl_strata.setItem(i, 0, item_cls)

            item_pix = QTableWidgetItem(f"{count:,}")
            item_pix.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            item_pix.setFlags(item_pix.flags() & ~Qt.ItemIsEditable)
            self.tbl_strata.setItem(i, 1, item_pix)

            item_pct = QTableWidgetItem(f"{pct:.1f}")
            item_pct.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            item_pct.setFlags(item_pct.flags() & ~Qt.ItemIsEditable)
            self.tbl_strata.setItem(i, 2, item_pct)

        self._update_sample_size()

    def _update_sample_size(self):
        """Recalculate recommended sample size from calculator inputs."""
        if not self._pixel_counts:
            self.lbl_recommended_n.setText("Recommended: \u2014")
            self._recommended_n = 0
            self._update_allocation()
            return

        from ..domain.sample_size import calculate_sample_size

        confidence = self.spn_confidence.value() / 100.0
        expected_acc = self.spn_expected_acc.value() / 100.0
        margin = self.spn_margin.value() / 100.0
        total_pixels = sum(self._pixel_counts.values())

        try:
            n = calculate_sample_size(
                confidence_level=confidence,
                expected_accuracy=expected_acc,
                margin_of_error=margin,
                population_size=total_pixels,
            )
            self._recommended_n = n
            self.lbl_recommended_n.setText(f"Recommended: {n}")
            # Set spinbox to recommended value (user can override)
            self.spn_total_n.blockSignals(True)
            self.spn_total_n.setValue(n)
            self.spn_total_n.blockSignals(False)
        except ValueError as e:
            self.lbl_recommended_n.setText(f"Error: {e}")
            self._recommended_n = 0

        self._update_allocation()

    def _update_allocation(self):
        """Recalculate per-class allocation based on strategy and total N."""
        total_n = self.spn_total_n.value()
        if not self._pixel_counts or total_n <= 0:
            self.tbl_allocation.setRowCount(0)
            self._allocation = {}
            return

        from ..domain.sample_size import allocate_equal, allocate_proportional

        classes = sorted(self._pixel_counts.keys())
        k = len(classes)

        # Scale min_per_class to respect the user's chosen total.
        # Default 25 (Olofsson), but reduce if total is too small.
        min_per_class = min(25, max(1, total_n // k))

        try:
            if self.rdo_proportional.isChecked():
                allocation, warnings = allocate_proportional(
                    total_n, self._pixel_counts, min_per_class=min_per_class
                )
            else:
                allocation, warnings = allocate_equal(total_n, classes)
        except ValueError:
            self.tbl_allocation.setRowCount(0)
            self._allocation = {}
            return

        self._allocation = allocation

        # Block signals while populating to avoid triggering cellChanged
        self.tbl_allocation.blockSignals(True)
        self.tbl_allocation.setRowCount(len(classes))
        for i, cls in enumerate(classes):
            n = allocation.get(cls, 0)

            item_cls = QTableWidgetItem(str(cls))
            item_cls.setFlags(item_cls.flags() & ~Qt.ItemIsEditable)
            self.tbl_allocation.setItem(i, 0, item_cls)

            # Samples column is EDITABLE so the user can override per-class
            item_n = QTableWidgetItem(str(n))
            item_n.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.tbl_allocation.setItem(i, 1, item_n)
        self.tbl_allocation.blockSignals(False)

    def _on_allocation_edited(self, row, col):
        """Handle user editing per-class sample counts in the allocation table."""
        if col != 1:
            return

        # Read class value from column 0
        cls_item = self.tbl_allocation.item(row, 0)
        n_item = self.tbl_allocation.item(row, 1)
        if cls_item is None or n_item is None:
            return

        try:
            cls_val = int(cls_item.text())
            new_n = max(0, int(n_item.text()))
        except ValueError:
            # Revert to previous value
            old_n = self._allocation.get(int(cls_item.text()), 0)
            self.tbl_allocation.blockSignals(True)
            n_item.setText(str(old_n))
            self.tbl_allocation.blockSignals(False)
            return

        self._allocation[cls_val] = new_n

        # Update the total spinbox to reflect the sum of manual edits
        new_total = sum(self._allocation.values())
        self.spn_total_n.blockSignals(True)
        self.spn_total_n.setValue(new_total)
        self.spn_total_n.blockSignals(False)

    def _on_generate(self):
        """Launch sample generation task."""
        layer = self.cmb_raster.currentLayer()
        if not layer:
            self._show_warning("Please select a classified raster.")
            return
        if not self._pixel_counts:
            self._show_warning(
                "No classes detected. Select a valid classified raster."
            )
            return

        # Parse seed
        try:
            seed = int(self.txt_seed.text())
        except ValueError:
            self._show_warning("Invalid seed value. Enter an integer.")
            return

        # Read per-class allocation from the (possibly user-edited) table
        allocation = dict(self._allocation)
        total_n = sum(allocation.values())
        if total_n <= 0:
            self._show_warning("Total sample count is zero. Adjust allocation.")
            return

        config = {
            "raster_path": layer.source(),
            "confidence_level": self.spn_confidence.value() / 100.0,
            "expected_accuracy": self.spn_expected_acc.value() / 100.0,
            "margin_of_error": self.spn_margin.value() / 100.0,
            "allocation_method": (
                "proportional" if self.rdo_proportional.isChecked() else "equal"
            ),
            "min_distance_m": self.spn_min_distance.value(),
            "seed": seed,
            "min_per_class": 1,
            "total_n_override": total_n,
            "allocation_override": allocation,
            "class_names": {cls: str(cls) for cls in self._pixel_counts},
        }

        from ..tasks.sampling_task import SamplingTask

        task = SamplingTask(config)
        self._sampling_task = task  # prevent garbage collection

        self.btn_generate.setEnabled(False)
        self.btn_generate.setText("Generating...")

        task.taskCompleted.connect(lambda: self._on_sampling_finished(True))
        task.taskTerminated.connect(lambda: self._on_sampling_finished(False))

        QgsApplication.taskManager().addTask(task)

    def _on_sampling_finished(self, success):
        """Handle sampling task completion on the main thread."""
        self.btn_generate.setEnabled(True)
        self.btn_generate.setText("Generate Reference Sample Points")

        task = self._sampling_task
        if task is None:
            return

        if success and task.result is not None:
            self._sample_result = task.result
            self.btn_export.setEnabled(True)

            n_points = len(task.result.points)
            self.iface.messageBar().pushMessage(
                "GeoAccuRate",
                f"Generated {n_points} reference sample points "
                f"for ground truth collection",
                level=Qgis.Success, duration=5,
            )

            # Add points as a temporary memory layer
            self._add_sample_layer(task.result)

            # Show allocation warnings
            for w in task.result.warnings:
                self.iface.messageBar().pushMessage(
                    "GeoAccuRate", w, level=Qgis.Warning, duration=8,
                )
        else:
            msg = (
                str(task.exception) if task.exception
                else "Sample generation failed or was cancelled."
            )
            self._show_error(msg)

    def _add_sample_layer(self, sample_set):
        """Add sample points as a temporary memory layer to QGIS."""
        from qgis.core import (
            QgsFeature,
            QgsGeometry,
            QgsPointXY,
            QgsProject,
            QgsVectorLayer,
        )

        raster_layer = self.cmb_raster.currentLayer()
        crs_str = ""
        if raster_layer and raster_layer.crs().isValid():
            crs_str = f"?crs={raster_layer.crs().authid()}"

        uri = (
            f"Point{crs_str}"
            "&field=point_id:integer"
            "&field=map_class:integer"
            "&field=map_label:string(50)"
            "&field=ground_truth:string(50)"
            "&field=notes:string(200)"
        )
        layer = QgsVectorLayer(
            uri,
            "GeoAccuRate \u2014 Reference Sample Points",
            "memory",
        )

        features = []
        for pt in sample_set.points:
            f = QgsFeature(layer.fields())
            f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(pt.x, pt.y)))
            name = sample_set.strata_info.get(
                pt.stratum_class, {}
            ).get("name", str(pt.stratum_class))
            # map_class / map_label = what the classification raster says
            # ground_truth = blank — user fills this after field visit or
            #                checking high-res imagery
            f.setAttributes([pt.id, pt.stratum_class, name, None, None])
            features.append(f)

        layer.dataProvider().addFeatures(features)
        layer.updateExtents()
        QgsProject.instance().addMapLayer(layer)

    def _on_export(self):
        """Export generated samples to file."""
        if self._sample_result is None:
            self._show_warning("No samples to export. Generate samples first.")
            return

        fmt = self.cmb_export_format.currentText()
        if fmt == "GeoPackage":
            filter_str = "GeoPackage (*.gpkg)"
            driver = "GPKG"
        else:
            filter_str = "Shapefile (*.shp)"
            driver = "ESRI Shapefile"

        path, _ = QFileDialog.getSaveFileName(
            self, "Export Samples", "", filter_str
        )
        if not path:
            return

        # Get CRS EPSG from raster
        raster_layer = self.cmb_raster.currentLayer()
        if not raster_layer:
            self._show_warning("Raster layer no longer available.")
            return

        from ..core.raster_reader import get_raster_info

        try:
            info = get_raster_info(raster_layer.source())
            epsg = info["crs_epsg"]
        except Exception as e:
            self._show_error(f"Cannot read raster CRS: {e}")
            return

        from ..core.vector_io import export_sample_points

        try:
            class_names = {cls: str(cls) for cls in self._pixel_counts}
            export_sample_points(
                list(self._sample_result.points),
                path,
                epsg,
                class_names,
                driver,
            )
            self.iface.messageBar().pushMessage(
                "GeoAccuRate",
                f"Samples exported to: {path}",
                level=Qgis.Success, duration=5,
            )
        except Exception as e:
            self._show_error(f"Export failed: {e}")

    def _on_random_seed(self):
        """Generate a random seed value."""
        self.txt_seed.setText(str(random.randint(1, 999999)))

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
