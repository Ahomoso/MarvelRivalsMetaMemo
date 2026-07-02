import sqlite3
import sys
import time
from dataclasses import dataclass

from PySide6.QtCore import Qt, QMargins, QEvent
from PySide6.QtGui import QBrush, QColor, QFont, QPainter
from functools import partial

from PySide6.QtCharts import QBarCategoryAxis, QBarSeries, QBarSet, QChart, QChartView
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QButtonGroup,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QFrame,
    QRadioButton,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from config import load_config, resolve_path
from debug_utils import debug_print
from sql_utils import load_sql
from viewer.list_modes import AllListMode, ListQueryContext, PlayerListMode
from viewer.match_detail_dialog import MatchDetailWindow
from viewer.viewer_utils import (
    avg,
    format_signed,
    gap,
    gap_value,
    get_int_or_none,
    max_value,
    median,
    min_value,
    std,
    variance,
)


CONFIG = load_config()
DB_PATH = resolve_path(CONFIG.database_path)
DEFAULT_PLAYER_UID = int(CONFIG.default_player_uid)
TOP500_FIELDS = {
    "KDA": "top500_kda",
    "ダメージ/分": "top500_damage_per_minutes",
    "被ダメージ/分": "top500_damage_taken_per_minutes",
    "回復/分": "top500_healing_per_minutes",
}
SQL_MATCH_LIST = load_sql("viewer/viewer_load_matches_by_player.sql")
SQL_MATCH_LIST_ALL = load_sql("viewer/viewer_load_matches_all.sql")
SQL_MATCH_COUNT = load_sql("viewer/viewer_load_match_count_by_player.sql")
SQL_MATCH_COUNT_ALL = load_sql("viewer/viewer_load_match_count_all.sql")
SQL_SELF_CAMP = load_sql("viewer/viewer_self_camp.sql")
SQL_MATCH_RESULT = load_sql("viewer/viewer_match_result.sql")
SQL_MATCH_PLAYERS_RATES = load_sql("viewer/viewer_match_players_rates.sql")
SQL_IS_PLAYER_IN_CAMP = load_sql("viewer/viewer_is_player_in_camp.sql")
SQL_MATCH_DETAIL_PLAYERS = load_sql("viewer/viewer_match_detail_players.sql")
SQL_PLAYER_PARTY_ID = load_sql("viewer/viewer_get_party_id.sql")
SQL_CURRENT_RATE = load_sql("viewer/viewer_get_current_rate.sql")
SQL_TOP500_STATS = load_sql("viewer/viewer_get_top500_stats.sql")
SQL_HAS_PARTY_IN_MATCH_CAMP = """
SELECT 1
FROM match_players_tbl AS mp
JOIN party_member_mst AS pm
  ON pm.player_uid = mp.player_uid
WHERE mp.match_uid = ?
  AND mp.camp = ?
  AND pm.party_id = ?
GROUP BY pm.party_id
HAVING COUNT(*) >= 2
LIMIT 1
"""


@dataclass
class SearchState:
    player_id: str = ""
    player_name: str = ""
    duo_player_id: str = ""
    duo_player_name: str = ""


class MatchListTableWidget(QTableWidget):
    def __init__(self, owner, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._owner = owner
        self.setMouseTracking(True)

    def mouseDoubleClickEvent(self, event):
        index = self.indexAt(event.position().toPoint())
        if self._is_detail_column(index):
            self._owner._open_match_detail_from_row(index.row())
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event):
        index = self.indexAt(event.position().toPoint())
        if event.button() == Qt.MouseButton.LeftButton and self._is_detail_column(index):
            self._owner._open_match_detail_from_row(index.row())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        index = self.indexAt(event.position().toPoint())
        if self._is_detail_column(index):
            self.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.viewport().unsetCursor()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self.viewport().unsetCursor()
        super().leaveEvent(event)

    def _is_detail_column(self, index):
        if not index.isValid():
            return False
        item = self.item(index.row(), index.column())
        return item is not None and item.text() == "詳細"


class ViewerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(CONFIG.viewer_title)
        self.resize(980, 860)
        self.state = SearchState()
        self.main_view_mode = "list"
        self.list_detail_mode = "rate"
        self.summary_mode = "stats"
        self.list_mode = PlayerListMode()
        self._build_ui()
        self._apply_theme()
        self.reload_all()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        title = QLabel("試合一覧画面")
        title.setObjectName("pageTitle")
        title.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        root.addWidget(title)

        top = QVBoxLayout()
        top.setSpacing(8)

        self.search_toggle_button = QPushButton("▲ 検索条件")
        self.search_toggle_button.setCheckable(True)
        self.search_toggle_button.setChecked(False)
        self.search_toggle_button.toggled.connect(self._toggle_search_panel)
        self.search_toggle_button.setObjectName("toggleButton")
        top.addWidget(self.search_toggle_button)

        self.search_panel = QWidget()
        search_panel_layout = QVBoxLayout(self.search_panel)
        search_panel_layout.setContentsMargins(0, 0, 0, 0)
        search_panel_layout.setSpacing(8)
        top.addWidget(self.search_panel)

        row1 = QHBoxLayout()
        row1.setSpacing(12)
        self.search_mode_box = QGroupBox("検索モード")
        search_mode_outer = QVBoxLayout(self.search_mode_box)
        self.search_mode_box.setFixedSize(240, 120)
        search_mode_top = QHBoxLayout()
        self.search_mode_player_radio = QRadioButton("プレイヤー")
        self.search_mode_all_radio = QRadioButton("全件")
        self.search_mode_player_radio.setChecked(True)
        self.search_mode_player_radio.toggled.connect(self._update_search_mode_enabled)
        self.search_mode_all_radio.toggled.connect(self._update_search_mode_enabled)
        search_mode_top.addWidget(self.search_mode_player_radio)
        search_mode_top.addWidget(self.search_mode_all_radio)
        search_mode_top.addStretch(1)
        search_mode_outer.addLayout(search_mode_top)
        search_mode_input = QGridLayout()
        search_mode_input.setHorizontalSpacing(8)
        search_mode_input.setVerticalSpacing(4)
        search_mode_input.addWidget(QLabel("プレイヤーUID"), 0, 0)
        self.player_id_edit = QLineEdit()
        self.player_id_edit.setText(CONFIG.default_player_uid)
        self.player_id_edit.setMaximumWidth(180)
        search_mode_input.addWidget(self.player_id_edit, 0, 1)
        search_mode_outer.addLayout(search_mode_input)
        row1.addWidget(self.search_mode_box)

        self.duo_box = QGroupBox("パーティ")
        duo_outer = QVBoxLayout(self.duo_box)
        self.duo_box.setFixedSize(140, 120)

        duo_checks = QVBoxLayout()
        self.duo_all_radio = QRadioButton("ALL")
        self.duo_circle_radio = QRadioButton("〇")
        self.duo_cross_radio = QRadioButton("×")
        self.duo_all_radio.setChecked(True)
        self.duo_circle_radio.toggled.connect(self._update_duo_inputs_enabled)
        self.duo_cross_radio.toggled.connect(self._update_duo_inputs_enabled)
        self.duo_all_radio.toggled.connect(self._update_duo_inputs_enabled)
        duo_checks.addWidget(self.duo_all_radio)
        duo_checks.addWidget(self.duo_circle_radio)
        duo_checks.addWidget(self.duo_cross_radio)
        duo_checks.addStretch(1)
        duo_outer.addLayout(duo_checks)

        row1.addWidget(self.duo_box)
        self.result_box = QGroupBox("勝敗")
        result_outer = QVBoxLayout(self.result_box)
        self.result_box.setFixedSize(180, 120)
        self.result_all_radio = QRadioButton("ALL")
        self.result_win_radio = QRadioButton("Win")
        self.result_lose_radio = QRadioButton("Lose")
        self.result_all_radio.setChecked(True)
        self.result_all_radio.toggled.connect(self._update_result_inputs_enabled)
        self.result_win_radio.toggled.connect(self._update_result_inputs_enabled)
        self.result_lose_radio.toggled.connect(self._update_result_inputs_enabled)
        result_outer.addWidget(self.result_all_radio)
        result_outer.addWidget(self.result_win_radio)
        result_outer.addWidget(self.result_lose_radio)
        result_outer.addStretch(1)
        row1.addWidget(self.result_box)
        row1.addStretch(1)
        search_panel_layout.addLayout(row1)

        row3 = QGridLayout()
        self.clear_button = QPushButton("クリア")
        self.clear_button.setObjectName("clearButton")
        self.clear_button.clicked.connect(self._reset_search_conditions_to_default)
        self.clear_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        row3.addWidget(self.clear_button, 0, 0, 1, 2)
        row3.setColumnStretch(0, 1)
        row3.setColumnStretch(1, 1)
        search_panel_layout.addLayout(row3)

        row4 = QGridLayout()
        self.search_button = QPushButton("検索実行")
        self.search_button.clicked.connect(self.reload_all)
        self.search_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        row4.addWidget(self.search_button, 0, 0, 1, 2)
        row4.setColumnStretch(0, 1)
        row4.setColumnStretch(1, 1)
        search_panel_layout.addLayout(row4)

        view_mode_box = QGroupBox("表示切替")
        view_mode_layout = QHBoxLayout(view_mode_box)
        view_mode_box.setFixedSize(180, 70)
        self.view_mode_list = QRadioButton("一覧")
        self.view_mode_summary = QRadioButton("総括")
        self.view_mode_list.setChecked(True)
        self.view_mode_list.toggled.connect(self._on_main_view_mode_changed)
        self.view_mode_summary.toggled.connect(self._on_main_view_mode_changed)
        view_mode_layout.addWidget(self.view_mode_list)
        view_mode_layout.addWidget(self.view_mode_summary)
        view_mode_layout.addStretch(1)
        top.addWidget(view_mode_box)
        top_widget = QWidget()
        top_widget.setLayout(top)
        top_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        root.addWidget(top_widget)

        self._update_duo_inputs_enabled()

        self.list_box = QGroupBox("一覧グリッド")
        box_layout = QVBoxLayout(self.list_box)
        list_info_row = QHBoxLayout()
        self.list_count_label = QLabel("")
        self.list_summary_label = QLabel("")
        list_info_row.addStretch(1)
        list_info_row.addWidget(self.list_summary_label)
        list_info_row.addSpacing(12)
        list_info_row.addWidget(self.list_count_label)
        box_layout.addLayout(list_info_row)
        list_display_mode_row = QHBoxLayout()
        list_display_mode_box = QGroupBox("一覧表示")
        list_display_mode_layout = QHBoxLayout(list_display_mode_box)
        self.list_display_rate_radio = QRadioButton("レート本体")
        self.list_display_gap_radio = QRadioButton("ギャップ")
        self.list_display_rate_radio.setChecked(True)
        self.list_display_rate_radio.toggled.connect(self._on_list_display_mode_changed)
        self.list_display_gap_radio.toggled.connect(self._on_list_display_mode_changed)
        list_display_mode_layout.addWidget(self.list_display_rate_radio)
        list_display_mode_layout.addWidget(self.list_display_gap_radio)
        list_display_mode_layout.addStretch(1)
        list_display_mode_row.addWidget(list_display_mode_box)
        list_display_mode_row.addStretch(1)
        box_layout.addLayout(list_display_mode_row)
        self.table = MatchListTableWidget(self, 0, 18)
        self.table.setHorizontalHeaderLabels(
            [
                "マッチUID",
                "勝敗",
                "PT",
                "レート平均\n(自)",
                "レート中央\n(自)",
                "レート最低\n(自)",
                "レート最高\n(自)",
                "レート平均\n(相)",
                "レート中央\n(相)",
                "レート最低\n(相)",
                "レート最高\n(相)",
                "平均差分",
                "中央差分",
                "最低差分",
                "最高差分",
                "レート偏差\n(陣営)",
                "レート偏差\n(全体)",
                "詳細",
            ]
        )
        header = self.table.horizontalHeader()
        for col_idx in range(0, 18):
            header.setSectionResizeMode(col_idx, QHeaderView.Fixed)
        header.setStretchLastSection(False)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setMinimumHeight(64)
        self.table.setColumnWidth(0, 82)
        self.table.setColumnWidth(1, 44)
        self.table.setColumnWidth(2, 34)
        self.table.setColumnWidth(3, 67)
        self.table.setColumnWidth(4, 67)
        self.table.setColumnWidth(5, 67)
        self.table.setColumnWidth(6, 67)
        self.table.setColumnWidth(7, 67)
        self.table.setColumnWidth(8, 67)
        self.table.setColumnWidth(9, 75)
        self.table.setColumnWidth(10, 75)
        self.table.setColumnWidth(11, 72)
        self.table.setColumnWidth(12, 72)
        self.table.setColumnWidth(13, 72)
        self.table.setColumnWidth(14, 72)
        self.table.setColumnWidth(15, 74)
        self.table.setColumnWidth(16, 74)
        self.table.setColumnWidth(17, 52)
        header.setSectionResizeMode(17, QHeaderView.Fixed)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        box_layout.addWidget(self.table)
        root.addWidget(self.list_box)

        self.overall_summary_box = QGroupBox("全体総括")
        self.overall_summary_layout = QGridLayout(self.overall_summary_box)
        self.overall_summary_layout.setHorizontalSpacing(12)
        self.overall_summary_layout.setVerticalSpacing(6)
        self.overall_summary_layout.setColumnStretch(0, 0)
        self.overall_summary_layout.setColumnStretch(1, 1)

        summary_wrapper = QWidget()
        summary_wrapper_layout = QVBoxLayout(summary_wrapper)
        summary_wrapper_layout.setContentsMargins(0, 0, 0, 0)
        summary_wrapper_layout.setSpacing(6)
        summary_wrapper_layout.addWidget(self.overall_summary_box)

        self.summary_scroll = QScrollArea()
        summary_scroll = self.summary_scroll
        summary_scroll.setWidgetResizable(True)
        summary_scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        summary_scroll.setWidget(summary_wrapper)
        root.addWidget(summary_scroll)

        self.list_box.setVisible(True)
        self.summary_scroll.setVisible(False)
        self._on_list_display_mode_changed()
        self._update_search_mode_enabled()
        self._update_duo_inputs_enabled()
        self._update_result_inputs_enabled()
        self._toggle_search_panel(False)

    def _apply_theme(self):
        self.setFont(QFont("Meiryo", 9))
        self.setStyleSheet(
            """
            QMainWindow { background: #f7f7f7; }
            QLabel#pageTitle { font-size: 16px; font-weight: 600; }
            QGroupBox { font-weight: 600; }
            QTableWidget { background: white; gridline-color: #ddd; }
            QLineEdit { padding: 4px; }
            QPushButton {
                padding: 8px 14px;
                border: 1px solid #1f4f8a;
                border-radius: 7px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3b6fa8, stop:1 #244f82);
                color: white;
                font-weight: 600;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4579b1, stop:1 #2a5a8e);
            }
            QPushButton:pressed {
                background: #1d426b;
                padding-top: 9px;
                padding-left: 15px;
            }
            QPushButton#clearButton {
                background: #f4f4f5;
                border: 1px solid #a1a1aa;
                color: #111827;
            }
            QPushButton#clearButton:hover {
                background: #e5e7eb;
            }
            QPushButton#clearButton:pressed {
                background: #d4d4d8;
                padding-top: 9px;
                padding-left: 15px;
            }
            QPushButton#toggleButton {
                background: transparent;
                border: 0px;
                color: #374151;
                text-align: left;
                padding: 0px;
                font-weight: 600;
            }
            QPushButton#toggleButton:hover {
                color: #111827;
                text-decoration: underline;
            }
            QPushButton#toggleButton:pressed {
                color: #111827;
                padding: 0px;
            }
            """
        )

    def _update_duo_inputs_enabled(self):
        return

    def _update_search_mode_enabled(self):
        enabled = self.search_mode_player_radio.isChecked()
        self.player_id_edit.setEnabled(enabled)
        all_mode = self.search_mode_all_radio.isChecked()
        self.duo_box.setVisible(not all_mode)
        self.result_box.setVisible(not all_mode)
        self.search_button.setVisible(True)
        self.duo_circle_radio.setEnabled(not all_mode)
        self.duo_cross_radio.setEnabled(not all_mode)
        self.duo_all_radio.setEnabled(not all_mode)
        self.search_mode_player_radio.setEnabled(True)
        self.search_mode_all_radio.setEnabled(True)
        self._update_result_inputs_enabled()
        self.list_mode = AllListMode() if self.search_mode_all_radio.isChecked() else PlayerListMode()
        if all_mode:
            self.view_mode_list.setChecked(True)
            self.view_mode_list.setEnabled(True)
            self.view_mode_summary.setChecked(False)
            self.view_mode_summary.setEnabled(False)
            self.main_view_mode = "list"
            self.list_box.setVisible(True)
            self.summary_scroll.setVisible(False)
        else:
            self.view_mode_list.setEnabled(True)
            self.view_mode_summary.setEnabled(True)

    def _get_target_player_uid(self):
        if self.search_mode_all_radio.isChecked():
            return None
        return get_int_or_none(self.player_id_edit.text())

    def _selected_game_mode_ids(self):
        return [2]

    def _selected_match_results(self):
        if self.result_all_radio.isChecked():
            return set()
        if self.result_win_radio.isChecked():
            return {"win"}
        if self.result_lose_radio.isChecked():
            return {"lose"}
        return set()

    def _reset_search_conditions_to_default(self):
        self.search_mode_player_radio.setChecked(True)
        self.search_mode_all_radio.setChecked(False)
        self.player_id_edit.setText(CONFIG.default_player_uid)
        self.duo_all_radio.setChecked(True)
        self.duo_circle_radio.setChecked(False)
        self.duo_cross_radio.setChecked(False)
        self.result_all_radio.setChecked(True)
        self.result_win_radio.setChecked(False)
        self.result_lose_radio.setChecked(False)
        self._update_search_mode_enabled()

    def _update_result_inputs_enabled(self):
        enabled = not self.search_mode_all_radio.isChecked()
        self.result_all_radio.setEnabled(enabled)
        self.result_win_radio.setEnabled(enabled)
        self.result_lose_radio.setEnabled(enabled)

    def _toggle_search_panel(self, collapsed: bool):
        self.search_panel.setVisible(not collapsed)
        self.search_toggle_button.setText("▼ 検索条件" if collapsed else "▲ 検索条件")
        self.search_panel.updateGeometry()
        self.centralWidget().updateGeometry()
        self.summary_scroll.updateGeometry()

    def _make_condition_row(self, check, edit, le_radio, ge_radio):
        row = QHBoxLayout()
        row.addWidget(check)
        row.addWidget(edit)
        row.addWidget(le_radio)
        row.addWidget(ge_radio)
        row.addStretch(1)
        return row

    def _make_list_query_context(self, conn, cur):
        return ListQueryContext(
            conn=conn,
            cur=cur,
            selected_game_mode_ids=set(self._selected_game_mode_ids()),
            selected_match_results=self._selected_match_results(),
            target_player_uid=self._get_target_player_uid(),
            duo_player_uids=set(),
            duo_allowed=self._duo_allowed,
            get_target_player_uid=self._get_target_player_uid,
            get_self_camp=self._get_self_camp,
            is_player_in_camp=self._is_player_in_camp,
            get_player_party_id=self._get_player_party_id,
            has_party_in_match_camp=self._has_party_in_match_camp,
            get_match_result=self._get_match_result,
            get_match_result_by_match=self._get_match_result_by_match,
            split_rates_by_self_camp=self._split_rates_by_self_camp,
            split_rates_by_camp=self._split_rates_by_camp,
            get_match_rate=self._get_match_rate,
            avg=avg,
            median=median,
            min_=min_value,
            max_=max_value,
            variance=variance,
            std=std,
            gap=gap,
            gap_value=gap_value,
            SQL_MATCH_LIST_BY_PLAYER=SQL_MATCH_LIST,
            SQL_MATCH_COUNT_BY_PLAYER=SQL_MATCH_COUNT,
            SQL_MATCH_LIST_ALL=SQL_MATCH_LIST_ALL,
            SQL_MATCH_COUNT_ALL=SQL_MATCH_COUNT_ALL,
        )

    def reload_all(self):
        self._set_ui_busy(True)
        try:
            total_start = time.perf_counter()
            debug_print("[viewer] reload_all start")
            if not self.search_mode_all_radio.isChecked():
                target_player_uid = self._get_target_player_uid()
                if target_player_uid is None:
                    raise ValueError("プレイヤーIDが不正です")
            load_start = time.perf_counter()
            all_rows = self._load_matches()
            debug_print(f"[viewer] _load_matches {len(all_rows)} rows in {time.perf_counter() - load_start:.3f}s")
            count_start = time.perf_counter()
            total_count = self._load_matches_count()
            debug_print(f"[viewer] _load_matches_count {total_count} rows in {time.perf_counter() - count_start:.3f}s")
            rows = all_rows
            table_start = time.perf_counter()
            self.table.setUpdatesEnabled(False)
            self.table.setSortingEnabled(False)
            self.table.setRowCount(len(rows))
            for row_idx, row in enumerate(rows):
                values = [
                    row["match_uid"],
                    row["is_win"],
                    row["duo"],
                    row["avg_my"],
                    row["median_my"],
                    row["min_my"],
                    row["max_my"],
                    row["avg_opp"],
                    row["median_opp"],
                    row["min_opp"],
                    row["max_opp"],
                    row["avg_gap"],
                    row["median_gap"],
                    row["min_gap"],
                    row["max_gap"],
                    self._format_deviation_score(row["rate_my"], row["avg_my"], row["std_my"]),
                    self._format_deviation_score(row["rate_my"], row["avg_all"], row["std_all"]),
                    "詳細",
                ]
                for col_idx, value in enumerate(values):
                    item = QTableWidgetItem(str(value))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    if col_idx == 0:
                        item.setToolTip(str(value))
                        item.setData(Qt.ItemDataRole.UserRole, row)
                    if col_idx == 1:
                        self._apply_result_brush(item, value)
                    if 10 <= col_idx <= 14:
                        self._apply_gap_brush(item, value)
                    self.table.setItem(row_idx, col_idx, item)
                for left_idx, right_idx in ((3, 7), (4, 8), (5, 9), (6, 10)):
                    self._apply_rate_pair_brush(
                        self.table.item(row_idx, left_idx),
                        self.table.item(row_idx, right_idx),
                        values[left_idx],
                        values[right_idx],
                    )
                self.table.item(row_idx, 17).setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.item(row_idx, 17).setForeground(QBrush(QColor("#0b5bd3")))
            debug_print(f"[viewer] table render in {time.perf_counter() - table_start:.3f}s")
            shown_count = len(rows)
            self.list_count_label.setText(f"{shown_count}/{total_count}")
            summary_start = time.perf_counter()
            self._update_overall_summary(rows)
            debug_print(f"[viewer] summary render in {time.perf_counter() - summary_start:.3f}s")
            debug_print(f"[viewer] reload_all total {time.perf_counter() - total_start:.3f}s")
        finally:
            self.table.setUpdatesEnabled(True)
            self._set_ui_busy(False)

    def _set_ui_busy(self, busy: bool):
        widgets = [
            self.player_id_edit,
            self.duo_circle_radio,
            self.duo_cross_radio,
            self.duo_all_radio,
            self.result_all_radio,
            self.result_win_radio,
            self.result_lose_radio,
            self.search_mode_player_radio,
            self.search_mode_all_radio,
            self.search_button,
            self.view_mode_list,
            self.view_mode_summary,
            self.table,
        ]
        for widget in widgets:
            widget.setEnabled(not busy)
        self.setCursor(Qt.CursorShape.WaitCursor if busy else Qt.CursorShape.ArrowCursor)
        if self.centralWidget() is not None:
            self.centralWidget().setEnabled(True)

    def _on_main_view_mode_changed(self):
        if self.search_mode_all_radio.isChecked():
            self.view_mode_list.setChecked(True)
            self.main_view_mode = "list"
            self.list_box.setVisible(True)
            self.summary_scroll.setVisible(False)
            return
        if self.view_mode_summary.isChecked():
            self.main_view_mode = "summary"
        else:
            self.main_view_mode = "list"
        self.list_box.setVisible(self.main_view_mode == "list")
        self.summary_scroll.setVisible(self.main_view_mode == "summary")

    def _on_list_display_mode_changed(self):
        self.list_detail_mode = "gap" if self.list_display_gap_radio.isChecked() else "rate"
        show_gap = self.list_detail_mode == "gap"
        # Base rate columns are useful in rate mode; gap columns are useful in gap mode.
        rate_mode_hidden = (3, 4, 5, 6, 7, 8, 9, 10)
        gap_mode_hidden = (11, 12, 13, 14)
        for col_idx in rate_mode_hidden:
            self.table.setColumnHidden(col_idx, show_gap)
        for col_idx in gap_mode_hidden:
            self.table.setColumnHidden(col_idx, not show_gap)
        self.table.setColumnHidden(15, False)
        self.table.setColumnHidden(16, False)
        self.table.setColumnHidden(17, False)

    def _update_overall_summary(self, rows):
        while self.overall_summary_layout.count():
            item = self.overall_summary_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self.overall_summary_layout.addWidget(QLabel("項目"), 0, 0)
        self.overall_summary_layout.addWidget(QLabel("全体"), 0, 1)

        summary_rows = [
            ("全体勝率", self._format_win_rate(rows)),
            ("平均値:平均レート差", avg([row["avg_gap"] for row in rows])),
            ("平均値:中央レート差", avg([row["median_gap"] for row in rows])),
            ("平均値:最低レート差", avg([row["min_gap"] for row in rows])),
            ("平均値:最高レート差", avg([row["max_gap"] for row in rows])),
            ("平均値:偏差値(陣営)", avg([self._format_deviation_score(row["rate_my"], row["avg_my"], row["std_my"]) for row in rows])),
            ("平均値:偏差値(全体)", avg([self._format_deviation_score(row["rate_my"], row["avg_all"], row["std_all"]) for row in rows])),
            ("平均レート差<0", self._format_rate_condition_ratio(rows, "avg_gap", lambda v: v < 0)),
            ("最低レート差<0", self._format_rate_condition_ratio(rows, "min_gap", lambda v: v < 0)),
            ("最高レート差<0", self._format_rate_condition_ratio(rows, "max_gap", lambda v: v < 0)),
            ("有利マッチを落とす", self._format_favorable_loss_ratio(rows)),
            ("不利マッチで勝つ", self._format_unfavorable_win_ratio(rows)),
        ]

        for idx, (label_text, value) in enumerate(summary_rows, start=1):
            self.overall_summary_layout.addWidget(QLabel(label_text), idx, 0)
            self.overall_summary_layout.addWidget(self._make_summary_value_label(value), idx, 1)

        chart_row = len(summary_rows) + 1
        charts = [
            self._build_rate_band_winrate_chart(rows, "avg_gap", "平均レート差帯別の勝率"),
            self._build_rate_band_winrate_chart(rows, "median_gap", "中央レート差帯別の勝率"),
            self._build_rate_band_winrate_chart(rows, "min_gap", "最低レート差帯別の勝率"),
            self._build_deviation_histogram_chart(rows),
        ]
        for offset, chart in enumerate(charts):
            self.overall_summary_layout.addWidget(chart, chart_row + offset, 0, 1, 2)

    def _load_matches(self):
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            ctx = self._make_list_query_context(conn, cur)
            rows = self.list_mode.load_matches(ctx)
            conn.close()
            return rows
        except Exception as exc:
            self._show_error_message(f"読み込みエラー: {exc}")
            return []

    def _load_matches_count(self):
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            ctx = self._make_list_query_context(conn, cur)
            return self.list_mode.load_count(ctx)
        except Exception:
            return 0
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _duo_allowed(self, duo_mark: str) -> bool:
        if self.duo_all_radio.isChecked():
            return True
        if duo_mark == "〇":
            return self.duo_circle_radio.isChecked()
        if duo_mark == "×":
            return self.duo_cross_radio.isChecked()
        return True

    def _get_win_camp(self, cur, match_uid: str):
        cur.execute(
            """
            SELECT camp
            FROM match_players_tbl
            WHERE match_uid = ? AND is_win = 1
            LIMIT 1
            """,
            (match_uid,),
        )
        row = cur.fetchone()
        return "" if row is None else row[0]

    def _get_match_result_by_match(self, cur, match_uid: str):
        win_camp = self._get_win_camp(cur, match_uid)
        return "win" if win_camp != "" else "lose"

    def _get_self_camp(self, cur, match_uid: str, player_uid: int):
        cur.execute(SQL_SELF_CAMP, (match_uid, player_uid))
        row = cur.fetchone()
        return None if row is None else row[0]

    def _is_player_in_camp(self, cur, match_uid: str, player_uid: int, camp: int) -> bool:
        cur.execute(SQL_IS_PLAYER_IN_CAMP, (match_uid, player_uid, camp))
        return cur.fetchone() is not None

    def _get_player_party_id(self, cur, player_uid: int):
        cur.execute(SQL_PLAYER_PARTY_ID, (player_uid,))
        row = cur.fetchone()
        return None if row is None else row[0]

    def _has_party_in_match_camp(self, cur, match_uid: str, camp: int, party_id: int) -> bool:
        cur.execute(SQL_HAS_PARTY_IN_MATCH_CAMP, (match_uid, camp, party_id))
        return cur.fetchone() is not None

    def _split_rates_by_self_camp(self, cur, match_uid: str, self_camp):
        cur.execute(SQL_MATCH_PLAYERS_RATES, (match_uid,))
        my_rates = []
        opp_rates = []
        for camp, rate in cur.fetchall():
            if rate is None:
                continue
            if self_camp is not None and camp == self_camp:
                my_rates.append(rate)
            else:
                opp_rates.append(rate)
        return my_rates, opp_rates

    def _split_rates_by_camp(self, cur, match_uid: str):
        cur.execute(SQL_MATCH_PLAYERS_RATES, (match_uid,))
        camp0_rates = []
        camp1_rates = []
        for camp, rate in cur.fetchall():
            if rate is None:
                continue
            if camp == 0:
                camp0_rates.append(rate)
            else:
                camp1_rates.append(rate)
        return camp0_rates, camp1_rates

    def _get_match_result(self, cur, match_uid: str, player_uid: int) -> str:
        cur.execute(SQL_MATCH_RESULT, (match_uid, player_uid))
        row = cur.fetchone()
        if row is None:
            return ""
        value = row[0]
        if isinstance(value, int):
            return "win" if value == 1 else "lose"
        if isinstance(value, str):
            value = value.strip().lower()
            if value in ("win", "lose"):
                return value
            return "win" if value in ("1", "true", "yes") else "lose"
        return "win" if value else "lose"

    def _apply_gap_brush(self, item, value):
        text = str(value).strip()
        if not text:
            return
        if text.startswith("+"):
            item.setBackground(QBrush(QColor("#dbeafe")))
        elif text.startswith("-"):
            item.setBackground(QBrush(QColor("#fee2e2")))

    def _apply_result_brush(self, item, value):
        if value == "win":
            item.setBackground(QColor("#0b3d91"))
        elif value == "lose":
            item.setBackground(QColor("#8b1e1e"))
        else:
            return
        item.setForeground(QBrush(QColor("#ffffff")))

    def _apply_rate_pair_brush(self, left_item, right_item, left_value, right_value):
        try:
            left_num = float(left_value)
            right_num = float(right_value)
        except (TypeError, ValueError):
            return
        if left_num == right_num:
            return
        winner_bg = QColor("#dbeafe")
        loser_bg = QColor("#fee2e2")
        if left_num > right_num:
            left_item.setBackground(winner_bg)
            right_item.setBackground(loser_bg)
        else:
            left_item.setBackground(loser_bg)
            right_item.setBackground(winner_bg)

    def _make_summary_value_label(self, value):
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

    def _build_rate_band_half_chart(self, rows, gap_key, title, bands, positive: bool):
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

    def _build_deviation_histogram_chart(self, rows):
        bins = [
            ("40未満", None, 40),
            ("40-45", 40, 45),
            ("45-50", 45, 50),
            ("50-55", 50, 55),
            ("55-60", 55, 60),
            ("60+", 60, None),
        ]
        camp_scores = [self._format_deviation_score(row["rate_my"], row["avg_my"], row["std_my"]) for row in rows]
        all_scores = [self._format_deviation_score(row["rate_my"], row["avg_all"], row["std_all"]) for row in rows]

        def count_scores(scores, low, high):
            count = 0
            for score in scores:
                if score in ("", None):
                    continue
                try:
                    value = float(score)
                except (TypeError, ValueError):
                    continue
                if low is None and value < high:
                    count += 1
                elif high is None and value >= low:
                    count += 1
                elif low is not None and high is not None and low <= value < high:
                    count += 1
            return count

        series = QBarSeries()
        camp_set = QBarSet("偏差値(陣営)")
        all_set = QBarSet("偏差値(全体)")
        camp_set.setColor(QColor("#244f82"))
        all_set.setColor(QColor("#6b7280"))

        for _, low, high in bins:
            camp_set.append(count_scores(camp_scores, low, high))
            all_set.append(count_scores(all_scores, low, high))

        series.append(camp_set)
        series.append(all_set)

        chart = QChart()
        chart.addSeries(series)
        chart.setTitle("偏差値ヒストグラム")
        chart.legend().setVisible(True)
        chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)
        chart.setBackgroundVisible(False)

        axis_x = QBarCategoryAxis()
        axis_x.append([label for label, _, _ in bins])
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(axis_x)

        from PySide6.QtCharts import QValueAxis

        axis_y = QValueAxis()
        max_count = max([count_scores(camp_scores, low, high) for _, low, high in bins] + [count_scores(all_scores, low, high) for _, low, high in bins] + [1])
        axis_y.setRange(0, max_count)
        axis_y.setTickCount(min(max_count + 1, 6))
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_y)
        chart.setMargins(QMargins(18, 18, 18, 18))

        view = QChartView(chart)
        view.setRenderHint(QPainter.RenderHint.Antialiasing)
        view.setMinimumHeight(300)
        return view

    def _show_match_detail(self, row):
        self.detail_window = MatchDetailWindow(self, row)
        self.detail_window.show()
        self.detail_window.raise_()
        self.detail_window.activateWindow()

    def _open_match_detail_from_row(self, row_idx):
        item = self.table.item(row_idx, 0)
        if item is None:
            return
        row = item.data(Qt.ItemDataRole.UserRole)
        if row is not None:
            self._show_match_detail(row)

    def _show_error_message(self, message: str):
        dialog = QDialog(self)
        dialog.setWindowTitle("エラー")
        dialog.resize(520, 180)
        layout = QVBoxLayout(dialog)
        label = QLabel(message)
        label.setWordWrap(True)
        layout.addWidget(label)
        close_button = QPushButton("閉じる")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button)
        dialog.exec()

    def _show_detail_dialog(self, row):
        dialog = QDialog(self)
        dialog.setWindowTitle(f"マッチ詳細: {row['match_uid']}")
        dialog.resize(1980, 800)
        layout = QVBoxLayout(dialog)
        layout.setSpacing(12)

        def make_value_label(value):
            label = QLabel(str(value))
            label.setFrameShape(QFrame.Shape.Panel)
            label.setFrameShadow(QFrame.Shadow.Sunken)
            label.setMinimumHeight(24)
            label.setStyleSheet("padding: 2px 6px; background: white;")
            return label

        overview = QGroupBox("概要")
        overview_layout = QGridLayout(overview)
        overview_layout.setHorizontalSpacing(12)
        overview_layout.setVerticalSpacing(6)
        overview_layout.addWidget(QLabel("マッチUID"), 0, 0)
        overview_layout.addWidget(make_value_label(row["match_uid"]), 0, 1)
        layout.addWidget(overview)

        detail_rows = self._load_match_detail_players(row["match_uid"])
        target_player_uid = self._get_target_player_uid()
        self_camp = self._get_self_camp_for_match(row["match_uid"], target_player_uid)
        score_mode_box = QGroupBox("表示切替")
        score_mode_layout = QHBoxLayout(score_mode_box)
        score_mode_normal = QRadioButton("通常値")
        score_mode_gap = QRadioButton("Top500平均との差")
        score_mode_normal.setChecked(True)
        score_mode_layout.addWidget(score_mode_normal)
        score_mode_layout.addWidget(score_mode_gap)
        score_mode_layout.addStretch(1)
        layout.addWidget(score_mode_box)

        players_box = QGroupBox("camp別プレイヤー明細")
        players_layout = QHBoxLayout(players_box)
        players_layout.setSpacing(12)
        players_layout.setContentsMargins(0, 0, 0, 0)

        def refresh_players():
            self._clear_layout(players_layout)
            camp0_rows = [r for r in detail_rows if r["camp"] == 0]
            camp1_rows = [r for r in detail_rows if r["camp"] == 1]
            score_mode = "gap" if score_mode_gap.isChecked() else "normal"
            self_rows = camp0_rows if self_camp == 0 else camp1_rows
            opp_rows = camp1_rows if self_camp == 0 else camp0_rows
            left_table = self._build_player_detail_table(
                "自分",
                self._pick_camp_result(self_rows),
                self_rows,
                score_mode,
            )
            right_table = self._build_player_detail_table(
                "相手",
                self._pick_camp_result(opp_rows),
                opp_rows,
                score_mode,
            )
            players_layout.addWidget(left_table)
            players_layout.addWidget(right_table)

        score_mode_normal.toggled.connect(refresh_players)
        score_mode_gap.toggled.connect(refresh_players)
        refresh_players()
        layout.addWidget(players_box)

        summary = QGroupBox("レート情報")
        summary_layout = QGridLayout(summary)
        summary_layout.setHorizontalSpacing(12)
        summary_layout.setVerticalSpacing(6)
        summary_items = [
            ("平均", row["avg_my"], row["avg_opp"], row["avg_gap"]),
            ("最低", row["min_my"], row["min_opp"], row["min_gap"]),
            ("最高", row["max_my"], row["max_opp"], row["max_gap"]),
            ("レート偏差(陣営)", self._format_deviation_score(row["rate_my"], row["avg_my"], row["std_my"]), "", ""),
            ("レート偏差(全体)", self._format_deviation_score(row["rate_my"], row["avg_all"], row["std_all"]), "", ""),
        ]
        summary_layout.addWidget(QLabel("項目"), 0, 0)
        summary_layout.addWidget(QLabel("自チーム"), 0, 1)
        summary_layout.addWidget(QLabel("相手チーム"), 0, 2)
        summary_layout.addWidget(QLabel("差分"), 0, 3)
        for idx, (label_text, self_value, opp_value, gap_value) in enumerate(summary_items, start=1):
            summary_layout.addWidget(QLabel(label_text), idx, 0)
            summary_layout.addWidget(make_value_label(self_value), idx, 1)
            summary_layout.addWidget(make_value_label(opp_value), idx, 2)
            summary_layout.addWidget(make_value_label(gap_value), idx, 3)
        layout.addWidget(summary)
        dialog.exec()

    def _load_match_detail_players(self, match_uid: str):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.cursor()
            cur.execute(SQL_MATCH_DETAIL_PLAYERS, (match_uid,))
            return cur.fetchall()
        finally:
            conn.close()

    def _get_self_camp_for_match(self, match_uid: str, player_uid: int):
        conn = sqlite3.connect(DB_PATH)
        try:
            cur = conn.cursor()
            cur.execute(SQL_SELF_CAMP, (match_uid, player_uid))
            row = cur.fetchone()
            return None if row is None else row[0]
        finally:
            conn.close()

    def _pick_camp_result(self, detail_rows):
        for detail_row in detail_rows:
            value = detail_row["is_win"]
            if value is None:
                continue
            return "win" if value else "lose"
        return ""

    def _build_player_detail_table(self, title, match_result, detail_rows, score_mode):
        box = QGroupBox(title)
        layout = QVBoxLayout(box)
        result_label = QLabel("win" if match_result == "win" else "lose")
        result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        result_label.setMinimumHeight(30)
        result_label.setStyleSheet(
            """
            QLabel {
                font-size: 14px;
                font-weight: 700;
                border-radius: 6px;
                padding: 4px 10px;
                margin-bottom: 6px;
                background: %s;
                color: #1f2937;
            }
            """
            % ("#dbeafe" if match_result == "win" else "#fee2e2")
        )
        layout.addWidget(result_label)
        headers = [
            "nick_name",
            "レート",
            "レート偏差値\n(自)",
            "レート偏差値\n(全)",
            "使用キャラ",
            "ロール",
            "K",
            "D",
            "A",
            "KDA",
            "KDA差分",
            "ダメージ/分",
            "ダメージ/分差分",
            "回復/分",
            "回復/分差分",
            "被ダメージ/分",
            "被ダメージ/分差分",
        ]
        table = QTableWidget(0, 17)
        table.setHorizontalHeaderLabels(headers)
        header = table.horizontalHeader()
        for col_idx in range(17):
            header.setSectionResizeMode(col_idx, QHeaderView.ResizeToContents)
        header.setStretchLastSection(False)
        table.setColumnWidth(0, 120)
        table.setColumnWidth(1, 70)
        table.setColumnWidth(2, 80)
        table.setColumnWidth(3, 80)
        table.setColumnWidth(4, 110)
        table.setColumnWidth(5, 70)
        table.setColumnWidth(6, 55)
        table.setColumnWidth(7, 55)
        table.setColumnWidth(8, 55)
        table.setColumnWidth(9, 95)
        table.setColumnWidth(10, 95)
        table.setColumnWidth(11, 105)
        table.setColumnWidth(12, 105)
        table.setColumnWidth(13, 90)
        table.setColumnWidth(14, 90)
        table.setColumnWidth(15, 105)
        table.setColumnWidth(16, 105)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        self._apply_score_mode(table, score_mode)
        team_rates = [r["current_rate"] for r in detail_rows if r["current_rate"] is not None]
        all_rates = [r["current_rate"] for r in detail_rows if r["current_rate"] is not None]
        team_mean = avg(team_rates)
        team_std = std(team_rates)
        all_mean = avg(all_rates)
        all_std = std(all_rates)
        for detail_row in detail_rows:
            hero_id = detail_row["cur_hero_id"]
            top500 = self._get_top500_stats(hero_id)
            kda = self._format_kda(detail_row["k"], detail_row["d"], detail_row["a"])
            damage_per_min = self._format_per_minute(detail_row["total_hero_damage"], detail_row["match_play_duration"])
            heal_per_min = self._format_per_minute(detail_row["total_hero_heal"], detail_row["match_play_duration"])
            taken_per_min = self._format_per_minute(detail_row["total_damage_taken"], detail_row["match_play_duration"])
            insert_row = table.rowCount()
            table.insertRow(insert_row)
            values = [
                detail_row["nick_name"] or "",
                self._format_rate(detail_row["current_rate"]),
                self._format_deviation_score(detail_row["current_rate"], team_mean, team_std),
                self._format_deviation_score(detail_row["current_rate"], all_mean, all_std),
                detail_row["hero_name"] or detail_row["cur_hero_id"] or "",
                self._format_role(detail_row["role_id"]),
                detail_row["k"],
                detail_row["d"],
                detail_row["a"],
                kda,
                self._format_signed_diff(kda, top500.get("KDA")),
                damage_per_min,
                self._format_signed_diff(damage_per_min, top500.get("ダメージ/分")),
                heal_per_min,
                self._format_signed_diff(heal_per_min, top500.get("回復/分")),
                taken_per_min,
                self._format_signed_diff(taken_per_min, top500.get("被ダメージ/分")),
            ]
            for col_idx, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                table.setItem(insert_row, col_idx, item)
        layout.addWidget(table)
        return box

    def _get_top500_stats(self, hero_id):
        if hero_id is None:
            return {}
        conn = sqlite3.connect(DB_PATH)
        try:
            cur = conn.cursor()
            cur.execute(SQL_TOP500_STATS, (hero_id,))
            row = cur.fetchone()
            if row is None:
                return {}
            return {
                "KDA": row[0],
                "accuracy": row[1],
                "ダメージ/分": row[2],
                "被ダメージ/分": row[3],
                "回復/分": row[4],
            }
        finally:
            conn.close()

    def _format_signed_diff(self, value, base):
        if value in ("", None) or base in ("", None):
            return ""
        if value == "∞":
            return ""
        try:
            diff = round(float(value) - float(base), 1)
        except (TypeError, ValueError):
            return ""
        return format_signed(diff)

    def _get_match_rate(self, cur, match_uid: str, player_uid: int):
        cur.execute(SQL_CURRENT_RATE, (match_uid, player_uid))
        row = cur.fetchone()
        if row is None or row[0] is None:
            return ""
        return row[0]

    def _format_deviation_score(self, value, mean, std):
        if value in ("", None) or mean in ("", None) or std in ("", None) or std == 0:
            return ""
        try:
            return round(50 + 10 * ((float(value) - float(mean)) / float(std)), 1)
        except (TypeError, ValueError, ZeroDivisionError):
            return ""

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _apply_score_mode(self, table, score_mode):
        gap_mode = score_mode == "gap"
        for col_idx in (9, 11, 13, 15):
            table.setColumnHidden(col_idx, gap_mode)
        for col_idx in (10, 12, 14, 16):
            table.setColumnHidden(col_idx, not gap_mode)

    def _format_rate(self, value):
        if value is None:
            return ""
        return round(value, 1)

    def _format_role(self, role_id):
        if role_id is None:
            return ""
        return {0: "Tank", 1: "DPS", 2: "Support"}.get(role_id, role_id)

    def _format_kda(self, k, d, a):
        if k is None or d is None or a is None:
            return ""
        if d == 0:
            return "∞"
        return round((k + a) / d, 2)

    def _format_per_minute(self, total_value, duration):
        if total_value is None or duration in (None, 0):
            return ""
        return round(total_value / duration, 1)


def run_viewer():
    app = QApplication(sys.argv)
    window = ViewerWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_viewer()
