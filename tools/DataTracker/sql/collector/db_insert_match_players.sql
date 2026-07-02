/* collector/db_register: Used when saving one player's row into match_players_tbl. */
INSERT OR REPLACE INTO match_players_tbl (
    match_uid, player_uid, nick_name, camp, cur_hero_id, current_rate,
    is_win, k, d, a, total_hero_damage, total_hero_heal, total_damage_taken,
    last_kill, solo_kill, session_hit_rate
) VALUES (
    ?, ?, ?, ?, ?, ?,
    ?, ?, ?, ?, ?, ?, ?,
    ?, ?, ?
);
