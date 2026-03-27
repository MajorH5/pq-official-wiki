<?php

namespace PixelQuestRoblox\Service;

/**
 * Best-effort extraction from save data (multiple __dataVersion shapes).
 */
final class PqRobloxPlayerDataParser {

	/**
	 * @param array<string, mixed> $root
	 * @return array<string, mixed>
	 */
	public static function getCharactersMap( array $root ): array {
		$c = $root['characters'] ?? null;
		if ( !is_array( $c ) ) {
			return [];
		}
		$out = [];
		foreach ( $c as $k => $row ) {
			if ( is_array( $row ) ) {
				$out[(string)$k] = $row;
			}
		}
		return $out;
	}

	/**
	 * @param array<string, mixed> $root
	 */
	public static function getGraveyardList( array $root ): array {
		$g = $root['graveyard'] ?? null;
		if ( !is_array( $g ) ) {
			return [];
		}
		return array_values( $g );
	}

	/**
	 * @param array<string, mixed> $root
	 * @return array<string, mixed>
	 */
	public static function getVaultSlots( array $root ): array {
		$v = $root['vaultSlots'] ?? null;
		if ( !is_array( $v ) ) {
			return [];
		}
		return $v;
	}

	/**
	 * @param array<string, mixed> $root
	 * @return array<string, int>
	 */
	public static function getSkinsQuantityMap( array $root ): array {
		$s = $root['skins'] ?? null;
		if ( !is_array( $s ) ) {
			return [];
		}
		$out = [];
		foreach ( $s as $id => $qty ) {
			$out[(string)$id] = max( 0, (int)$qty );
		}
		return $out;
	}

	public static function getAccountValor( array $root ): ?float {
		if ( !array_key_exists( 'valor', $root ) ) {
			return null;
		}
		$v = $root['valor'];
		if ( !is_scalar( $v ) ) {
			return null;
		}
		return (float)$v;
	}

	/**
	 * Account-wide level from root save (best-effort keys).
	 */
	public static function getAccountLevel( array $root ): ?int {
		foreach ( [ 'accountLevel', 'AccountLevel', 'account_level', 'totalLevel', 'TotalLevel' ] as $k ) {
			if ( !array_key_exists( $k, $root ) ) {
				continue;
			}
			$v = $root[$k];
			if ( is_int( $v ) || is_float( $v ) ) {
				return (int)$v;
			}
			if ( is_string( $v ) && is_numeric( $v ) ) {
				return (int)$v;
			}
		}
		return null;
	}

	/**
	 * @param array<string, mixed> $char
	 */
	public static function getCharacterLevel( array $char ): ?int {
		foreach ( [ 'level', 'Level', 'characterLevel', 'CharacterLevel' ] as $k ) {
			if ( !array_key_exists( $k, $char ) ) {
				continue;
			}
			$v = $char[$k];
			if ( is_int( $v ) || is_float( $v ) ) {
				return (int)$v;
			}
			if ( is_string( $v ) && is_numeric( $v ) ) {
				return (int)$v;
			}
		}
		return null;
	}

	/**
	 * @param array<string, mixed> $char
	 */
	public static function characterValorFromExp( array $char ): float {
		$exp = isset( $char['experience'] ) ? (float)$char['experience'] : 0.0;
		return floor( $exp / 1500.0 );
	}

	/**
	 * @return array<string, scalar|string>
	 */
	public static function normalizeStats( mixed $raw ): array {
		if ( !is_array( $raw ) ) {
			return [];
		}
		$keys = array_keys( $raw );
		$isAssoc = $keys !== range( 0, count( $raw ) - 1 );
		$out = [];
		if ( $isAssoc ) {
			foreach ( $raw as $k => $v ) {
				if ( is_array( $v ) ) {
					continue;
				}
				if ( is_scalar( $v ) ) {
					$out[(string)$k] = $v;
				}
			}
			return $out;
		}
		$list = array_values( $raw );
		for ( $i = 0; $i + 1 < count( $list ); $i += 2 ) {
			if ( is_scalar( $list[$i] ) ) {
				$out[(string)$list[$i]] = $list[$i + 1];
			}
		}
		return $out;
	}

