/* viewer: Used by the viewer to resolve a player's party identifier for match detail filtering. */
SELECT party_id
FROM party_member_mst
WHERE player_uid = ?
LIMIT 1;
