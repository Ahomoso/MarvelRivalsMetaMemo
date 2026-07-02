/* collector/db_register: Used when saving per-hero breakdown rows into match_player_heroes_tbl. */
INSERT OR REPLACE INTO match_player_heroes_tbl (
    match_uid, player_uid, hero_id, play_time, k, d, a, session_hit_rate
) VALUES (
    ?, ?, ?, ?, ?, ?, ?, ?
);
