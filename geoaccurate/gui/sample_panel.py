"""Sample design and generation panel.

Wires GUI controls to existing QgsTask workflows for sample size
calculation, stratified random sampling, and export.
"""

import math
import random

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
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
from qgis.gui import QgsMapLayerComboBox, QgsRubberBand
from qgis.core import (
    Qgis,
    QgsApplication,
    QgsGeometry,
    QgsMapLayerProxyModel,
    QgsPointXY,
    QgsWkbTypes,
)

# Cross-version layer filter compatibility (3.34 vs 3.44+)
try:
    _RasterFilter = Qgis.LayerFilter.RasterLayer
except AttributeError:
    _RasterFilter = QgsMapLayerProxyModel.RasterLayer

_DEFAULT_PTS_PER_SHAPE = 50


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
        self._class_names = {}
        self._class_colors = {}
        self._recommended_n = 0
        self._allocation = {}
        self._sample_result = None
        self._sampling_task = None

        # AOI state
        self._aoi_geometries = []   # list of QgsGeometry polygons
        self._aoi_rubber_bands = [] # persistent rubber bands on canvas
        self._aoi_labels = []       # display names ("Rect 1", "Circle 1", ...)
        self._aoi_desired_n = []    # desired point count per shape
        self._rect_count = 0
        self._circle_count = 0
        self._polygon_count = 0
        self._prev_map_tool = None
        self._rect_tool = None
        self._circle_tool = None
        self._polygon_tool = None

        self._setup_ui()
        self._connect_signals()

        # Clean up rubber bands when project changes or widget is destroyed
        from qgis.core import QgsProject
        QgsProject.instance().cleared.connect(self._on_clear_aois)
        self.destroyed.connect(self._on_clear_aois)

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

        self.tbl_strata = QTableWidget(0, 5)
        self.tbl_strata.setHorizontalHeaderLabels(["", "Class", "Name", "Pixels", "%"])
        self.tbl_strata.setColumnWidth(0, 30)
        self.tbl_strata.setColumnWidth(1, 60)
        self.tbl_strata.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        input_layout.addWidget(self.tbl_strata)

        layout.addWidget(input_group)

        # -- Areas of Interest --
        aoi_group = QGroupBox("Areas of Interest (optional)")
        aoi_layout = QVBoxLayout(aoi_group)

        aoi_hint = QLabel("Draw shapes on the map to restrict sampling area")
        aoi_hint.setWordWrap(True)
        aoi_hint.setStyleSheet("color: gray; font-style: italic;")
        aoi_layout.addWidget(aoi_hint)

        aoi_btn_row = QHBoxLayout()
        self.btn_draw_rect = QPushButton("Rectangle")
        self.btn_draw_rect.setToolTip("Draw a rectangle AOI on the map canvas")
        self.btn_draw_circle = QPushButton("Circle")
        self.btn_draw_circle.setToolTip("Draw a circle AOI on the map canvas")
        self.btn_draw_polygon = QPushButton("Polygon")
        self.btn_draw_polygon.setToolTip(
            "Draw a free polygon: left-click to add vertices, right-click to finish"
        )
        self.btn_delete_aoi = QPushButton("Delete")
        self.btn_delete_aoi.setToolTip("Delete the selected AOI shape")
        self.btn_clear_aois = QPushButton("Clear All")
        self.btn_clear_aois.setToolTip("Remove all AOI shapes from the map")
        aoi_btn_row.addWidget(self.btn_draw_rect)
        aoi_btn_row.addWidget(self.btn_draw_circle)
        aoi_btn_row.addWidget(self.btn_draw_polygon)
        aoi_btn_row.addWidget(self.btn_delete_aoi)
        aoi_btn_row.addWidget(self.btn_clear_aois)
        aoi_layout.addLayout(aoi_btn_row)

        # Table: Shape | Points (editable) | Generated
        self.tbl_aois = QTableWidget(0, 3)
        self.tbl_aois.setHorizontalHeaderLabels(["Shape", "Points", "Generated"])
        self.tbl_aois.setMaximumHeight(110)
        self.tbl_aois.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.Stretch
        )
        self.tbl_aois.setColumnWidth(1, 60)
        self.tbl_aois.setColumnWidth(2, 70)
        aoi_layout.addWidget(self.tbl_aois)

        self.lbl_aoi_total = QLabel("")
        self.lbl_aoi_total.setStyleSheet("font-weight: bold;")
        aoi_layout.addWidget(self.lbl_aoi_total)

        layout.addWidget(aoi_group)

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
        self.btn_draw_rect.clicked.connect(self._on_draw_rectangle)
        self.btn_draw_circle.clicked.connect(self._on_draw_circle)
        self.btn_draw_polygon.clicked.connect(self._on_draw_polygon)
        self.btn_delete_aoi.clicked.connect(self._on_delete_selected_aoi)
        self.btn_clear_aois.clicked.connect(self._on_clear_aois)
        self.tbl_aois.cellChanged.connect(self._on_aoi_points_edited)

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------

    def _on_raster_changed(self, layer):
        """Detect classes and pixel counts when raster selection changes."""
        self.lbl_raster_status.setText("")
        self._on_clear_aois()

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

        # Extract class names and colors from the raster renderer
        class_names, class_colors = self._get_class_info_from_renderer(layer)

        # Store for use elsewhere (export, allocation table, etc.)
        self._class_names = class_names
        self._class_colors = class_colors

        # Populate strata table
        total = sum(self._pixel_counts.values())

        self.lbl_classes.setText(f"Classes detected: {n_classes}")
        self.tbl_strata.setRowCount(n_classes)

        for i, cls in enumerate(classes):
            count = self._pixel_counts[cls]
            pct = count / total * 100 if total > 0 else 0

            chk = QCheckBox()
            chk.setChecked(cls != 0)
            chk.stateChanged.connect(lambda _: self._update_sample_size())
            self.tbl_strata.setCellWidget(i, 0, chk)

            # Class value with color swatch background
            item_cls = QTableWidgetItem(str(cls))
            item_cls.setTextAlignment(Qt.AlignCenter)
            item_cls.setFlags(item_cls.flags() & ~Qt.ItemIsEditable)
            color = class_colors.get(cls)
            if color:
                from qgis.PyQt.QtGui import QBrush
                item_cls.setBackground(QBrush(color))
                # Smart text contrast
                lum = 0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue()
                item_cls.setForeground(QBrush(QColor(255, 255, 255) if lum < 128 else QColor(0, 0, 0)))
            self.tbl_strata.setItem(i, 1, item_cls)

            # Class name
            name = class_names.get(cls, "")
            item_name = QTableWidgetItem(name)
            item_name.setFlags(item_name.flags() & ~Qt.ItemIsEditable)
            self.tbl_strata.setItem(i, 2, item_name)

            item_pix = QTableWidgetItem(f"{count:,}")
            item_pix.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            item_pix.setFlags(item_pix.flags() & ~Qt.ItemIsEditable)
            self.tbl_strata.setItem(i, 3, item_pix)

            item_pct = QTableWidgetItem(f"{pct:.1f}")
            item_pct.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            item_pct.setFlags(item_pct.flags() & ~Qt.ItemIsEditable)
            self.tbl_strata.setItem(i, 4, item_pct)

        # Fit all rows (30px each + header), scrollbar kicks in past 300px
        ideal = 30 + 30 * n_classes + 2
        self.tbl_strata.setFixedHeight(min(ideal, 300))

        self._update_sample_size()

    def _get_enabled_pixel_counts(self):
        """Return pixel counts for only the checked classes in the strata table."""
        enabled = {}
        for row in range(self.tbl_strata.rowCount()):
            chk = self.tbl_strata.cellWidget(row, 0)
            if chk is not None and chk.isChecked():
                cls_item = self.tbl_strata.item(row, 1)
                if cls_item is not None:
                    cls_val = int(cls_item.text())
                    if cls_val in self._pixel_counts:
                        enabled[cls_val] = self._pixel_counts[cls_val]
        return enabled

    def _update_sample_size(self):
        """Recalculate recommended sample size from calculator inputs."""
        if not self._pixel_counts:
            self.lbl_recommended_n.setText("Recommended: \u2014")
            self._recommended_n = 0
            self._update_allocation()
            return

        from ..domain.sample_size import calculate_sample_size

        enabled = self._get_enabled_pixel_counts()
        if not enabled:
            self.lbl_recommended_n.setText("Recommended: \u2014")
            self._recommended_n = 0
            self._update_allocation()
            return

        confidence = self.spn_confidence.value() / 100.0
        expected_acc = self.spn_expected_acc.value() / 100.0
        margin = self.spn_margin.value() / 100.0
        total_pixels = sum(enabled.values())

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
        enabled = self._get_enabled_pixel_counts()
        if not enabled or total_n <= 0:
            self.tbl_allocation.setRowCount(0)
            self._allocation = {}
            return

        from ..domain.sample_size import allocate_equal, allocate_proportional

        classes = sorted(enabled.keys())
        k = len(classes)

        # Scale min_per_class to respect the user's chosen total.
        # Default 25 (Olofsson), but reduce if total is too small.
        min_per_class = min(25, max(1, total_n // k))

        try:
            if self.rdo_proportional.isChecked():
                allocation, warnings = allocate_proportional(
                    total_n, enabled, min_per_class=min_per_class
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
        names = getattr(self, "_class_names", {})
        colors = getattr(self, "_class_colors", {})
        for i, cls in enumerate(classes):
            n = allocation.get(cls, 0)

            label = names.get(cls, str(cls))
            display = f"{cls} — {label}" if label and label != str(cls) else str(cls)
            item_cls = QTableWidgetItem(display)
            item_cls.setFlags(item_cls.flags() & ~Qt.ItemIsEditable)
            color = colors.get(cls)
            if color:
                from qgis.PyQt.QtGui import QBrush
                item_cls.setBackground(QBrush(color))
                lum = 0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue()
                item_cls.setForeground(QBrush(QColor(255, 255, 255) if lum < 128 else QColor(0, 0, 0)))
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

        # Read class value from column 0 (may be "4 — Cotton" format)
        cls_item = self.tbl_allocation.item(row, 0)
        n_item = self.tbl_allocation.item(row, 1)
        if cls_item is None or n_item is None:
            return

        try:
            cls_text = cls_item.text().split("\u2014")[0].strip()
            cls_val = int(cls_text)
            new_n = max(0, int(n_item.text()))
        except ValueError:
            # Revert to previous value
            try:
                cls_text = cls_item.text().split("\u2014")[0].strip()
                old_n = self._allocation.get(int(cls_text), 0)
            except (ValueError, KeyError):
                old_n = 0
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

        # When AOIs are defined, over-generate so enough points fall in shapes
        if self._aoi_geometries:
            total_aoi_desired = sum(self._aoi_desired_n)
            if total_aoi_desired <= 0:
                self._show_warning(
                    "AOI point counts are all zero. "
                    "Set desired points per shape in the AOI table."
                )
                return
            overfactor = self._compute_overgeneration_factor(layer)
            # Scale each class proportionally but ensure a generous total
            min_candidates = total_aoi_desired * overfactor
            current_total = sum(allocation.values())
            if current_total > 0:
                scale = max(overfactor, min_candidates / current_total)
            else:
                scale = overfactor
            allocation = {
                cls: max(1, math.ceil(n * scale))
                for cls, n in allocation.items()
            }
            total_n = sum(allocation.values())

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
            "class_names": {
                cls: getattr(self, "_class_names", {}).get(cls, str(cls))
                for cls in allocation
            },
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
            result = task.result

            # Filter and select points per AOI if any are defined
            if self._aoi_geometries:
                selected = self._select_points_per_aoi(result.points)
                self._update_aoi_generated_counts(selected)
                from ..domain.models import SampleSet
                result = SampleSet(
                    design=result.design,
                    points=tuple(selected),
                    strata_info=result.strata_info,
                    warnings=result.warnings,
                )

            self._sample_result = result
            self.btn_export.setEnabled(True)

            n_points = len(result.points)
            self.iface.messageBar().pushMessage(
                "GeoAccuRate",
                f"Generated {n_points} reference sample points "
                f"for ground truth collection",
                level=Qgis.Success, duration=5,
            )

            # Add points as a temporary memory layer
            self._add_sample_layer(result)

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
            class_names = {
                cls: getattr(self, "_class_names", {}).get(cls, str(cls))
                for cls in self._pixel_counts
            }
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
    # AOI drawing
    # ------------------------------------------------------------------

    def _on_draw_rectangle(self):
        """Activate the rectangle drawing tool on the map canvas."""
        from .aoi_map_tool import RectangleDrawTool

        canvas = self.iface.mapCanvas()
        self._prev_map_tool = canvas.mapTool()

        if self._rect_tool is None:
            self._rect_tool = RectangleDrawTool(canvas)
            self._rect_tool.shapeDrawn.connect(self._on_shape_drawn)

        canvas.setMapTool(self._rect_tool)

    def _on_draw_circle(self):
        """Activate the circle drawing tool on the map canvas."""
        from .aoi_map_tool import CircleDrawTool

        canvas = self.iface.mapCanvas()
        self._prev_map_tool = canvas.mapTool()

        if self._circle_tool is None:
            self._circle_tool = CircleDrawTool(canvas)
            self._circle_tool.shapeDrawn.connect(self._on_shape_drawn)

        canvas.setMapTool(self._circle_tool)

    def _on_draw_polygon(self):
        """Activate the polygon drawing tool on the map canvas."""
        from .aoi_map_tool import PolygonDrawTool

        canvas = self.iface.mapCanvas()
        self._prev_map_tool = canvas.mapTool()

        if self._polygon_tool is None:
            self._polygon_tool = PolygonDrawTool(canvas)
            self._polygon_tool.shapeDrawn.connect(self._on_shape_drawn)

        canvas.setMapTool(self._polygon_tool)

    def _on_shape_drawn(self, geometry, label_prefix):
        """Handle a completed AOI shape from a map tool."""
        if label_prefix == "Rect":
            self._rect_count += 1
            label = f"Rect {self._rect_count}"
        elif label_prefix == "Circle":
            self._circle_count += 1
            label = f"Circle {self._circle_count}"
        else:
            self._polygon_count += 1
            label = f"Polygon {self._polygon_count}"

        self._aoi_geometries.append(geometry)
        self._aoi_labels.append(label)
        self._aoi_desired_n.append(_DEFAULT_PTS_PER_SHAPE)

        # Add persistent rubber band to canvas
        canvas = self.iface.mapCanvas()
        rb = QgsRubberBand(canvas, QgsWkbTypes.PolygonGeometry)
        rb.setColor(QColor(0, 120, 215, 50))
        rb.setStrokeColor(QColor(0, 120, 215))
        rb.setWidth(2)
        rb.setToGeometry(geometry, None)
        self._aoi_rubber_bands.append(rb)

        # Add row to AOI table
        self._refresh_aoi_table()
        self._sync_aoi_total()

        # Restore previous map tool
        if self._prev_map_tool is not None:
            canvas.setMapTool(self._prev_map_tool)
            self._prev_map_tool = None

    def _on_delete_selected_aoi(self):
        """Delete the currently selected AOI shape from the table and canvas."""
        row = self.tbl_aois.currentRow()
        if row < 0 or row >= len(self._aoi_geometries):
            self._show_warning("Select a shape in the AOI table to delete.")
            return

        # Remove rubber band from canvas
        canvas = self.iface.mapCanvas()
        canvas.scene().removeItem(self._aoi_rubber_bands[row])

        # Remove from all state lists
        del self._aoi_geometries[row]
        del self._aoi_rubber_bands[row]
        del self._aoi_labels[row]
        del self._aoi_desired_n[row]

        # Rebuild the table
        self._refresh_aoi_table()
        self._sync_aoi_total()

    def _refresh_aoi_table(self):
        """Rebuild the AOI table from current state."""
        self.tbl_aois.blockSignals(True)
        self.tbl_aois.setRowCount(len(self._aoi_labels))
        for i, label in enumerate(self._aoi_labels):
            # Shape name (read-only)
            item_name = QTableWidgetItem(label)
            item_name.setFlags(item_name.flags() & ~Qt.ItemIsEditable)
            self.tbl_aois.setItem(i, 0, item_name)

            # Desired points (editable)
            item_n = QTableWidgetItem(str(self._aoi_desired_n[i]))
            item_n.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.tbl_aois.setItem(i, 1, item_n)

            # Generated (read-only, filled after generation)
            item_gen = QTableWidgetItem("\u2014")
            item_gen.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            item_gen.setFlags(item_gen.flags() & ~Qt.ItemIsEditable)
            self.tbl_aois.setItem(i, 2, item_gen)
        self.tbl_aois.blockSignals(False)

    def _on_aoi_points_edited(self, row, col):
        """Handle user editing desired point count in AOI table."""
        if col != 1 or row >= len(self._aoi_desired_n):
            return
        item = self.tbl_aois.item(row, 1)
        if item is None:
            return
        try:
            new_n = max(0, int(item.text()))
        except ValueError:
            self.tbl_aois.blockSignals(True)
            item.setText(str(self._aoi_desired_n[row]))
            self.tbl_aois.blockSignals(False)
            return
        self._aoi_desired_n[row] = new_n
        self._sync_aoi_total()

    def _sync_aoi_total(self):
        """Update the AOI total label and Total samples spinbox from per-shape counts."""
        if not self._aoi_desired_n:
            self.lbl_aoi_total.setText("")
            return
        total = sum(self._aoi_desired_n)
        self.lbl_aoi_total.setText(f"AOI Total: {total} pts")
        self.spn_total_n.blockSignals(True)
        self.spn_total_n.setValue(total)
        self.spn_total_n.blockSignals(False)

    def _on_clear_aois(self):
        """Remove all AOI shapes from the canvas and clear state."""
        canvas = self.iface.mapCanvas()
        for rb in self._aoi_rubber_bands:
            canvas.scene().removeItem(rb)
        self._aoi_rubber_bands.clear()
        self._aoi_geometries.clear()
        self._aoi_labels.clear()
        self._aoi_desired_n.clear()
        self._rect_count = 0
        self._circle_count = 0
        self._polygon_count = 0
        self.tbl_aois.setRowCount(0)
        self.lbl_aoi_total.setText("")

    def _compute_overgeneration_factor(self, raster_layer):
        """Estimate how much to over-generate so enough points land in AOIs.

        Uses ratio of raster extent area to AOI area with a generous safety
        margin. Classified pixels are often a fraction of the extent, so the
        actual ratio of candidates landing in AOIs may be better than the
        extent-based estimate. The 3x safety margin accounts for this.
        """
        extent = raster_layer.extent()
        raster_area = extent.width() * extent.height()
        if raster_area <= 0:
            return 20

        aoi_union = QgsGeometry.unaryUnion(self._aoi_geometries)
        aoi_area = aoi_union.area()
        if aoi_area <= 0:
            return 20

        ratio = raster_area / aoi_area
        # 3x safety margin, clamp between 10x and 500x
        return max(10, min(500, math.ceil(ratio * 3)))

    def _select_points_per_aoi(self, all_points):
        """For each AOI, pick up to its desired number of points.

        Points are consumed: once assigned to an AOI they aren't reused,
        preventing duplicates when shapes overlap.
        """
        rng = random.Random(42)
        used_ids = set()
        selected = []

        for i, geom in enumerate(self._aoi_geometries):
            desired = self._aoi_desired_n[i]
            candidates = [
                p for p in all_points
                if p.id not in used_ids
                and geom.contains(QgsPointXY(p.x, p.y))
            ]
            rng.shuffle(candidates)
            picked = candidates[:desired]
            for p in picked:
                used_ids.add(p.id)
            selected.extend(picked)

        # Re-number IDs sequentially
        from ..domain.models import SamplePoint
        renumbered = []
        for idx, p in enumerate(selected, start=1):
            renumbered.append(SamplePoint(
                id=idx, x=p.x, y=p.y, stratum_class=p.stratum_class,
            ))
        return renumbered

    def _update_aoi_generated_counts(self, selected_points):
        """Update the 'Generated' column in the AOI table."""
        self.tbl_aois.blockSignals(True)
        for i, geom in enumerate(self._aoi_geometries):
            # Count how many of the selected points fall in this shape
            count = sum(
                1 for p in selected_points
                if geom.contains(QgsPointXY(p.x, p.y))
            )
            item = self.tbl_aois.item(i, 2)
            if item is not None:
                item.setText(str(count))
        self.tbl_aois.blockSignals(False)

    # ------------------------------------------------------------------
    # Raster class info
    # ------------------------------------------------------------------

    def _get_class_info_from_renderer(self, layer):
        """Extract class names and colors from the raster layer renderer.

        Supports QgsPalettedRasterRenderer (classified rasters).
        Falls back to GDAL color table / category names if renderer
        doesn't provide labels.

        Returns:
            (class_names, class_colors): dicts mapping class_value -> str/QColor
        """
        class_names = {}
        class_colors = {}

        if layer is None:
            return class_names, class_colors

        renderer = layer.renderer()
        if renderer is not None:
            # Try paletted renderer (most common for classified rasters)
            try:
                for entry in renderer.classes():
                    val = int(entry.value)
                    if entry.label:
                        class_names[val] = entry.label
                    class_colors[val] = QColor(entry.color)
                if class_names:
                    return class_names, class_colors
            except (AttributeError, TypeError):
                pass

        # Fallback: GDAL color table and category names
        try:
            from osgeo import gdal
            ds = gdal.OpenEx(layer.source(), gdal.OF_RASTER | gdal.OF_READONLY)
            if ds:
                band = ds.GetRasterBand(1)
                cat_names = band.GetCategoryNames()
                ct = band.GetColorTable()
                if cat_names:
                    for i, name in enumerate(cat_names):
                        if name:
                            class_names[i] = name
                if ct:
                    for i in range(ct.GetCount()):
                        entry = ct.GetColorEntry(i)
                        class_colors[i] = QColor(entry[0], entry[1], entry[2], entry[3] if len(entry) > 3 else 255)
                ds = None
        except Exception:
            pass

        return class_names, class_colors

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
