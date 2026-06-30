import json
import os
import time
from selenium.webdriver.common.by import By


def fetch_match_details(
    driver,
    input_path="data/match_uids.json",
    output_dir="data/matches"
):
    with open(input_path, "r", encoding="utf-8") as f:
        match_uids = json.load(f)

    os.makedirs(output_dir, exist_ok=True)

    saved = 0

    for i, match_uid in enumerate(match_uids, start=1):
        output_path = os.path.join(output_dir, f"{match_uid}.json")

        if os.path.exists(output_path):
            print(f"[{i}/{len(match_uids)}] 既存: {match_uid}")
            continue

        url = f"https://rivalsmeta.com/api/matches/{match_uid}"

        print(f"[{i}/{len(match_uids)}] 詳細取得: {match_uid}")
        driver.get(url)
        time.sleep(0.5)

        text = driver.find_element(By.TAG_NAME, "body").text
        detail = json.loads(text)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(detail, f, ensure_ascii=False, indent=4)

        saved += 1

    return saved