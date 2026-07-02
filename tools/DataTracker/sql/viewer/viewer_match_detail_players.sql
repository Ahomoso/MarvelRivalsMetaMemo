/* viewer: Used by the match detail window to display all players in a match, grouped by camp and role. */
SELECT
    mp.camp,
    mp.player_uid,
    mp.nick_name,
    mp.is_win,
    mp.current_rate,
    mp.cur_hero_id,
    hm.hero_name,
    hm.role_id,
    mp.k,
    mp.d,
    mp.a,
    mp.total_hero_damage,
    mp.total_hero_heal,
    mp.total_damage_taken,
    m.match_play_duration
FROM match_players_tbl AS mp
LEFT JOIN heroes_mst AS hm
    ON hm.hero_id = mp.cur_hero_id
LEFT JOIN matches_tbl AS m
    ON m.match_uid = mp.match_uid
WHERE mp.match_uid = ?
ORDER BY
    mp.camp,
    CASE hm.role_id
        WHEN 0 THEN 0
        WHEN 1 THEN 1
        WHEN 2 THEN 2
        ELSE 3
    END,
    mp.current_rate DESC,
    mp.player_uid ASC;
