/* collector: Used to remove match player rows before re-registering a match. */
DELETE FROM match_players_tbl
WHERE match_uid = ?;