	/**
	 * Graveyard record field by 1-based index (Lua-style). For list rows: index 1 = time, 2 = cause, 3 = level,
	 * 4 = valor, 5 = accolades, 6 = skin id, 7–10 = primary/secondary/armor/accessory, 11 = stats array, …
	 */
	public static function graveField( mixed $rec, int $luaIndex ): mixed {
		if ( !is_array( $rec ) ) {
			return null;
		}
		if ( array_key_exists( 0, $rec ) ) {
			$zero = $luaIndex - 1;
			if ( $zero >= 0 && array_key_exists( $zero, $rec ) ) {
				return $rec[$zero];
			}
		}
		if ( array_key_exists( $luaIndex, $rec ) ) {
			return $rec[$luaIndex];
		}
		$sk = (string)$luaIndex;
		if ( array_key_exists( $sk, $rec ) ) {
			return $rec[$sk];
		}
		return null;
	}

	/**
	 * Item id 0 = empty slot (game sentinel).
	 *
	 * @param array<string, mixed>|null $item
	 * @return array{id:int, quantity:int, metadata:mixed}|null
	 */
	/**
	 * Equipped slot or grave equipment: may be a bare id or `{ id, quantity, metadata }`.
	 */
	public static function equippedItemIdFromField( mixed $raw ): int {
		if ( $raw === null || $raw === 'nil' ) {
			return 0;
		}
		if ( is_array( $raw ) ) {
			$norm = self::normalizeItemBlob( $raw );
			return ( $norm !== null && $norm['id'] > 0 ) ? $norm['id'] : 0;
		}
		return (int)$raw;
	}

	public static function normalizeItemBlob( ?array $item ): ?array {
		if ( $item === null ) {
			return null;
		}
		$id = isset( $item['id'] ) ? (int)$item['id'] : ( isset( $item['Id'] ) ? (int)$item['Id'] : 0 );
		if ( $id < 0 ) {
			return null;
		}
		if ( $id === 0 ) {
			return [ 'id' => 0, 'quantity' => 0, 'metadata' => null ];
		}
		$q = isset( $item['quantity'] ) ? (int)$item['quantity'] : ( isset( $item['Quantity'] ) ? (int)$item['Quantity'] : 0 );
		$meta = $item['metadata'] ?? $item['Metadata'] ?? null;
		return [ 'id' => $id, 'quantity' => max( 0, $q ), 'metadata' => $meta ];
	}

	/**
	 * Declared inventory capacity (defaults to 8 if unknown).
	 *
	 * @param array<string, mixed> $char
	 */
	public static function getInventorySlotCount( array $char ): int {
		foreach ( [ 'inventorySlots', 'InventorySlots', 'totalInventorySlots', 'inventorySlotCount' ] as $k ) {
			if ( isset( $char[$k] ) && is_numeric( $char[$k] ) ) {
				return max( 0, (int)$char[$k] );
			}
		}
		$inv = $char['inventory'] ?? [];
		if ( is_array( $inv ) && $inv !== [] ) {
			$maxKey = 0;
			foreach ( array_keys( $inv ) as $k ) {
				if ( is_int( $k ) || ( is_string( $k ) && ctype_digit( $k ) ) ) {
					$maxKey = max( $maxKey, (int)$k );
				}
			}
			return max( 8, $maxKey );
		}
		return 8;
	}

