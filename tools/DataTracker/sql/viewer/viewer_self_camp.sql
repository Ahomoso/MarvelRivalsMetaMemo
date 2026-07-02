/* viewer: Used by the viewer to resolve the target player's own camp in a match. */
SELECT camp
FROM match_players_tbl
WHERE match_uid = ? AND player_uid = ?
LIMIT 1;
