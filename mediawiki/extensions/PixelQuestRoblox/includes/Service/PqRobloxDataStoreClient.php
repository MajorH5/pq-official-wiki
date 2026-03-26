<?php

namespace PixelQuestRoblox\Service;

use MediaWiki\MediaWikiServices;
use PixelQuestRoblox\PqRobloxConfig;

/**
 * Roblox Open Cloud — Standard Data Stores v2 (Get Data Store Entry).
 *
 * URL shape (matches working Open Cloud usage):
 *   GET /cloud/v2/universes/{universeId}/data-stores/{dataStoreName}/entries/{entryKey}
 * Entry key is typically the Roblox user id string.
 *
 * Open Cloud returns an envelope; `value` often contains Profile/Data Store service fields
 * (`Data`, `MetaData`, `UserIds`, …). The in-game save (valor, characters, …) lives in `value.Data`.
 *
 * @see https://create.roblox.com/docs/reference/cloud/datastores-api
 */
final class PqRobloxDataStoreClient {

	private static function log( string $line ): void {
		wfDebugLog( 'pqroblox', '[DataStore] ' . $line );
	}

	/**
	 * If this blob is a profile-service envelope, return the inner save; otherwise return as-is.
	 *
	 * @param array<string, mixed> $blob
	 * @return array<string, mixed>
	 */
	private static function unwrapProfileServiceEnvelope( array $blob ): array {
		if ( isset( $blob['Data'] ) && is_array( $blob['Data'] ) ) {
			// Preserve a few useful envelope-level fields that UI needs
			// (join date + online indicator).
			//
			// Some callers expect these to exist on the returned player root, but
			// previously we returned only `Data`, dropping envelope siblings like
			// `ProfileCreateTime` and `MetaData`.
			self::log(
				'unwrapProfileServiceEnvelope: using Data field (inner keys: '
				. implode( ',', array_keys( $blob['Data'] ) ) . ')'
			);
			$data = $blob['Data'];
			if ( array_key_exists( 'ProfileCreateTime', $blob ) ) {
				$data['ProfileCreateTime'] = $blob['ProfileCreateTime'];
			}
			if ( array_key_exists( 'MetaData', $blob ) ) {
				$data['MetaData'] = $blob['MetaData'];
			}
			if ( array_key_exists( 'metadata', $blob ) ) {
				$data['metadata'] = $blob['metadata'];
			}
			return $data;
		}
		self::log( 'unwrapProfileServiceEnvelope: no Data key, using blob as player root (keys: ' . implode( ',', array_keys( $blob ) ) . ')' );
		return $blob;
	}

	/**
	 * @return array<string, mixed>|null Decoded player table (best-effort), or null if missing / error.
	 */
	public static function getPlayerDataForRobloxUser( int $robloxUserId, bool $forceRefresh = false ): ?array {
		if ( $robloxUserId <= 0 ) {
			self::log( "getPlayerDataForRobloxUser: skip (invalid id $robloxUserId)" );
			return null;
		}
		$universe = PqRobloxConfig::getRobloxUniverseId();
		$apiKey = PqRobloxConfig::getRobloxOpenCloudApiKey();
		$store = PqRobloxConfig::getDataStoreName();
		if ( $universe === '' || $apiKey === '' || $store === '' ) {
			self::log( 'getPlayerDataForRobloxUser: missing config (universe, API key, or ROBLOX_DATA_STORE_NAME empty)' );
			return null;
		}

		$cache = MediaWikiServices::getInstance()->getMainWANObjectCache();
		$key = $cache->makeGlobalKey( 'pqroblox', 'playerdata', 'v2', (string)$robloxUserId );
		$ttl = PqRobloxConfig::getPlayerDataCacheTTL();

		if ( $forceRefresh ) {
			self::log( "getPlayerDataForRobloxUser: force refresh, deleting WAN key for robloxUserId=$robloxUserId" );
			$cache->delete( $key );
		}

		return $cache->getWithSetCallback(
			$key,
			$ttl,
			static function () use ( $universe, $apiKey, $store, $robloxUserId ) {
				PqRobloxThrottle::waitTurn();
				return self::fetchEntryRaw( $universe, $apiKey, $store, (string)$robloxUserId );
			}
		);
	}

