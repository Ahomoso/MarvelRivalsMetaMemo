/* viewer: Used by the match detail window to display top500 reference stats for a hero. */
SELECT top500_kda,
       top500_accuracy,
       top500_damage_per_minutes,
       top500_healing_per_minutes,
       top500_damage_taken_per_minutes
FROM heroes_mst
WHERE hero_id = ?;
