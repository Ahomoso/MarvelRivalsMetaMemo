PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS heroes_mst (
  hero_id INTEGER PRIMARY KEY,
  hero_name TEXT,
  role_id INTEGER
);

CREATE TABLE IF NOT EXISTS code_mst (
  code_type TEXT NOT NULL,
  code_value TEXT NOT NULL,
  code_name TEXT NOT NULL,
  sort_order INTEGER,
  is_active INTEGER NOT NULL DEFAULT 1,
  PRIMARY KEY (code_type, code_value)
);

CREATE TABLE IF NOT EXISTS matches_tbl (
  match_uid TEXT PRIMARY KEY,
  source TEXT NOT NULL,
  match_time_stamp INTEGER,
  game_mode_id INTEGER,
  replay_id TEXT,
  match_play_duration REAL,
  mvp_uid INTEGER,
  mvp_hero_id INTEGER,
  svp_uid INTEGER,
  svp_hero_id INTEGER,
  raw_path TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS match_players_tbl (
  match_uid TEXT NOT NULL,
  player_uid INTEGER NOT NULL,
  nick_name TEXT,
  player_icon INTEGER,
  camp INTEGER,
  cur_hero_id INTEGER,
  is_win INTEGER,
  k INTEGER,
  d INTEGER,
  a INTEGER,
  total_hero_damage REAL,
  total_hero_heal REAL,
  total_damage_taken REAL,
  last_kill INTEGER,
  solo_kill INTEGER,
  session_hit_rate REAL,
  dynamic_fields_json TEXT,
  badge_ids_json TEXT,
  PRIMARY KEY (match_uid, player_uid)
);

CREATE TABLE IF NOT EXISTS match_player_heroes_tbl (
  match_uid TEXT NOT NULL,
  player_uid INTEGER NOT NULL,
  hero_id INTEGER NOT NULL,
  play_time REAL,
  k INTEGER,
  d INTEGER,
  a INTEGER,
  session_hit_rate REAL,
  PRIMARY KEY (match_uid, player_uid, hero_id)
);

INSERT OR IGNORE INTO code_mst (code_type, code_value, code_name, sort_order, is_active) VALUES
('camp', '0', 'Ally', NULL, 1),
('camp', '1', 'Oppo', NULL, 1),
('game_mode_id', '1', 'QuickMatch', 1, 1),
('game_mode_id', '2', 'RankMatch', 2, 1),
('game_mode_id', '3', 'CustomMatch', 3, 1),
('is_win', '0', 'lose', NULL, 1),
('is_win', '1', 'win', NULL, 1),
('login_os', '0', 'Unknown', NULL, 1),
('login_os', '1', 'PC', NULL, 1),
('login_os', '2', 'Console', NULL, 1),
('role_id', '0', 'Tank', 0, 1),
('role_id', '1', 'DPS', 1, 1),
('role_id', '2', 'Support', 2, 1);