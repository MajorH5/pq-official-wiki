<?php

namespace PixelQuestRoblox;

final class PqRobloxConfig {

	public static function getApiSecret(): string {
		global $wgPqRobloxApiSecret;
		if ( isset( $wgPqRobloxApiSecret ) && is_string( $wgPqRobloxApiSecret ) && $wgPqRobloxApiSecret !== '' ) {
			return $wgPqRobloxApiSecret;
		}
		$v = getenv( 'PQ_API_SECRET' );
		if ( is_string( $v ) && $v !== '' ) {
			return $v;
		}
		$v = getenv( 'DATADUMP_INGEST_SECRET' );
		return is_string( $v ) ? $v : '';
	}

	public static function getCodeTTL(): int {
		global $wgPqRobloxCodeTTL;
		if ( isset( $wgPqRobloxCodeTTL ) && is_int( $wgPqRobloxCodeTTL ) && $wgPqRobloxCodeTTL > 0 ) {
			return $wgPqRobloxCodeTTL;
		}
		return 900;
	}

	public static function getRobloxUniverseId(): string {
		global $wgPqRobloxUniverseId;
		if ( isset( $wgPqRobloxUniverseId ) && is_string( $wgPqRobloxUniverseId ) && $wgPqRobloxUniverseId !== '' ) {
			return $wgPqRobloxUniverseId;
		}
		$v = getenv( 'ROBLOX_UNIVERSE_ID' );
		return is_string( $v ) ? trim( $v ) : '';
	}

	public static function getRobloxOpenCloudApiKey(): string {
		global $wgPqRobloxOpenCloudApiKey;
		if ( isset( $wgPqRobloxOpenCloudApiKey ) && is_string( $wgPqRobloxOpenCloudApiKey ) && $wgPqRobloxOpenCloudApiKey !== '' ) {
			return $wgPqRobloxOpenCloudApiKey;
		}
		$v = getenv( 'ROBLOX_OPEN_CLOUD_API_KEY' );
		return is_string( $v ) ? trim( $v ) : '';
	}

	public static function getMessagingTopic(): string {
		global $wgPqRobloxMessagingTopic;
		if ( isset( $wgPqRobloxMessagingTopic ) && is_string( $wgPqRobloxMessagingTopic ) && $wgPqRobloxMessagingTopic !== '' ) {
			return $wgPqRobloxMessagingTopic;
		}
		$v = getenv( 'ROBLOX_MESSAGING_TOPIC' );
		if ( is_string( $v ) && trim( $v ) !== '' ) {
			return trim( $v );
		}
		return 'wiki-link';
	}

	public static function getDataStoreName(): string {
		global $wgPqRobloxDataStoreName;
		if ( isset( $wgPqRobloxDataStoreName ) && is_string( $wgPqRobloxDataStoreName ) && $wgPqRobloxDataStoreName !== '' ) {
			return $wgPqRobloxDataStoreName;
		}
		$v = getenv( 'ROBLOX_DATA_STORE_NAME' );
		return is_string( $v ) ? trim( $v ) : '';
	}

	/** Absolute path to pq-datadump.json (items, skins, entities for lookups). */
	public static function getDataDumpPath(): string {
		global $wgPqRobloxDataDumpPath;
		if ( isset( $wgPqRobloxDataDumpPath ) && is_string( $wgPqRobloxDataDumpPath ) && $wgPqRobloxDataDumpPath !== '' ) {
			return $wgPqRobloxDataDumpPath;
		}
		$v = getenv( 'PQ_DATADUMP_PATH' );
		if ( is_string( $v ) && trim( $v ) !== '' ) {
			return trim( $v );
		}
		return '/var/www/html/pq-datadump.json';
	}

	public static function getPlayerDataCacheTTL(): int {
		global $wgPqRobloxPlayerDataCacheTTL;
		if ( isset( $wgPqRobloxPlayerDataCacheTTL ) && is_int( $wgPqRobloxPlayerDataCacheTTL ) && $wgPqRobloxPlayerDataCacheTTL > 0 ) {
			return $wgPqRobloxPlayerDataCacheTTL;
		}
		return 600;
	}

	public static function getDatastoreMinIntervalSeconds(): float {
		global $wgPqRobloxDatastoreMinInterval;
		if ( isset( $wgPqRobloxDatastoreMinInterval ) && is_numeric( $wgPqRobloxDatastoreMinInterval ) && (float)$wgPqRobloxDatastoreMinInterval > 0 ) {
			return (float)$wgPqRobloxDatastoreMinInterval;
		}
		return 0.25;
	}

	public static function getGraveyardPerPage(): int {
		global $wgPqRobloxGraveyardPerPage;
		if ( isset( $wgPqRobloxGraveyardPerPage ) && is_int( $wgPqRobloxGraveyardPerPage ) && $wgPqRobloxGraveyardPerPage > 0 ) {
			return $wgPqRobloxGraveyardPerPage;
		}
		return 20;
	}
}
