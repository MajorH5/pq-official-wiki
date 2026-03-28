<?php

namespace PixelQuestRoblox\Service;

use MediaWiki\MediaWikiServices;

/**
 * Roblox Friends API helper (v1).
 *
 * Endpoint:
 * GET https://friends.roblox.com/v1/users/{userId}/friends
 *
 * Response has:
 * {
 *   "data": [ { "id": 123, ... }, ... ],
 *   "nextPageCursor": "..." // optional
 * }
 */
final class PqRobloxFriendService {
	// How long we keep the friend list in cache (per viewer user).
	private const FRIENDS_CACHE_TTL = 3600; // 1 hour

	/**
	 * Returns whether $viewerRobloxId and $targetRobloxId are friends.
	 */
	public static function areRobloxUsersFriends( int $viewerRobloxId, int $targetRobloxId ): bool {
		if ( $viewerRobloxId <= 0 || $targetRobloxId <= 0 ) {
			return false;
		}
		if ( $viewerRobloxId === $targetRobloxId ) {
			return false;
		}

		$wan = MediaWikiServices::getInstance()->getMainWANObjectCache();
		$key = $wan->makeGlobalKey( 'pqroblox', 'friends', 'v1', (string)$viewerRobloxId );

		// Cache the whole friend-ID set for the viewer, then just membership test per target.
		$ttl = self::FRIENDS_CACHE_TTL;
		$friendsSet = $wan->getWithSetCallback(
			$key,
			$ttl,
			static function () use ( $viewerRobloxId ) : array {
				$friendsSet = [];
				$cursor = null;

				$httpFactory = MediaWikiServices::getInstance()->getHttpRequestFactory();
				do {
					PqRobloxThrottle::waitTurn();
					$url = "https://friends.roblox.com/v1/users/{$viewerRobloxId}/friends";
					if ( is_string( $cursor ) && $cursor !== '' ) {
						$url .= '?cursor=' . rawurlencode( $cursor );
					}

					$req = $httpFactory->create(
						$url,
						[
							'timeout' => 12,
							'connectTimeout' => 4,
						],
						__METHOD__
					);
					$req->setHeader( 'Accept', 'application/json' );
					$status = $req->execute();
					if ( !$status->isOK() || (int)$req->getStatus() !== 200 ) {
						wfDebugLog( 'pqroblox', '[FriendService] friends HTTP error viewer=' . $viewerRobloxId
							. ' status=' . $req->getStatus() );
						break;
					}

					$body = $req->getContent();
					$json = json_decode( $body, true );
					if ( !is_array( $json ) ) {
						wfDebugLog( 'pqroblox', '[FriendService] friends JSON decode failed viewer=' . $viewerRobloxId );
						break;
					}

					$data = $json['data'] ?? [];
					if ( is_array( $data ) ) {
						foreach ( $data as $f ) {
							if ( is_array( $f ) && isset( $f['id'] ) && is_numeric( $f['id'] ) ) {
								$friendsSet[(string)(int)$f['id']] = true;
							}
						}
					}

					$cursor = $json['nextPageCursor'] ?? null;
				} while ( is_string( $cursor ) && $cursor !== '' );

				return $friendsSet;
			}
		);

		return isset( $friendsSet[(string)(int)$targetRobloxId] );
	}
}

