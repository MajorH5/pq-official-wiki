<?php

namespace PixelQuestRoblox\Service;

use PixelQuestRoblox\PqRobloxTextureNames;
use PixelQuestRoblox\PqRobloxWikiFileUrl;

/**
 * Honor total from completed achievements (HonorBoost rewards) + rank from datadump ranges.
 */
final class PqRobloxHonorService {

	/** @var array<string, array{total:float, rankId:int}> */
	private static $cache = [];

	public static function resetCacheForTests(): void {
		self::$cache = [];
	}

	/**
	 * @param array<string, mixed> $playerData
	 * @return array{total:float, rankId:int}
	 */
	public static function computeForPlayerData(
		PqRobloxLookupIndex $lookup,
		array $playerData,
		int $robloxUserId
	): array {
		$ids = PqRobloxPlayerDataParser::getCompletedAchievementIds( $playerData );
		$key = $robloxUserId . '|' . md5( json_encode( $ids ) );
		if ( isset( self::$cache[$key] ) ) {
			return self::$cache[$key];
		}
		$maxAttainable = $lookup->getMaxAttainableHonorPoints();
		if ( $maxAttainable <= 0 ) {
			$out = [ 'total' => 0.0, 'rankId' => 0 ];
			self::$cache[$key] = $out;
			return $out;
		}
		$total = 0.0;
		foreach ( $ids as $aid ) {
			$row = $lookup->getAchievementRow( (int)$aid );
			if ( $row === null ) {
				continue;
			}
			$rewards = $row['Rewards'] ?? $row['rewards'] ?? null;
			if ( !is_array( $rewards ) ) {
				continue;
			}
			foreach ( $rewards as $rw ) {
				if ( !is_array( $rw ) ) {
					continue;
				}
				$t = (string)( $rw['Type'] ?? $rw['type'] ?? '' );
				if ( $t !== 'HonorBoost' ) {
					continue;
				}
				$v = $rw['Value'] ?? $rw['value'] ?? 0;
				if ( is_numeric( $v ) ) {
					$total += (float)$v;
				}
			}
		}
		// Same as game: normalized = (honor / MaxAttainableHonorPoints) * 100
		$normalized = ( $total / $maxAttainable ) * 100.0;
		$rankId = $lookup->rankIdFromHonorPercent( $normalized );
		$out = [ 'total' => $total, 'rankId' => $rankId ];
		self::$cache[$key] = $out;
		return $out;
	}

	public static function honorIconUrlForRank( PqRobloxLookupIndex $lookup, int $rankId ): ?string {
		$name = $lookup->getHonorDisplayNameForRankId( $rankId );
		$base = PqRobloxTextureNames::honorIconBase( $name );
		return PqRobloxWikiFileUrl::forFilename( $base . '.png' );
	}
}
