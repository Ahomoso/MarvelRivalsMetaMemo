/* collector/db_register: Used when saving a scraped match header into matches_tbl. */
INSERT OR REPLACE INTO matches_tbl (
    match_uid, source, match_time_stamp, game_mode_id, replay_id,
    match_play_duration, mvp_uid, mvp_hero_id, svp_uid, svp_hero_id
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
