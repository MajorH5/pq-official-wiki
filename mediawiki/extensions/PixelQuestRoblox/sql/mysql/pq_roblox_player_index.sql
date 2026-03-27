-- Lightweight index: Roblox user id -> display username (game server pushes; profile views refresh).
-- Primary key is roblox_user_id only (no surrogate id) so schema matches partial/manual installs.
CREATE TABLE pq_roblox_player_index (
	roblox_user_id BIGINT UNSIGNED NOT NULL,
	username_normalized VARCHAR(64) NOT NULL,
	username_display VARCHAR(64) NOT NULL,
	updated_at BINARY(14) NOT NULL,
	PRIMARY KEY (roblox_user_id),
	KEY pq_roblox_player_index_name (username_normalized)
) /*$wgDBTableOptions*/;
