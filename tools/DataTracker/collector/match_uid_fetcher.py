import json
import os
import time
from selenium.webdriver.common.by import By


def _parse_player_ids(player_ids: str):
    result = []
    for part in (player_ids or "").split(","):
        value = part.strip()
        if value:
            result.append(value)
    return result


def fetch_match_uids(driver, player_id: str, season: int, output_path="data/match_uids.json"):
    all_match_uids = []
    seen = set()
    target_player_ids = _parse_player_ids(player_id)
    for target_player_id in target_player_ids:
        for skip in range(0, 1000, 20):
            url = (
                f"https://rivalsmeta.com/api/player-match-history/{target_player_id}"
                f"?skip={skip}&game_mode_id=0&hero_id=0&season={season}"
            )
            driver.get(url)
            time.sleep(0.5)
            text = driver.find_element(By.TAG_NAME, "body").text
            batch = json.loads(text)
            if not batch:
                break
            for match in batch:
                match_uid = match.get("match_uid")
                if match_uid and match_uid not in seen:
                    seen.add(match_uid)
                    all_match_uids.append(match_uid)
            if len(batch) < 20:
                break

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_match_uids, f, ensure_ascii=False, indent=4)
    return all_match_uids
