/* viewer: Used by the player search list to count matches for a single player. */
SELECT COUNT(*)
FROM matches_tbl AS m
WHERE EXISTS (
    SELECT 1
    FROM match_players_tbl AS mp
    WHERE mp.match_uid = m.match_uid
      AND mp.player_uid = ?
);
