import json
import os
import sqlite3
import time
from glob import glob

from config import load_config, resolve_path
from sql_utils import load_sql


CONFIG = load_config()
DB_PATH = resolve_path(CONFIG.database_path)
MATCH_DIR = resolve_path(os.path.join(CONFIG.data_dir, "matches"))
SQL_INSERT_MATCHES = load_sql("collector/db_insert_matches.sql")
SQL_INSERT_MATCH_PLAYERS = load_sql("collector/db_insert_match_players.sql")
SQL_INSERT_MATCH_PLAYER_HEROES = load_sql("collector/db_insert_match_player_heroes.sql")
SQL_MATCH_UID_EXISTS = load_sql("collector/db_register_match_uid_in.sql")


def _load_match_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def register_matches_from_files(db_path: str = DB_PATH, match_dir: str = MATCH_DIR) -> int:
    total_start = time.perf_counter()
    match_paths = sorted(glob(os.path.join(match_dir, "*.json")))
    print(f"[db_register] found {len(match_paths)} json files in {match_dir}", flush=True)
    if not match_paths:
        return 0

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        inserted = 0
        for index, path in enumerate(match_paths, start=1):
            file_start = time.perf_counter()
            file_name = os.path.basename(path)
            print(f"[db_register] ({index}/{len(match_paths)}) start {file_name}", flush=True)

            load_start = time.perf_counter()
            payload = _load_match_json(path)
            print(
                f"[db_register] ({index}/{len(match_paths)}) loaded json in {time.perf_counter() - load_start:.3f}s",
                flush=True,
            )
            if not isinstance(payload, list):
                print(
                    f"[db_register] ({index}/{len(match_paths)}) skip non-list payload type={type(payload).__name__}",
                    flush=True,
                )
                continue

            build_start = time.perf_counter()
            match_rows = []
            player_rows = []
            hero_rows = []

            for data in payload:
                if not isinstance(data, dict):
                    continue
                match_uid = data.get("match_uid")
                if not match_uid:
                    continue

                match_rows.append(
                    (
                        match_uid,
                        "rivalsmeta",
                        data.get("match_time_stamp"),
                        data.get("game_mode_id"),
                        data.get("replay_id"),
                        data.get("match_play_duration"),
                        data.get("mvp_uid"),
                        data.get("mvp_hero_id"),
                        data.get("svp_uid"),
                        data.get("svp_hero_id"),
                    )
                )

                for player in data.get("match_players") or []:
                    dynamic_fields = player.get("dynamic_fields") or {}
                    player_rows.append(
                        (
                            match_uid,
                            player.get("player_uid"),
                            player.get("nick_name"),
                            player.get("camp"),
                            player.get("cur_hero_id"),
                            dynamic_fields.get("new_score"),
                            player.get("is_win"),
                            player.get("k"),
                            player.get("d"),
                            player.get("a"),
                            player.get("total_hero_damage"),
                            player.get("total_hero_heal"),
                            player.get("total_damage_taken"),
                            player.get("last_kill"),
                            player.get("solo_kill"),
                            player.get("session_hit_rate"),
                        )
                    )

                    for hero in player.get("player_heroes") or []:
                        hero_rows.append(
                            (
                                match_uid,
                                player.get("player_uid"),
                                hero.get("hero_id"),
                                hero.get("play_time"),
                                hero.get("k"),
                                hero.get("d"),
                                hero.get("a"),
                                hero.get("session_hit_rate"),
                            )
                        )

            print(
                f"[db_register] ({index}/{len(match_paths)}) built rows matches={len(match_rows)} players={len(player_rows)} heroes={len(hero_rows)} in {time.perf_counter() - build_start:.3f}s",
                flush=True,
            )

            uid_list = [row[0] for row in match_rows]
            existing_uids = set()
            if uid_list:
                lookup_start = time.perf_counter()
                chunk_size = 500
                for offset in range(0, len(uid_list), chunk_size):
                    chunk = uid_list[offset : offset + chunk_size]
                    placeholders = ",".join("?" for _ in chunk)
                    query = SQL_MATCH_UID_EXISTS.format(placeholders=placeholders)
                    existing_uids.update(row[0] for row in conn.execute(query, chunk))
                print(
                    f"[db_register] ({index}/{len(match_paths)}) existing uid lookup found {len(existing_uids)} in {time.perf_counter() - lookup_start:.3f}s",
                    flush=True,
                )

            if existing_uids:
                keep_match_rows = [row for row in match_rows if row[0] not in existing_uids]
                keep_uids = {row[0] for row in keep_match_rows}
                keep_player_rows = [row for row in player_rows if row[0] in keep_uids]
                keep_hero_rows = [row for row in hero_rows if row[0] in keep_uids]
                print(
                    f"[db_register] ({index}/{len(match_paths)}) skip existing matches={len(match_rows) - len(keep_match_rows)} keep matches={len(keep_match_rows)} players={len(keep_player_rows)} heroes={len(keep_hero_rows)}",
                    flush=True,
                )
            else:
                keep_match_rows = match_rows
                keep_player_rows = player_rows
                keep_hero_rows = hero_rows

            if not keep_match_rows:
                print(
                    f"[db_register] ({index}/{len(match_paths)}) nothing new to insert, skip file",
                    flush=True,
                )
                continue

            insert_start = time.perf_counter()
            if keep_match_rows:
                conn.executemany(SQL_INSERT_MATCHES, keep_match_rows)
            print(
                f"[db_register] ({index}/{len(match_paths)}) insert matches done in {time.perf_counter() - insert_start:.3f}s",
                flush=True,
            )
            insert_start = time.perf_counter()
            if keep_player_rows:
                conn.executemany(SQL_INSERT_MATCH_PLAYERS, keep_player_rows)
            print(
                f"[db_register] ({index}/{len(match_paths)}) insert players done in {time.perf_counter() - insert_start:.3f}s",
                flush=True,
            )
            insert_start = time.perf_counter()
            if keep_hero_rows:
                conn.executemany(SQL_INSERT_MATCH_PLAYER_HEROES, keep_hero_rows)
            print(
                f"[db_register] ({index}/{len(match_paths)}) insert heroes done in {time.perf_counter() - insert_start:.3f}s",
                flush=True,
            )

            commit_start = time.perf_counter()
            conn.commit()
            print(
                f"[db_register] ({index}/{len(match_paths)}) commit done in {time.perf_counter() - commit_start:.3f}s",
                flush=True,
            )
            inserted += 1
            print(
                f"[db_register] ({index}/{len(match_paths)}) finished {file_name} total={time.perf_counter() - file_start:.3f}s",
                flush=True,
            )
        print(f"[db_register] all done inserted={inserted} total={time.perf_counter() - total_start:.3f}s", flush=True)
        return inserted
    finally:
        conn.close()
