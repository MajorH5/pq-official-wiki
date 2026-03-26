<?php

namespace PixelQuestRoblox\Service;

use PixelQuestRoblox\PqRobloxConfig;

/**
 * Global cross-request throttle for Open Cloud Data Store reads (single-writer lock file).
 */
final class PqRobloxThrottle {

	public static function waitTurn(): void {
		$path = self::lockPath();
		$fp = fopen( $path, 'c+' );
		if ( !$fp ) {
			return;
		}
		$min = PqRobloxConfig::getDatastoreMinIntervalSeconds();
		flock( $fp, LOCK_EX );
		$raw = stream_get_contents( $fp );
		$last = is_string( $raw ) ? (float)trim( $raw ) : 0.0;
		$now = microtime( true );
		if ( $last > 0 && ( $now - $last ) < $min ) {
			$wait = $min - ( $now - $last );
			usleep( (int)( $wait * 1_000_000 ) );
			$now = microtime( true );
		}
		rewind( $fp );
		ftruncate( $fp, 0 );
		fwrite( $fp, (string)$now );
		fflush( $fp );
		flock( $fp, LOCK_UN );
		fclose( $fp );
	}

	private static function lockPath(): string {
		$base = rtrim( sys_get_temp_dir(), DIRECTORY_SEPARATOR );
		return $base . DIRECTORY_SEPARATOR . 'pq_roblox_ds_throttle.lock';
	}
}
