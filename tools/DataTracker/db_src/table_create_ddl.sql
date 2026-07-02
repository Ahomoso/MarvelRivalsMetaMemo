PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS heroes_mst (
  hero_id INTEGER PRIMARY KEY,
  hero_name TEXT,
  role_id INTEGER,
  slug TEXT,
  top500_kda REAL,
  top500_accuracy REAL,
  top500_damage_per_minutes REAL,
  top500_damage_taken_per_minutes REAL,
  top500_healing_per_minutes REAL
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
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS match_players_tbl (
  match_uid TEXT NOT NULL,
  player_uid INTEGER NOT NULL,
  nick_name TEXT,
  camp INTEGER,
  cur_hero_id INTEGER,
  current_rate REAL,
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

CREATE TABLE IF NOT EXISTS party_mst (
  party_id INTEGER PRIMARY KEY AUTOINCREMENT,
  party_name TEXT NOT NULL,
  memo TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS party_member_mst (
  party_id INTEGER NOT NULL,
  player_uid INTEGER NOT NULL,
  valid_from TEXT,
  valid_to TEXT,
  memo TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now')),
  PRIMARY KEY (party_id, player_uid),
  FOREIGN KEY (party_id) REFERENCES party_mst(party_id) ON DELETE CASCADE
);

INSERT OR IGNORE INTO party_mst (party_id, party_name, memo) VALUES
(1, 'たへー宅', '1032997637 / 693888859 / 1254677174');

INSERT OR IGNORE INTO party_member_mst (party_id, player_uid, valid_from, valid_to, memo) VALUES
(1, 1032997637, NULL, NULL, NULL),
(1, 693888859, NULL, NULL, NULL),
(1, 1254677174, NULL, NULL, NULL);

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
