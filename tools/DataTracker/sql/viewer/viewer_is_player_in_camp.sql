/* viewer: Used by the viewer to check whether a player belongs to a given camp in a match. */
SELECT 1
FROM match_players_tbl
WHERE match_uid = ? AND player_uid = ? AND camp = ?
LIMIT 1;
