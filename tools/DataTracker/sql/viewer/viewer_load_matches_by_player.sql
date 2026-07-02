/* viewer: Used by the player search list to fetch match rows for a single player. */
SELECT m.match_uid, m.match_time_stamp, m.game_mode_id, m.replay_id
FROM matches_tbl AS m
WHERE EXISTS (
    SELECT 1
    FROM match_players_tbl AS mp
    WHERE mp.match_uid = m.match_uid
      AND mp.player_uid = ?
)
ORDER BY m.match_time_stamp DESC;
