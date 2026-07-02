/* collector: Used to remove per-hero rows before re-registering a match. */
DELETE FROM match_player_heroes_tbl
WHERE match_uid = ?;
