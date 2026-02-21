"""Results display dialogs for GeoAccuRate.

Provides simple QDialog wrappers to show confusion matrix
and per-class metrics in table form.
"""

import math

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QBrush, QColor
from qgis.PyQt.QtWidgets import (
    QDialog,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ..domain.models import ConfusionMatrixResult


class ConfusionMatrixDialog(QDialog):
    """Dialog showing confusion matrix as a table."""

    def __init__(self, result: ConfusionMatrixResult, parent=None):
        super().__init__(parent)
        self.setWindowTitle("GeoAccuRate — Confusion Matrix")
        self.setMinimumSize(500, 400)
        self._build_ui(result)

    def _build_ui(self, result):
        layout = QVBoxLayout(self)

        labels = [result.class_names.get(lbl, str(lbl)) for lbl in result.class_labels]
        k = len(labels)
        matrix = result.matrix

        table = QTableWidget(k + 1, k + 1)
        table.setHorizontalHeaderLabels(labels + ["Row Total"])
        table.setVerticalHeaderLabels(labels + ["Col Total"])

        diag_color = QBrush(QColor(217, 243, 217))

        for i in range(k):
            for j in range(k):
                item = QTableWidgetItem(str(int(matrix[i, j])))
                item.setTextAlignment(Qt.AlignCenter)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                if i == j:
                    item.setBackground(diag_color)
                table.setItem(i, j, item)

            row_total = QTableWidgetItem(str(int(matrix[i, :].sum())))
            row_total.setTextAlignment(Qt.AlignCenter)
            row_total.setFlags(row_total.flags() & ~Qt.ItemIsEditable)
            table.setItem(i, k, row_total)

        for j in range(k):
            col_total = QTableWidgetItem(str(int(matrix[:, j].sum())))
            col_total.setTextAlignment(Qt.AlignCenter)
            col_total.setFlags(col_total.flags() & ~Qt.ItemIsEditable)
            table.setItem(k, j, col_total)

        grand = QTableWidgetItem(str(int(matrix.sum())))
        grand.setTextAlignment(Qt.AlignCenter)
        grand.setFlags(grand.flags() & ~Qt.ItemIsEditable)
        table.setItem(k, k, grand)

        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.verticalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(table)

        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.close)
        layout.addWidget(btn_close)


class PerClassMetricsDialog(QDialog):
    """Dialog showing per-class accuracy metrics."""

    def __init__(self, result: ConfusionMatrixResult, parent=None):
        super().__init__(parent)
        self.setWindowTitle("GeoAccuRate — Per-Class Metrics")
        self.setMinimumSize(650, 400)
        self._build_ui(result)

    def _build_ui(self, result):
        layout = QVBoxLayout(self)

        headers = ["Class", "PA", "PA CI", "UA", "UA CI", "F1"]
        k = len(result.class_labels)
        table = QTableWidget(k, len(headers))
        table.setHorizontalHeaderLabels(headers)

        for i, label in enumerate(result.class_labels):
            name = result.class_names.get(label, str(label))
            pa = result.producers_accuracy.get(label, float("nan"))
            ua = result.users_accuracy.get(label, float("nan"))
            f1 = result.f1_per_class.get(label, float("nan"))
            pa_ci = result.producers_accuracy_ci.get(
                label, (float("nan"), float("nan"))
            )
            ua_ci = result.users_accuracy_ci.get(
                label, (float("nan"), float("nan"))
            )

            def _fmt(v):
                return f"{v:.1%}" if not math.isnan(v) else "\u2014"

            def _fmt_ci(ci):
                lo, hi = ci
                return f"{lo:.1%}\u2013{hi:.1%}" if not math.isnan(lo) else "\u2014"

            values = [
                name,
                _fmt(pa),
                _fmt_ci(pa_ci),
                _fmt(ua),
                _fmt_ci(ua_ci),
                _fmt(f1),
            ]
            for j, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignCenter)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                table.setItem(i, j, item)

        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(table)

        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.close)
        layout.addWidget(btn_close)
