<?php

namespace PixelQuestRoblox\Service;

use MediaWiki\MediaWikiServices;

/**
 * Public Roblox Users API (no auth): https://users.roblox.com/v1/users/{userId}
 */
final class PqRobloxUsersApi {

	private const CACHE_TTL_GOOD = 604800; // 7 days — usernames change rarely
	private const CACHE_TTL_MISS = 300; // 5 min — retry transient failures

	/**
	 * @return array{name: string, displayName: string}|null
	 */
	public static function getPublicUser( int $robloxUserId ): ?array {
		if ( $robloxUserId <= 0 ) {
			return null;
		}
		$wan = MediaWikiServices::getInstance()->getMainWANObjectCache();
		$key = $wan->makeGlobalKey( 'pqroblox', 'roblox-users-api-v1', (string)$robloxUserId );
		$wrapped = $wan->get( $key );
		if ( $wrapped !== false ) {
			if ( $wrapped === '@@miss@@' ) {
				return null;
			}
			$decoded = json_decode( $wrapped, true );
			return is_array( $decoded ) && isset( $decoded['name'] ) ? $decoded : null;
		}

		$data = self::fetchPublicUserUncached( $robloxUserId );
		if ( $data !== null ) {
			$wan->set( $key, json_encode( $data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES ), self::CACHE_TTL_GOOD );
			return $data;
		}
		$wan->set( $key, '@@miss@@', self::CACHE_TTL_MISS );
		return null;
	}

	/**
	 * @return array{name: string, displayName: string}|null
	 */
	private static function fetchPublicUserUncached( int $robloxUserId ): ?array {
		PqRobloxThrottle::waitTurn();
		$url = 'https://users.roblox.com/v1/users/' . $robloxUserId;
		$req = MediaWikiServices::getInstance()->getHttpRequestFactory()->create(
			$url,
			[
				'timeout' => 8,
				'connectTimeout' => 4,
			],
			__METHOD__
		);
		$req->setHeader( 'Accept', 'application/json' );
		$status = $req->execute();
		if ( !$status->isOK() ) {
			wfDebugLog( 'pqroblox', '[UsersApi] HTTP error userId=' . $robloxUserId );
			return null;
		}
		if ( (int)$req->getStatus() !== 200 ) {
			wfDebugLog( 'pqroblox', '[UsersApi] status ' . $req->getStatus() . ' userId=' . $robloxUserId );
			return null;
		}
		$body = $req->getContent();
		$json = json_decode( $body, true );
		if ( !is_array( $json ) || !isset( $json['name'] ) || !is_string( $json['name'] ) || $json['name'] === '' ) {
			return null;
		}
		$dn = $json['displayName'] ?? '';
		return [
			'name' => $json['name'],
			'displayName' => is_string( $dn ) ? $dn : '',
		];
	}

	/**
	 * Resolve current Roblox username to user id (POST /v1/usernames/users).
	 *
	 * @return int|null Positive id or null if not found.
	 */
	public static function getUserIdFromUsername( string $username ): ?int {
		$username = trim( $username );
		if ( $username === '' ) {
			return null;
		}
		$wan = MediaWikiServices::getInstance()->getMainWANObjectCache();
		$key = $wan->makeGlobalKey( 'pqroblox', 'roblox-username-to-id', md5( strtolower( str_replace( '_', ' ', $username ) ) ) );
		$wrapped = $wan->get( $key );
		if ( $wrapped !== false ) {
			if ( $wrapped === '@@miss@@' ) {
				return null;
			}
			$id = (int)$wrapped;
			return $id > 0 ? $id : null;
		}

		PqRobloxThrottle::waitTurn();
		$url = 'https://users.roblox.com/v1/usernames/users';
		$req = MediaWikiServices::getInstance()->getHttpRequestFactory()->create(
			$url,
			[
				'method' => 'POST',
				'postData' => json_encode( [ 'usernames' => [ $username ] ], JSON_UNESCAPED_UNICODE ),
				'timeout' => 8,
				'connectTimeout' => 4,
			],
			__METHOD__
		);
		$req->setHeader( 'Content-Type', 'application/json' );
		$req->setHeader( 'Accept', 'application/json' );
		$status = $req->execute();
		if ( !$status->isOK() || (int)$req->getStatus() !== 200 ) {
			wfDebugLog( 'pqroblox', '[UsersApi] username lookup failed: ' . $username );
			$wan->set( $key, '@@miss@@', self::CACHE_TTL_MISS );
			return null;
		}
		$json = json_decode( $req->getContent(), true );
		$data = $json['data'] ?? null;
		if ( !is_array( $data ) || $data === [] ) {
			$wan->set( $key, '@@miss@@', self::CACHE_TTL_MISS );
			return null;
		}
		$first = $data[0];
		if ( !is_array( $first ) || !isset( $first['id'] ) ) {
			$wan->set( $key, '@@miss@@', self::CACHE_TTL_MISS );
			return null;
		}
		$id = (int)$first['id'];
		if ( $id <= 0 ) {
			$wan->set( $key, '@@miss@@', self::CACHE_TTL_MISS );
			return null;
		}
		$wan->set( $key, (string)$id, self::CACHE_TTL_GOOD );
		return $id;
	}
}
