import json
import os
import sqlite3
import time
from selenium.webdriver.common.by import By

from config import load_config, resolve_path
from sql_utils import load_sql


CONFIG = load_config()
SQL_MATCH_UIDS_ALL = load_sql("collector/collector_match_detail_fetcher_match_uids.sql")


def _load_existing_match_uids(db_path: str) -> set[str]:
    if not os.path.exists(db_path):
        return set()

    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(SQL_MATCH_UIDS_ALL).fetchall()
        return {row[0] for row in rows if row and row[0]}
    finally:
        conn.close()


def fetch_match_details(driver, player_uid: str, input_path=None, output_dir=None, db_path=None):
    if input_path is None:
        input_path = resolve_path(os.path.join(CONFIG.data_dir, "match_uids.json"))
    if output_dir is None:
        output_dir = resolve_path(os.path.join(CONFIG.data_dir, "matches"))
    if db_path is None:
        db_path = resolve_path(CONFIG.database_path)

    with open(input_path, "r", encoding="utf-8") as f:
        match_uids = json.load(f)

    existing_match_uids = _load_existing_match_uids(db_path)
    if existing_match_uids:
        before = len(match_uids)
        match_uids = [match_uid for match_uid in match_uids if match_uid not in existing_match_uids]
        print(
            f"[match_detail_fetcher] skipped {before - len(match_uids)} already-registered match_uids",
            flush=True,
        )

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{player_uid}.json")
    details = []
    for i, match_uid in enumerate(match_uids, start=1):
        url = f"https://rivalsmeta.com/api/matches/{match_uid}"
        driver.get(url)
        time.sleep(0.5)
        text = driver.find_element(By.TAG_NAME, "body").text
        detail = json.loads(text)
        details.append(detail)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(details, f, ensure_ascii=False, indent=4)

    return len(details)