	/**
	 * @return array<string, mixed>|null
	 */
	private static function fetchEntryRaw( string $universe, string $apiKey, string $dataStoreName, string $entryKey ): ?array {
		if ( !function_exists( 'curl_init' ) ) {
			self::log( 'fetchEntryRaw: curl extension not loaded' );
			return null;
		}

		// Same path as working Node integration (no /scopes/global/ segment).
		$url = sprintf(
			'https://apis.roblox.com/cloud/v2/universes/%s/data-stores/%s/entries/%s',
			rawurlencode( $universe ),
			rawurlencode( $dataStoreName ),
			rawurlencode( $entryKey )
		);
		self::log( 'fetchEntryRaw: GET ' . $url . ' (x-api-key: <redacted>)' );

		$ch = curl_init( $url );
		curl_setopt_array( $ch, [
			CURLOPT_HTTPGET => true,
			CURLOPT_HTTPHEADER => [
				'Accept: application/json',
				'Content-Type: application/json',
				'x-api-key: ' . $apiKey,
			],
			CURLOPT_RETURNTRANSFER => true,
			CURLOPT_TIMEOUT => 25,
		] );
		$body = curl_exec( $ch );
		$curlErr = curl_error( $ch );
		$code = (int)curl_getinfo( $ch, CURLINFO_HTTP_CODE );
		curl_close( $ch );

		if ( $curlErr !== '' ) {
			self::log( "fetchEntryRaw: curl error: $curlErr (HTTP code reported: $code)" );
		}
		self::log( "fetchEntryRaw: HTTP $code, body length=" . ( is_string( $body ) ? strlen( $body ) : 0 ) );

		if ( $code === 404 ) {
			self::log( 'fetchEntryRaw: 404 — no entry for this key (player may have no save yet)' );
			return null;
		}
		if ( $code !== 200 || !is_string( $body ) ) {
			self::log( 'fetchEntryRaw: non-200 or empty body, snippet=' . substr( (string)$body, 0, 500 ) );
			return null;
		}

		$data = json_decode( $body, true );
		if ( !is_array( $data ) ) {
			self::log( 'fetchEntryRaw: JSON top-level decode failed, snippet=' . substr( $body, 0, 500 ) );
			return null;
		}

		$hasValue = array_key_exists( 'value', $data ) || array_key_exists( 'Value', $data );
		$value = $data['value'] ?? $data['Value'] ?? null;
		$vtype = $value === null ? 'null' : gettype( $value );
		self::log( 'fetchEntryRaw: parsed JSON keys=' . implode( ',', array_keys( $data ) )
			. " hasValue=" . ( $hasValue ? '1' : '0' ) . " valueType=$vtype" );

		// Primary: value is JSON string or object (Node behavior).
		if ( $value !== null ) {
			if ( is_string( $value ) ) {
				$decoded = json_decode( $value, true );
				if ( !is_array( $decoded ) ) {
					self::log( 'fetchEntryRaw: value is string but inner JSON decode failed, snippet=' . substr( $value, 0, 400 ) );
					return null;
				}
				self::log( 'fetchEntryRaw: decoded value string, outer keys=' . implode( ',', array_keys( $decoded ) ) );
				return self::unwrapProfileServiceEnvelope( $decoded );
			}
			if ( is_array( $value ) ) {
				self::log( 'fetchEntryRaw: value is array, outer keys=' . implode( ',', array_keys( $value ) ) );
				return self::unwrapProfileServiceEnvelope( $value );
			}
			self::log( 'fetchEntryRaw: value is neither string nor array' );
			return null;
		}

		// Fallbacks (same idea as Node).
		if ( array_key_exists( 'Data', $data ) ) {
			$d = $data['Data'];
			self::log( 'fetchEntryRaw: no value field, using Data key (type=' . gettype( $d ) . ')' );
			return is_array( $d ) ? $d : null;
		}
		if ( isset( $data['UserIds'] ) || isset( $data['MetaData'] ) ) {
			self::log( 'fetchEntryRaw: no value field, returning whole response as player blob (UserIds/MetaData present)' );
			return $data;
		}

		self::log( 'fetchEntryRaw: no usable value/Data in response' );
		return null;
	}
}
