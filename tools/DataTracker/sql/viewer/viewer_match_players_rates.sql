/* viewer: Used by the viewer to compare the current rates of all players in a match. */
SELECT camp, current_rate
FROM match_players_tbl
WHERE match_uid = ?
ORDER BY camp, player_uid;
