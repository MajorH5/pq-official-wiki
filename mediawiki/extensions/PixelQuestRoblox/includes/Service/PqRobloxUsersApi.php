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
}