	/**
	 * Displayable "last seen": prefer `lastSeenTimestampUTC` (seconds; ignore 0/-1),
	 * else fallback to envelope metadata `MetaData.LastUpdate` unix timestamp.
	 *
	 * @return array{unix:int, approximate:bool}|null
	 */
	public static function resolveLastSeenForDisplay( array $root ): ?array {
		foreach ( [ 'lastSeenTimestampUTC', 'LastSeenTimestampUTC' ] as $k ) {
			if ( !array_key_exists( $k, $root ) ) {
				continue;
			}
			$v = $root[$k];
			if ( !is_numeric( $v ) ) {
				continue;
			}
			$t = (float)$v;
			// Some sources send ms or μs; normalize to seconds.
			while ( $t > 1e12 ) {
				$t /= 1000.0;
			}
			$ti = (int)floor( $t );
			if ( $ti > 0 ) {
				return [ 'unix' => $ti, 'approximate' => false ];
			}
		}

		$meta = $root['MetaData'] ?? $root['metadata'] ?? $root['Metadata'] ?? null;
		if ( is_array( $meta ) ) {
			$lu = $meta['LastUpdate'] ?? $meta['lastUpdate'] ?? $meta['lastupdate'] ?? null;
			if ( is_numeric( $lu ) ) {
				$t = (float)$lu;
				while ( $t > 1e12 ) {
					$t /= 1000.0;
				}
				$ti = (int)floor( $t );
				if ( $ti > 0 ) {
					return [ 'unix' => $ti, 'approximate' => true ];
				}
			}
		}
		return null;
	}

	/**
	 * Account-owned badge ids (no quantities). Root key "badges".
	 *
	 * @return int[]
	 */
	public static function getOwnedBadgeIds( array $root ): array {
		$b = $root['badges'] ?? $root['Badges'] ?? null;
		if ( !is_array( $b ) ) {
			return [];
		}
		$out = [];
		foreach ( $b as $v ) {
			if ( is_numeric( $v ) ) {
				$i = (int)$v;
				if ( $i > 0 ) {
					$out[] = $i;
				}
			}
		}
		return $out;
	}

	/**
	 * Account equipped badge (0 = none). Lives on unwrapped save root, not per character.
	 */
	public static function getEquippedPlayerBadgeId( array $root ): int {
		foreach ( [ 'equippedPlayerBadge', 'EquippedPlayerBadge' ] as $k ) {
			if ( array_key_exists( $k, $root ) && is_numeric( $root[$k] ) ) {
				$i = (int)$root[$k];
				return $i > 0 ? $i : 0;
			}
		}

		return 0;
	}

	/**
	 * Equipped badge on a character (0 = none). Legacy / fallback only; prefer getEquippedPlayerBadgeId().
	 */
	public static function getEquippedBadgeIdForCharacter( array $char ): int {
		foreach ( [ 'equippedPlayerBadge', 'EquippedPlayerBadge' ] as $k ) {
			if ( array_key_exists( $k, $char ) && is_numeric( $char[$k] ) ) {
				return (int)$char[$k];
			}
		}
		return 0;
	}

	/**
	 * Completed achievement ids from Data.progressTrackers.achievements.completed
	 *
	 * After profile unwrap (PqRobloxDataStoreClient), the save root is often the inner `Data`
	 * object — progressTrackers live at root, not under a nested `Data` key.
	 *
	 * @return int[]
	 */
	public static function getCompletedAchievementIds( array $root ): array {
		$inner = $root;
		if ( isset( $root['Data'] ) && is_array( $root['Data'] ) ) {
			$inner = $root['Data'];
		} elseif ( isset( $root['data'] ) && is_array( $root['data'] ) ) {
			$inner = $root['data'];
		}
		$pt = $inner['progressTrackers'] ?? $inner['ProgressTrackers'] ?? null;
		if ( !is_array( $pt ) ) {
			return [];
		}
		$ach = $pt['achievements'] ?? $pt['Achievements'] ?? null;
		if ( !is_array( $ach ) ) {
			return [];
		}
		$done = $ach['completed'] ?? $ach['Completed'] ?? null;
		if ( !is_array( $done ) ) {
			return [];
		}
		$out = [];
		foreach ( $done as $v ) {
			if ( is_numeric( $v ) ) {
				$i = (int)$v;
				if ( $i > 0 ) {
					$out[] = $i;
				}
			}
		}
		return $out;
	}
}
