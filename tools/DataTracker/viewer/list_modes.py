from dataclasses import dataclass
from typing import Callable, Optional, Set


@dataclass
class ListQueryContext:
    conn: object
    cur: object
    selected_game_mode_ids: Set[int]
    selected_match_results: Set[str]
    target_player_uid: Optional[int]
    duo_player_uids: Set[int]
    duo_allowed: Callable[[str], bool]
    get_target_player_uid: Callable[[], Optional[int]]
    get_self_camp: Callable[[object, str, int], Optional[int]]
    is_player_in_camp: Callable[[object, str, int, int], bool]
    get_player_party_id: Callable[[object, int], Optional[int]]
    has_party_in_match_camp: Callable[[object, str, int, int], bool]
    get_match_result: Callable[[object, str, int], str]
    get_match_result_by_match: Callable[[object, str], str]
    split_rates_by_self_camp: Callable[[object, str, Optional[int]], tuple]
    split_rates_by_camp: Callable[[object, str], tuple]
    get_match_rate: Callable[[object, str, int], object]
    avg: Callable[[object], object]
    median: Callable[[object], object]
    min_: Callable[[object], object]
    max_: Callable[[object], object]
    variance: Callable[[object], object]
    std: Callable[[object], object]
    gap: Callable[[object, object, Callable[[object], object]], object]
    gap_value: Callable[[object, object, Callable[[object], object]], object]
    SQL_MATCH_LIST_BY_PLAYER: str = ""
    SQL_MATCH_COUNT_BY_PLAYER: str = ""
    SQL_MATCH_LIST_ALL: str = ""
    SQL_MATCH_COUNT_ALL: str = ""


class BaseListMode:
    name = "base"

    def is_all_search(self) -> bool:
        return False

    def load_matches(self, ctx: ListQueryContext):
        raise NotImplementedError

    def load_count(self, ctx: ListQueryContext):
        raise NotImplementedError


class PlayerListMode(BaseListMode):
    name = "player"

    def load_matches(self, ctx: ListQueryContext):
        target_player_uid = ctx.get_target_player_uid()
        if target_player_uid is None:
            raise ValueError("プレイヤーIDが不正です")
        ctx.cur.execute(ctx.SQL_MATCH_LIST_BY_PLAYER, (target_player_uid,))
        rows = []
        for match_uid, match_time_stamp, game_mode_id, replay_id in ctx.cur.fetchall():
            if ctx.selected_game_mode_ids and game_mode_id not in ctx.selected_game_mode_ids:
                continue
            self_camp = ctx.get_self_camp(ctx.cur, match_uid, target_player_uid)
            duo_mark = "×"
            if self_camp is not None:
                party_id = ctx.get_player_party_id(ctx.cur, target_player_uid)
                if party_id is not None and ctx.has_party_in_match_camp(ctx.cur, match_uid, self_camp, party_id):
                    duo_mark = "〇"
            if not ctx.duo_allowed(duo_mark):
                continue

            is_win = ctx.get_match_result(ctx.cur, match_uid, target_player_uid)
            if ctx.selected_match_results and is_win not in ctx.selected_match_results:
                continue

            my_rates, opp_rates = ctx.split_rates_by_self_camp(ctx.cur, match_uid, self_camp)
            all_rates = my_rates + opp_rates
            avg_my = ctx.avg(my_rates)
            avg_all = ctx.avg(all_rates)
            median_my = ctx.median(my_rates)
            median_opp = ctx.median(opp_rates)

            rows.append(
                {
                    "match_uid": match_uid,
                    "is_win": is_win,
                    "duo": duo_mark,
                    "rate_my": ctx.get_match_rate(ctx.cur, match_uid, target_player_uid),
                    "avg_my": avg_my,
                    "median_my": median_my,
                    "median_opp": median_opp,
                    "avg_all": avg_all,
                    "avg_opp": ctx.avg(opp_rates),
                    "avg_gap": ctx.gap(my_rates, opp_rates, ctx.avg),
                    "median_gap": ctx.gap([median_my] if median_my != "" else [], [median_opp] if median_opp != "" else [], ctx.median),
                    "min_my": ctx.min_(my_rates),
                    "min_opp": ctx.min_(opp_rates),
                    "min_gap": ctx.gap(my_rates, opp_rates, ctx.min_),
                    "max_my": ctx.max_(my_rates),
                    "max_opp": ctx.max_(opp_rates),
                    "max_gap": ctx.gap(my_rates, opp_rates, ctx.max_),
                    "var_my": ctx.variance(my_rates),
                    "var_opp": ctx.variance(opp_rates),
                    "std_my": ctx.std(my_rates),
                    "std_all": ctx.std(all_rates),
                    "self_camp": self_camp if self_camp is not None else "",
                    "match_time_stamp": match_time_stamp,
                    "game_mode_id": game_mode_id,
                    "replay_id": replay_id,
                }
            )
        return rows

    def load_count(self, ctx: ListQueryContext):
        target_player_uid = ctx.get_target_player_uid()
        if target_player_uid is None:
            return 0
        ctx.cur.execute(ctx.SQL_MATCH_COUNT_BY_PLAYER, (target_player_uid,))
        row = ctx.cur.fetchone()
        return 0 if row is None else row[0]


class AllListMode(BaseListMode):
    name = "all"

    def is_all_search(self) -> bool:
        return True

    def load_matches(self, ctx: ListQueryContext):
        ctx.cur.execute(ctx.SQL_MATCH_LIST_ALL)
        rows = []
        for match_uid, match_time_stamp, game_mode_id, replay_id in ctx.cur.fetchall():
            if ctx.selected_game_mode_ids and game_mode_id not in ctx.selected_game_mode_ids:
                continue
            is_win = ctx.get_match_result_by_match(ctx.cur, match_uid)
            if ctx.selected_match_results and is_win not in ctx.selected_match_results:
                continue
            camp0_rates, camp1_rates = ctx.split_rates_by_camp(ctx.cur, match_uid)
            avg_gap = abs(ctx.gap_value(camp0_rates, camp1_rates, ctx.avg))
            median_gap = abs(ctx.gap_value(camp0_rates, camp1_rates, ctx.median))
            min_gap = abs(ctx.gap_value(camp0_rates, camp1_rates, ctx.min_))
            max_gap = abs(ctx.gap_value(camp0_rates, camp1_rates, ctx.max_))
            rows.append(
                {
                    "match_uid": match_uid,
                    "is_win": ctx.get_match_result_by_match(ctx.cur, match_uid),
                    "duo": "",
                    "rate_my": "",
                    "avg_my": "",
                    "avg_all": "",
                    "avg_opp": "",
                    "avg_gap": avg_gap,
                    "median_gap": median_gap,
                    "min_my": "",
                    "min_opp": "",
                    "min_gap": min_gap,
                    "max_my": "",
                    "max_opp": "",
                    "max_gap": max_gap,
                    "var_my": "",
                    "var_opp": "",
                    "std_my": "",
                    "std_all": "",
                    "self_camp": "",
                    "match_time_stamp": match_time_stamp,
                    "game_mode_id": game_mode_id,
                    "replay_id": replay_id,
                }
            )
        return rows

    def load_count(self, ctx: ListQueryContext):
        ctx.cur.execute(ctx.SQL_MATCH_COUNT_ALL)
        row = ctx.cur.fetchone()
        return 0 if row is None else row[0]
