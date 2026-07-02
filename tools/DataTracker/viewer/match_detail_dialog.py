import sqlite3

from PySide6.QtCore import QEvent, Qt
from PySide6.QtCore import QSignalBlocker
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QAbstractItemView,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from config import load_config, resolve_path
from debug_utils import debug_print
from sql_utils import load_sql


CONFIG = load_config()
DB_PATH = resolve_path(CONFIG.database_path)
DEFAULT_PLAYER_UID = int(CONFIG.default_player_uid)
SQL_SELF_CAMP = load_sql("viewer/viewer_self_camp.sql")
SQL_MATCH_DETAIL_PLAYERS = load_sql("viewer/viewer_match_detail_players.sql")
SQL_MATCH_DETAIL_HEROES = """
/* viewer: Used by the match detail window to display every hero used in a match, ordered by player and role. */
SELECT
    mp.camp,
    mp.player_uid,
    mp.nick_name,
    mp.is_win,
    mp.current_rate,
    mph.hero_id AS cur_hero_id,
    hm.hero_name,
    hm.role_id,
    mph.play_time,
    mph.k,
    mph.d,
    mph.a,
    mp.total_hero_damage,
    mp.total_hero_heal,
    mp.total_damage_taken,
    m.match_play_duration
FROM match_player_heroes_tbl AS mph
JOIN match_players_tbl AS mp
    ON mp.match_uid = mph.match_uid
   AND mp.player_uid = mph.player_uid
LEFT JOIN heroes_mst AS hm
    ON hm.hero_id = mph.hero_id
LEFT JOIN matches_tbl AS m
    ON m.match_uid = mph.match_uid
WHERE mph.match_uid = ?
ORDER BY
    mp.player_uid ASC,
    CASE hm.role_id
        WHEN 0 THEN 0
        WHEN 1 THEN 1
        WHEN 2 THEN 2
        ELSE 3
    END,
    mph.play_time DESC,
    mph.hero_id ASC;
"""


