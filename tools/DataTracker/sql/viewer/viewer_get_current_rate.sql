/* viewer: Used by the viewer to resolve the current rate for a match player row. */
SELECT current_rate
FROM match_players_tbl
WHERE match_uid = ? AND player_uid = ?
LIMIT 1;
