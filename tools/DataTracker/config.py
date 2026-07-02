import json
import os
from dataclasses import dataclass


CONFIG_PATH = os.path.abspath("app_config.json")


@dataclass(frozen=True)
class AppConfig:
    app_name: str
    launcher_title: str
    collector_title: str
    viewer_title: str
    database_path: str
    default_player_uid: str
    season: int
    chrome_path: str
    chrome_debug_port: int
    chrome_user_data_dir: str
    data_dir: str
    debug_mode: bool


def load_config(path: str = CONFIG_PATH) -> AppConfig:
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return AppConfig(**raw)


def resolve_path(path: str) -> str:
    return os.path.abspath(path)