class MatchDetailWindow(QMainWindow):
    def __init__(self, parent, row):
        super().__init__(parent)
        self.row = row
        self.self_camp = None
        self.detail_rows = []
        self.players_layout = None
        self.score_mode_normal = None
        self.score_mode_gap = None
        self.detail_mode_current = None
        self.detail_mode_all = None
        self.self_table = None
        self.opp_table = None
        self._syncing_scroll = False
        self.setWindowTitle(f"Match detail: {row['match_uid']}")
        self.resize(1120, 780)
        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(12)

        overview = QGroupBox("Overview")
        overview_layout = QGridLayout(overview)
        overview_layout.addWidget(QLabel("Match UID"), 0, 0)
        overview_layout.addWidget(self._make_value_label(self.row["match_uid"]), 0, 1)
        layout.addWidget(overview)

        self.self_camp = self._get_self_camp_for_match(self.row["match_uid"])
        self.detail_rows = self._load_match_detail_players(self.row["match_uid"])
        self.hero_rows = self._load_match_detail_heroes(self.row["match_uid"])

        mode_box = QGroupBox("Display mode")
        mode_layout = QHBoxLayout(mode_box)
        self.score_mode_normal = QRadioButton("Normal")
        self.score_mode_gap = QRadioButton("Top500 delta")
        self.score_mode_normal.setChecked(True)
        mode_layout.addWidget(self.score_mode_normal)
        mode_layout.addWidget(self.score_mode_gap)
        mode_layout.addStretch(1)
        layout.addWidget(mode_box)

        detail_mode_box = QGroupBox("Camp players mode")
        detail_mode_layout = QHBoxLayout(detail_mode_box)
        self.detail_mode_current = QRadioButton("Current hero")
        self.detail_mode_all = QRadioButton("All")
        self.detail_mode_current.setChecked(True)
        detail_mode_layout.addWidget(self.detail_mode_current)
        detail_mode_layout.addWidget(self.detail_mode_all)
        detail_mode_layout.addStretch(1)
        layout.addWidget(detail_mode_box)

        players_box = QGroupBox("Camp players")
        self.players_layout = QHBoxLayout(players_box)
        self.players_layout.setSpacing(12)
        self.players_layout.setContentsMargins(0, 0, 0, 0)
        self.score_mode_normal.toggled.connect(self._refresh_players)
        self.score_mode_gap.toggled.connect(self._refresh_players)
        self.detail_mode_current.toggled.connect(self._refresh_players)
        self.detail_mode_all.toggled.connect(self._refresh_players)
        self._refresh_players()
        layout.addWidget(players_box)

        summary = QGroupBox("Rate info")
        summary_layout = QGridLayout(summary)
        summary_layout.setHorizontalSpacing(12)
        summary_layout.setVerticalSpacing(6)
        summary_layout.addWidget(QLabel("Item"), 0, 0)
        summary_layout.addWidget(QLabel("My camp"), 0, 1)
        summary_layout.addWidget(QLabel("Opp camp"), 0, 2)
        summary_layout.addWidget(QLabel("Gap"), 0, 3)
        summary_items = [
            ("Average", self.row["avg_my"], self.row["avg_opp"], self.row["avg_gap"]),
            ("Minimum", self.row["min_my"], self.row["min_opp"], self.row["min_gap"]),
            ("Maximum", self.row["max_my"], self.row["max_opp"], self.row["max_gap"]),
            ("Variance", self.row["var_my"], self.row["var_opp"], ""),
        ]
        for idx, (label_text, self_value, opp_value, gap_value) in enumerate(summary_items, start=1):
            summary_layout.addWidget(QLabel(label_text), idx, 0)
            summary_layout.addWidget(self._make_value_label(self_value), idx, 1)
            summary_layout.addWidget(self._make_value_label(opp_value), idx, 2)
            summary_layout.addWidget(self._make_value_label(gap_value), idx, 3)
        layout.addWidget(summary)

    def _refresh_players(self):
        while self.players_layout.count():
            item = self.players_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        source_rows = self.hero_rows if self.detail_mode_all.isChecked() else self.detail_rows
        camp0_rows = [r for r in source_rows if r["camp"] == 0]
        camp1_rows = [r for r in source_rows if r["camp"] == 1]
        score_mode = "gap" if self.score_mode_gap.isChecked() else "normal"

        self_rows = camp0_rows if self.self_camp == 0 else camp1_rows
        opp_rows = camp1_rows if self.self_camp == 0 else camp0_rows
        self.self_table = self._build_player_detail_table("Self", self._pick_camp_result(self_rows), self_rows, score_mode)
        self.opp_table = self._build_player_detail_table("Opp", self._pick_camp_result(opp_rows), opp_rows, score_mode)
        self._sync_camp_tables(self.self_table, self.opp_table)
        self.players_layout.addWidget(self.self_table)
        self.players_layout.addWidget(self.opp_table)

    def _make_value_label(self, value):
        label = QLabel("" if value in ("", None) else str(value))
        label.setFrameShape(QFrame.Shape.Panel)
        label.setFrameShadow(QFrame.Shadow.Sunken)
        label.setMinimumHeight(24)
        label.setStyleSheet("padding: 2px 6px; background: white;")
        return label

    def _load_match_detail_players(self, match_uid: str):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.cursor()
            cur.execute(SQL_MATCH_DETAIL_PLAYERS, (match_uid,))
            return cur.fetchall()
        finally:
            conn.close()

    def _load_match_detail_heroes(self, match_uid: str):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.cursor()
            cur.execute(SQL_MATCH_DETAIL_HEROES, (match_uid,))
            return cur.fetchall()
        finally:
            conn.close()

    def _get_self_camp_for_match(self, match_uid: str):
        conn = sqlite3.connect(DB_PATH)
        try:
            cur = conn.cursor()
            cur.execute(SQL_SELF_CAMP, (match_uid, DEFAULT_PLAYER_UID))
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
            "font-size: 14px; font-weight: 700; border-radius: 6px; padding: 4px 10px; "
            + (
                "background: #0b3d91; color: white;"
                if match_result == "win"
                else "background: #8b1e1e; color: white;"
            )
        )
        layout.addWidget(result_label)

        if score_mode == "gap":
            if self.detail_mode_all.isChecked():
                headers = [
                    "nick_name",
                    "rate",
                    "rate_dev(camp)",
                    "rate_dev(all)",
                    "hero",
                    "role",
                    "play_time(min)",
                    "K",
                    "D",
                    "A",
                    "KDA delta",
                ]
            else:
                headers = [
                    "nick_name",
                    "rate",
                    "rate_dev(camp)",
                    "rate_dev(all)",
                    "hero",
                    "role",
                    "K",
                    "D",
                    "A",
                    "KDA delta",
                    "damage/min",
                    "damage/min delta",
                    "heal/min",
                    "heal/min delta",
                    "taken/min",
                    "taken/min delta",
                ]
        else:
            if self.detail_mode_all.isChecked():
                headers = [
                    "nick_name",
                    "rate",
                    "rate_dev(camp)",
                    "rate_dev(all)",
                    "hero",
                    "role",
                    "play_time(min)",
                    "K",
                    "D",
                    "A",
                    "KDA",
                ]
            else:
                headers = [
                    "nick_name",
                    "rate",
                    "rate_dev(camp)",
                    "rate_dev(all)",
                    "hero",
                    "role",
                    "K",
                    "D",
                    "A",
                    "KDA",
                    "damage/min",
                    "heal/min",
                    "taken/min",
                ]

        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setWordWrap(True)
        table.setTextElideMode(Qt.TextElideMode.ElideNone)
        table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        widths = [110, 70, 90, 90, 110, 70, 70, 40, 40, 40, 80, 92, 84, 98]
        for col_idx, width in enumerate(widths[: len(headers)]):
            table.setColumnWidth(col_idx, width)
        header.setStretchLastSection(False)
        if score_mode == "gap" and not self.detail_mode_all.isChecked():
            for col_idx in (10, 12, 14):
                if col_idx < table.columnCount():
                    table.setColumnHidden(col_idx, True)

        if self.detail_mode_all.isChecked():
            team_rates = self._unique_rates_by_player(detail_rows)
            all_rates = self._unique_rates_by_player(self.hero_rows)
        else:
            team_rates = [r["current_rate"] for r in detail_rows if r["current_rate"] is not None]
            all_rates = [r["current_rate"] for r in self.detail_rows if r["current_rate"] is not None]
        team_mean = self._avg(team_rates)
        team_std = self._std(team_rates)
        all_mean = self._avg(all_rates)
        all_std = self._std(all_rates)

        for detail_row in detail_rows:
            hero_id = detail_row["cur_hero_id"]
            top500 = self._get_top500_stats(hero_id)
            kda = self._format_kda(detail_row["k"], detail_row["d"], detail_row["a"])
            play_time = ""
            if "play_time" in detail_row.keys() and detail_row["play_time"] is not None:
                play_time = round(float(detail_row["play_time"]) / 60, 1)
            if not self.detail_mode_all.isChecked():
                damage_per_min = self._format_per_minute(detail_row["total_hero_damage"], detail_row["match_play_duration"])
                heal_per_min = self._format_per_minute(detail_row["total_hero_heal"], detail_row["match_play_duration"])
                taken_per_min = self._format_per_minute(detail_row["total_damage_taken"], detail_row["match_play_duration"])
                debug_print(
                    "[match_detail]",
                    "player_uid=",
                    detail_row["player_uid"],
                    "hero_id=",
                    hero_id,
                    "duration=",
                    detail_row["match_play_duration"],
                    "damage_raw=",
                    detail_row["total_hero_damage"],
                    "heal_raw=",
                    detail_row["total_hero_heal"],
                    "taken_raw=",
                    detail_row["total_damage_taken"],
                    "damage/min=",
                    damage_per_min,
                    "heal/min=",
                    heal_per_min,
                    "taken/min=",
                    taken_per_min,
                    "top500=",
                    top500,
                )

            row_idx = table.rowCount()
            table.insertRow(row_idx)

            values = [
                detail_row["nick_name"] or "",
                self._format_rate(detail_row["current_rate"]),
                self._format_deviation_score(detail_row["current_rate"], team_mean, team_std),
                self._format_deviation_score(detail_row["current_rate"], all_mean, all_std),
                detail_row["hero_name"] or detail_row["cur_hero_id"] or "",
                self._format_role(detail_row["role_id"]),
            ]
            if self.detail_mode_all.isChecked():
                values.extend(
                    [
                        play_time,
                        detail_row["k"],
                        detail_row["d"],
                        detail_row["a"],
                    ]
                )
            else:
                values.extend(
                    [
                        detail_row["k"],
                        detail_row["d"],
                        detail_row["a"],
                    ]
                )
            if score_mode == "gap":
                if self.detail_mode_all.isChecked():
                    values.extend([self._format_signed_diff(kda, top500.get("KDA"))])
                else:
                    values.extend(
                        [
                            self._format_signed_diff(kda, top500.get("KDA")),
                            damage_per_min,
                            self._format_signed_diff(damage_per_min, top500.get("damage/min")),
                            heal_per_min,
                            self._format_signed_diff(heal_per_min, top500.get("heal/min")),
                            taken_per_min,
                            self._format_signed_diff(taken_per_min, top500.get("taken/min")),
                        ]
                    )
            else:
                if self.detail_mode_all.isChecked():
                    values.extend([kda])
                else:
                    values.extend([kda, damage_per_min, heal_per_min, taken_per_min])

            for col_idx, value in enumerate(values):
                table.setItem(row_idx, col_idx, QTableWidgetItem(str(value)))

        table.horizontalScrollBar().setValue(0)
        layout.addWidget(table)
        box.table = table
        return box

    def _sync_camp_tables(self, left_box, right_box):
        if left_box is None or right_box is None:
            return

        left_table = left_box.table
        right_table = right_box.table
        left_table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        right_table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        left_table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        right_table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)

        self._sync_scrollbars(left_table.horizontalScrollBar(), right_table.horizontalScrollBar())
        self._sync_scrollbars(left_table.verticalScrollBar(), right_table.verticalScrollBar())
        left_table.viewport().installEventFilter(self)
        right_table.viewport().installEventFilter(self)
        self._mirror_scroll_positions(left_table, right_table)

    def _sync_scrollbars(self, bar_a, bar_b):
        def sync_to_other(value):
            if self._syncing_scroll:
                return
            self._syncing_scroll = True
            try:
                bar_b.setValue(value)
            finally:
                self._syncing_scroll = False

        def sync_back(value):
            if self._syncing_scroll:
                return
            self._syncing_scroll = True
            try:
                bar_a.setValue(value)
            finally:
                self._syncing_scroll = False

        bar_a.valueChanged.connect(sync_to_other)
        bar_b.valueChanged.connect(sync_back)

    def _mirror_scroll_positions(self, source_box, target_box):
        target_box.horizontalScrollBar().setValue(source_box.horizontalScrollBar().value())
        target_box.verticalScrollBar().setValue(source_box.verticalScrollBar().value())

    def eventFilter(self, watched, event):
        if event.type() in (QEvent.Type.Wheel, QEvent.Type.MouseMove):
            if self.self_table is not None and self.opp_table is not None:
                left_table = self.self_table.table
                right_table = self.opp_table.table
                if watched is left_table.viewport():
                    self._mirror_scroll_positions(left_table, right_table)
                elif watched is right_table.viewport():
                    self._mirror_scroll_positions(right_table, left_table)
        return super().eventFilter(watched, event)

    def _get_top500_stats(self, hero_id):
        if hero_id is None:
            return {}
        conn = sqlite3.connect(DB_PATH)
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT top500_kda,
                       top500_damage_per_minutes,
                       top500_healing_per_minutes,
                       top500_damage_taken_per_minutes
                FROM heroes_mst
                WHERE hero_id = ?
                """,
                (hero_id,),
            )
            row = cur.fetchone()
            if row is None:
                return {}
            return {
                "KDA": row[0],
                "damage/min": row[1],
                "heal/min": row[2],
                "taken/min": row[3],
            }
        finally:
            conn.close()

    def _avg(self, values):
        if not values:
            return ""
        return round(sum(values) / len(values), 1)

    def _std(self, values):
        if not values:
            return ""
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        return round(variance ** 0.5, 1)

    def _format_rate(self, value):
        if value is None:
            return ""
        return round(value, 1)

    def _unique_rates_by_player(self, rows):
        seen = set()
        rates = []
        for row in rows:
            player_uid = row["player_uid"]
            rate = row["current_rate"]
            if player_uid in seen or rate is None:
                continue
            seen.add(player_uid)
            rates.append(rate)
        return rates

    def _format_role(self, role_id):
        if role_id is None:
            return ""
        return {0: "Tank", 1: "DPS", 2: "Support"}.get(role_id, role_id)

    def _format_kda(self, k, d, a):
        if k is None or d is None or a is None:
            return ""
        if d == 0:
            return ""
        return round((k + a) / d, 2)

    def _format_per_minute(self, total_value, duration):
        if total_value is None or duration in (None, 0):
            return ""
        return round((total_value * 60) / duration, 1)

    def _format_signed_diff(self, value, base):
        if value in ("", None) or base in ("", None):
            return ""
        try:
            diff = round(float(value) - float(base), 1)
        except (TypeError, ValueError):
            return ""
        return self._format_signed(diff)

    def _format_signed(self, value):
        if value == 0:
            return "0"
        sign = "+" if value > 0 else "-"
        return f"{sign}{abs(value):.1f}"

    def _format_deviation_score(self, value, mean, std):
        if value in ("", None) or mean in ("", None) or std in ("", None) or std == 0:
            return ""
        try:
            return round(50 + 10 * ((float(value) - float(mean)) / float(std)), 1)
        except (TypeError, ValueError, ZeroDivisionError):
            return ""
