/* collector: Used to remove a match header row before re-registering or pruning imported data. */
DELETE FROM matches_tbl
WHERE match_uid = ?;
