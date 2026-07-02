/* collector: Used when pruning non-ranked matches before re-registering collected data. */
SELECT match_uid
FROM matches_tbl
WHERE game_mode_id IN (1, 3);
