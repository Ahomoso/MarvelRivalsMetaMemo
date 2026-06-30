import json
import os
import time
from selenium.webdriver.common.by import By


def fetch_match_uids(driver, player_id: str, season: int, output_path="data/match_uids.json"):
    all_matches = []

    for skip in range(0, 1000, 20):
        url = (
            f"https://rivalsmeta.com/api/player-match-history/{player_id}"
            f"?skip={skip}"
            f"&game_mode_id=0"
            f"&hero_id=0"
            f"&season={season}"
        )

        print(f"取得中: skip={skip}")
        driver.get(url)
        time.sleep(0.5)

        text = driver.find_element(By.TAG_NAME, "body").text
        batch = json.loads(text)

        if not batch:
            break

        all_matches.extend(batch)

        if len(batch) < 20:
            break

    match_uids = [m["match_uid"] for m in all_matches]

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(match_uids, f, ensure_ascii=False, indent=4)

    return match_uids