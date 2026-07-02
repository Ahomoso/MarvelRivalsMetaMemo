/* collector: Used to detect whether an incoming match UID already exists before registering it. */
SELECT match_uid
FROM matches_tbl
WHERE match_uid IN ({placeholders});
