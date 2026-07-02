/* viewer: Used by the all-search list to fetch every stored match row. */
SELECT match_uid, match_time_stamp, game_mode_id, replay_id
FROM matches_tbl
ORDER BY match_time_stamp DESC;
