"""Background task for PDF report generation."""

from typing import Optional

from qgis.core import Qgis, QgsMessageLog, QgsTask

from ..domain.models import ReportContent


class ReportTask(QgsTask):
    """Background task that generates a PDF report."""

    def __init__(self, content: ReportContent, output_path: str):
        super().__init__("Generating PDF report", QgsTask.CanCancel)

        self._content = content
        self._output_path = output_path
        self.output_path: Optional[str] = None
        self.exception: Optional[Exception] = None

    def run(self) -> bool:
        try:
            from ..reporting.pdf_builder import generate_pdf

            self.setProgress(10)

            if self.isCanceled():
                return False

            self.output_path = generate_pdf(self._content, self._output_path)
            self.setProgress(100)

            QgsMessageLog.logMessage(
                f"Report saved: {self.output_path}",
                "GeoAccuRate", Qgis.Info,
            )
            return True

        except Exception as e:
            self.exception = e
            QgsMessageLog.logMessage(
                f"Report generation failed: {e}",
                "GeoAccuRate", Qgis.Critical,
            )
            return False

    def finished(self, success: bool):
        if self.exception:
            QgsMessageLog.logMessage(
                f"Error: {self.exception}", "GeoAccuRate", Qgis.Critical,
            )
