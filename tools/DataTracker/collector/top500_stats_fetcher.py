import sqlite3
import time

from selenium.webdriver.common.by import By

from config import load_config, resolve_path


CONFIG = load_config()
DB_PATH = resolve_path(CONFIG.database_path)

def _extract_top500_kda(text: str):
    import re

    match = re.search(r"KDA\s*[:\s]*([0-9]+(?:\.[0-9]+)?)", text)
    if match:
        return float(match.group(1))
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*KDA\b", text)
    if match:
        return float(match.group(1))
    return None


def _parse_stat_blocks(driver):
    import re

    stat_map = {}
    stat_blocks = []
    for selector in ("div.middle.second div.stat", "div.line-stats div.stat", "div.stat"):
        try:
            stat_blocks.extend(driver.find_elements(By.CSS_SELECTOR, selector))
        except Exception:
            continue

    for stat in stat_blocks:
        try:
            raw_text = stat.text.strip()
        except Exception:
            continue

        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        if not lines:
            continue

        label = lines[0]
        value_text = " ".join(lines[1:]) if len(lines) > 1 else raw_text
        value_match = re.search(r"(\d+(?:\.\d+)?)", value_text)
        if not value_match:
            continue

        value = float(value_match.group(1))
        stat_map[label] = value
        lower_label = label.lower()
        if "accuracy" in lower_label:
            stat_map["Accuracy"] = value
        if "damage taken" in lower_label:
            stat_map["Damage Taken"] = value
        if lower_label == "damage":
            stat_map["Damage"] = value
        if lower_label == "healing":
            stat_map["Healing"] = value
    return stat_map


def _extract_damage_stats(driver):
    stat_map = _parse_stat_blocks(driver)
    return {
        "accuracy": stat_map.get("Accuracy") or stat_map.get("accuracy"),
        "damage": stat_map.get("Damage"),
        "damage_taken": stat_map.get("Damage Taken"),
        "healing": stat_map.get("Healing"),
    }


def fetch_top500_stats(driver):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT hero_id, hero_name, slug FROM heroes_mst ORDER BY hero_id"
    )
    heroes = cur.fetchall()

    updated = 0
    for hero_id, hero_name, slug in heroes:
        if not slug:
            print(f"[top500] SKIP {hero_id} {hero_name}: slug is empty")
            continue
        url = f"https://rivalsmeta.com/characters/{slug}/stats"
        print(f"[top500] GET {hero_id} {hero_name} -> {url}")
        driver.get(url)
        time.sleep(0.8)
        body_text = driver.find_element(By.TAG_NAME, "body").text
        kda = _extract_top500_kda(body_text)
        damage_stats = _extract_damage_stats(driver)
        accuracy = damage_stats["accuracy"]
        damage = damage_stats["damage"]
        damage_taken = damage_stats["damage_taken"]
        healing = damage_stats["healing"]
        cur.execute(
            """
            UPDATE heroes_mst
            SET top500_kda = ?,
                top500_accuracy = ?,
                top500_damage_per_minutes = ?,
                top500_damage_taken_per_minutes = ?,
                top500_healing_per_minutes = ?
            WHERE hero_id = ?
            """,
            (kda, accuracy, damage, damage_taken, healing, hero_id),
        )
        conn.commit()
        updated += 1

    conn.close()
    return updated
