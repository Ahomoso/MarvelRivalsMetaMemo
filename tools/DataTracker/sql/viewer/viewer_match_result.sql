/* viewer: Used by the viewer to resolve win/lose for a specific player in a match. */
SELECT is_win
FROM match_players_tbl
WHERE match_uid = ? AND player_uid = ?
LIMIT 1;
