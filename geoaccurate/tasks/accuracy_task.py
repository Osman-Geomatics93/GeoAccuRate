"""Background task for accuracy assessment.

Wraps the accuracy workflow in a QgsTask for non-blocking execution.

Depends on: qgis.core, core.accuracy_workflow.
"""

from typing import Optional

import numpy as np

from qgis.core import Qgis, QgsMessageLog, QgsTask

from ..core.accuracy_workflow import run_accuracy_assessment
from ..core.input_validator import ValidationResult
from ..domain.models import ConfusionMatrixResult, RunMetadata


class AccuracyTask(QgsTask):
    """Background task that runs a categorical accuracy assessment.

    Usage:
        task = AccuracyTask(config)
        task.completed.connect(on_done)   # custom signal
        QgsApplication.taskManager().addTask(task)
    """

    def __init__(self, config: dict):
        super().__init__("Computing accuracy metrics", QgsTask.CanCancel)

        # COPY all data before task starts — never reference GUI objects
        self.config = dict(config)
        self._classified_raster_path: str = config["classified_raster_path"]
        self._reference_points_xy: np.ndarray = config["reference_points_xy"].copy()
        self._reference_class_values: np.ndarray = config["reference_class_values"].copy()
        self._class_labels: tuple = tuple(config["class_labels"])
        self._class_names: dict = dict(config.get("class_names", {}))
        self._class_mapping: Optional[dict] = config.get("class_mapping")
        self._compute_kappa: bool = config.get("compute_kappa", False)
        self._compute_area_weighted: bool = config.get("compute_area_weighted", True)
        self._confidence_level: float = config.get("confidence_level", 0.95)
        self._plugin_version: str = config.get("plugin_version", "1.0.0")
        self._qgis_version: str = config.get("qgis_version", "")
        self._ref_layer_path: str = config.get("reference_layer_path", "")
        self._ref_layer_name: str = config.get("reference_layer_name", "")
        self._ref_field: str = config.get("reference_field", "")

        # Results (populated in run(), read in finished())
        self.result: Optional[ConfusionMatrixResult] = None
        self.validation: Optional[ValidationResult] = None
        self.metadata: Optional[RunMetadata] = None
        self.exception: Optional[Exception] = None

    def run(self) -> bool:
        """Execute in background thread. NEVER touch GUI here."""
        try:
            QgsMessageLog.logMessage(
                "Starting accuracy assessment...",
                "GeoAccuRate", Qgis.Info,
            )

            self.setProgress(10)

            if self.isCanceled():
                return False

            self.result, self.validation, self.metadata = run_accuracy_assessment(
                classified_raster_path=self._classified_raster_path,
                reference_points_xy=self._reference_points_xy,
                reference_class_values=self._reference_class_values,
                class_labels=self._class_labels,
                class_names=self._class_names,
                class_mapping=self._class_mapping,
                compute_kappa=self._compute_kappa,
                compute_area_weighted=self._compute_area_weighted,
                confidence_level=self._confidence_level,
                plugin_version=self._plugin_version,
                qgis_version=self._qgis_version,
                reference_layer_path=self._ref_layer_path,
                reference_layer_name=self._ref_layer_name,
                reference_field=self._ref_field,
            )

            self.setProgress(100)

            QgsMessageLog.logMessage(
                f"Accuracy assessment complete: OA={self.result.overall_accuracy:.1%}",
                "GeoAccuRate", Qgis.Info,
            )
            return True

        except Exception as e:
            self.exception = e
            QgsMessageLog.logMessage(
                f"Accuracy assessment failed: {e}",
                "GeoAccuRate", Qgis.Critical,
            )
            return False

    def finished(self, success: bool):
        """Called on the main thread. Safe to update GUI here."""
        if self.exception:
            QgsMessageLog.logMessage(
                f"Error: {self.exception}", "GeoAccuRate", Qgis.Critical,
            )

    def cancel(self):
        QgsMessageLog.logMessage(
            "Accuracy task cancelled", "GeoAccuRate", Qgis.Info,
        )
        super().cancel()
