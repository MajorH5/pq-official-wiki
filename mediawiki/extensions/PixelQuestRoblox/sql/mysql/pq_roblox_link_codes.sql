CREATE TABLE /*_*/pq_roblox_link_codes (
  prlc_id int unsigned NOT NULL AUTO_INCREMENT,
  prlc_roblox_user_id bigint unsigned NOT NULL,
  prlc_code varchar(16) NOT NULL,
  prlc_expires_unix bigint unsigned NOT NULL,
  prlc_created_unix bigint unsigned NOT NULL,
  PRIMARY KEY (prlc_id),
  UNIQUE KEY prlc_roblox_user_id (prlc_roblox_user_id),
  UNIQUE KEY prlc_code (prlc_code)
) /*$wgDBTableOptions*/;
