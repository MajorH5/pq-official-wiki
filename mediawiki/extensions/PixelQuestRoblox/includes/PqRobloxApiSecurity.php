<?php

namespace PixelQuestRoblox;

use MediaWiki\Request\WebRequest;

final class PqRobloxApiSecurity {

	public static function getProvidedSecret( WebRequest $request ): string {
		$h = $request->getHeader( 'X-PQ-API-Secret' );
		if ( is_string( $h ) && $h !== '' ) {
			return trim( $h );
		}
		$auth = $request->getHeader( 'Authorization' );
		if ( is_string( $auth ) && preg_match( '/^Bearer\s+(.+)$/i', $auth, $m ) ) {
			return trim( $m[1] );
		}
		return '';
	}

	public static function secretMatches( WebRequest $request ): bool {
		$expected = PqRobloxConfig::getApiSecret();
		if ( $expected === '' ) {
			return false;
		}
		$provided = self::getProvidedSecret( $request );
		if ( $provided === '' ) {
			return false;
		}
		return hash_equals( $expected, $provided );
	}
}
