from PySide6.QtCore import Qt, QMargins
from PySide6.QtGui import QColor, QPainter
from PySide6.QtCharts import QBarCategoryAxis, QBarSeries, QBarSet, QChart, QChartView
from PySide6.QtWidgets import QLabel, QFrame, QGridLayout, QVBoxLayout, QWidget

from viewer.viewer_utils import avg, format_signed, gap_value


class OverallSummaryPanel:
    def __init__(self, layout: QGridLayout, format_deviation_score):
        self.layout = layout
        self.format_deviation_score = format_deviation_score

    def update(self, rows):
        self._clear()
        self.layout.addWidget(QLabel("項目"), 0, 0)
        self.layout.addWidget(QLabel("全体"), 0, 1)

        summary_rows = [
            ("全体勝率", self._format_win_rate(rows)),
            ("平均値:平均レート差", avg([row["avg_gap"] for row in rows])),
            ("平均値:中央レート差", avg([row["median_gap"] for row in rows])),
            ("平均値:最低レート差", avg([row["min_gap"] for row in rows])),
            ("平均値:最高レート差", avg([row["max_gap"] for row in rows])),
            ("平均値:偏差値(陣営)", avg([self.format_deviation_score(row["rate_my"], row["avg_my"], row["std_my"]) for row in rows])),
            ("平均値:偏差値(全体)", avg([self.format_deviation_score(row["rate_my"], row["avg_all"], row["std_all"]) for row in rows])),
            ("平均レート差<0", self._format_rate_condition_ratio(rows, "avg_gap", lambda v: v < 0)),
            ("最低レート差<0", self._format_rate_condition_ratio(rows, "min_gap", lambda v: v < 0)),
            ("最高レート差<0", self._format_rate_condition_ratio(rows, "max_gap", lambda v: v < 0)),
            ("偏差値(陣営)>50", self._format_rate_condition_ratio(
                rows,
                "rate_dev_camp",
                lambda v: v > 50,
                value_factory=lambda row: self.format_deviation_score(row["rate_my"], row["avg_my"], row["std_my"]),
            )),
            ("有利マッチを落とす", self._format_favorable_loss_ratio(rows)),
            ("不利マッチで勝つ", self._format_unfavorable_win_ratio(rows)),
        ]

        for idx, (label_text, value) in enumerate(summary_rows, start=1):
            self.layout.addWidget(QLabel(label_text), idx, 0)
            self.layout.addWidget(self._make_value_label(value), idx, 1)

        chart_row = len(summary_rows) + 1
        charts = [
            self._build_rate_band_winrate_chart(rows, "avg_gap", "平均レート差帯別の勝率"),
            self._build_rate_band_winrate_chart(rows, "median_gap", "中央レート差帯別の勝率"),
            self._build_rate_band_winrate_chart(rows, "min_gap", "最低レート差帯別の勝率"),
        ]
        for offset, chart in enumerate(charts):
            self.layout.addWidget(chart, chart_row + offset, 0, 1, 2)

    def _clear(self):
        while self.layout.count():
            item = self.layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _make_value_label(self, value):
        label = QLabel("" if value in ("", None) else str(value))
        label.setFrameShape(QFrame.Shape.Panel)
        label.setFrameShadow(QFrame.Shadow.Sunken)
        label.setMinimumHeight(24)
        label.setStyleSheet("padding: 2px 6px; background: white;")
        return label

    def _format_win_rate(self, rows):
        if not rows:
            return ""
        win_count = sum(1 for row in rows if row["is_win"] in (1, "1", True, "win"))
        return f"{round((win_count / len(rows)) * 100, 1)}%"

    def _is_unfavorable_match(self, row):
        avg_gap = row["avg_gap"]
        try:
            avg_gap = float(avg_gap)
        except (TypeError, ValueError):
            avg_gap = None
        return avg_gap is not None and avg_gap < 0

    def _format_favorable_loss_ratio(self, rows):
        favorable_rows = [row for row in rows if not self._is_unfavorable_match(row)]
        if not favorable_rows:
            return ""
        loss_count = sum(1 for row in favorable_rows if row["is_win"] in (0, "0", False, "lose"))
        return f"{round((loss_count / len(favorable_rows)) * 100, 1)}%"

    def _format_unfavorable_win_ratio(self, rows):
        unfavorable_rows = [row for row in rows if self._is_unfavorable_match(row)]
        if not unfavorable_rows:
            return ""
        win_count = sum(1 for row in unfavorable_rows if row["is_win"] in (1, "1", True, "win"))
        return f"{round((win_count / len(unfavorable_rows)) * 100, 1)}%"

    def _format_rate_condition_ratio(self, rows, key, predicate, value_factory=None):
        if not rows:
            return ""
        matched = 0
        total = 0
        for row in rows:
            if value_factory is not None:
                value = value_factory(row)
            else:
                value = row[key]
            if value in ("", None):
                continue
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            total += 1
            if predicate(numeric):
                matched += 1
        if total == 0:
            return ""
        return f"{round((matched / total) * 100, 1)}%"

    def _build_rate_band_winrate_chart(self, rows, gap_key, title):
        bands = [0, 30, 60, 90, 120]
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self._build_rate_band_half_chart(rows, gap_key, title + " (+側)", bands, positive=True))
        layout.addWidget(self._build_rate_band_half_chart(rows, gap_key, title + " (-側)", bands, positive=False))
        return container

    def _build_rate_band_half_chart(self, rows, gap_key, title, bands, positive):
        labels = [f"{bands[i]}〜{bands[i + 1]}" for i in range(len(bands) - 1)]
        series = QBarSeries()
        values = QBarSet("win率")
        values.setColor(QColor("#0b3d91" if positive else "#8b1e1e"))
        values.setLabelColor(QColor("#ffffff"))

        for low, high in zip(bands[:-1], bands[1:]):
            band_rows = []
            for row in rows:
                gap = row.get(gap_key)
                try:
                    gap_value = float(gap)
                except (TypeError, ValueError):
                    continue
                if positive and low <= gap_value < high:
                    band_rows.append(row)
                if not positive:
                    if low == 0:
                        if gap_value == 0:
                            band_rows.append(row)
                    elif -high <= gap_value < -low:
                        band_rows.append(row)
            if not band_rows:
                values.append(0.0)
                continue
            win_count = sum(1 for row in band_rows if row["is_win"] in (1, "1", True, "win"))
            values.append(round((win_count / len(band_rows)) * 100, 1))

        series.append(values)
        chart = QChart()
        chart.addSeries(series)
        chart.setTitle(title)
        chart.legend().setVisible(True)
        chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)
        chart.setBackgroundVisible(False)

        axis_x = QBarCategoryAxis()
        axis_x.append(labels)
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(axis_x)

        from PySide6.QtCharts import QValueAxis
        axis_y = QValueAxis()
        axis_y.setRange(0, 100)
        axis_y.setTickCount(6)
        axis_y.setLabelFormat("%d%%")
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_y)
        chart.setMargins(QMargins(18, 18, 18, 18))

        view = QChartView(chart)
        view.setRenderHint(QPainter.RenderHint.Antialiasing)
        view.setMinimumHeight(240)
        return view
