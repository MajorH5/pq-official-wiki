CREATE TABLE /*_*/pq_roblox_link (
  prl_id int unsigned NOT NULL AUTO_INCREMENT,
  prl_user_id int unsigned NOT NULL,
  prl_roblox_user_id bigint unsigned NOT NULL,
  prl_created_unix bigint unsigned NOT NULL,
  PRIMARY KEY (prl_id),
  UNIQUE KEY prl_roblox_user_id (prl_roblox_user_id),
  UNIQUE KEY prl_user_id (prl_user_id)
) /*$wgDBTableOptions*/;
