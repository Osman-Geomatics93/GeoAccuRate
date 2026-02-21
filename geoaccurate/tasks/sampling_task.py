"""Background task for sample generation.

Wraps the sampling workflow in a QgsTask for non-blocking execution.
"""

from typing import Dict, Optional

from qgis.core import Qgis, QgsMessageLog, QgsTask

from ..core.sampling_workflow import run_sample_generation
from ..domain.models import SampleSet


class SamplingTask(QgsTask):
    """Background task that generates stratified random samples."""

    def __init__(self, config: dict):
        super().__init__("Generating sample points", QgsTask.CanCancel)

        self._raster_path: str = config["raster_path"]
        self._confidence_level: float = config.get("confidence_level", 0.95)
        self._expected_accuracy: float = config.get("expected_accuracy", 0.85)
        self._margin_of_error: float = config.get("margin_of_error", 0.05)
        self._allocation: str = config.get("allocation_method", "proportional")
        self._min_distance: float = config.get("min_distance_m", 0.0)
        self._seed: int = config.get("seed", 42)
        self._min_per_class: int = config.get("min_per_class", 25)
        self._total_n_override: int = config.get("total_n_override", 0)
        self._class_names: dict = dict(config.get("class_names", {}))
        self._allocation_override: Optional[Dict[int, int]] = config.get(
            "allocation_override"
        )

        self.result: Optional[SampleSet] = None
        self.exception: Optional[Exception] = None

    def run(self) -> bool:
        try:
            QgsMessageLog.logMessage(
                "Starting sample generation...",
                "GeoAccuRate", Qgis.Info,
            )

            def progress(step, total):
                if self.isCanceled():
                    raise InterruptedError("Task cancelled")
                self.setProgress(step / total * 100)

            self.result = run_sample_generation(
                raster_path=self._raster_path,
                confidence_level=self._confidence_level,
                expected_accuracy=self._expected_accuracy,
                margin_of_error=self._margin_of_error,
                allocation_method=self._allocation,
                min_distance_m=self._min_distance,
                seed=self._seed,
                min_per_class=self._min_per_class,
                class_names=self._class_names,
                progress_callback=progress,
                total_n_override=self._total_n_override or None,
                allocation_override=self._allocation_override,
            )

            QgsMessageLog.logMessage(
                f"Generated {len(self.result.points)} sample points",
                "GeoAccuRate", Qgis.Info,
            )
            return True

        except InterruptedError:
            return False
        except Exception as e:
            self.exception = e
            QgsMessageLog.logMessage(
                f"Sampling failed: {e}", "GeoAccuRate", Qgis.Critical,
            )
            return False

    def finished(self, success: bool):
        if self.exception:
            QgsMessageLog.logMessage(
                f"Error: {self.exception}", "GeoAccuRate", Qgis.Critical,
            )

    def cancel(self):
        QgsMessageLog.logMessage(
            "Sampling task cancelled", "GeoAccuRate", Qgis.Info,
        )
        super().cancel()
