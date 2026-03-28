<?php

namespace PixelQuestRoblox\Service;

use MediaWiki\MediaWikiServices;
use MediaWiki\Request\WebRequest;
use MediaWiki\User\User;
use PixelQuestRoblox\PqRobloxConfig;

/**
 * Limits how often an identity (IP or wiki user) can trigger Roblox/DataStore work via Special:PQProfile.
 */
final class PqRobloxProfileRateLimit {

	/**
	 * Call before each outbound Roblox/Open Cloud action (username resolve, datastore read, etc.).
	 * Multiple checks per page view are expected (e.g. username API + datastore).
	 */
	public static function allowOutbound( User $viewer, WebRequest $req ): bool {
		$max = $viewer->isRegistered()
			? PqRobloxConfig::getProfileOutboundBudgetPerMinuteUser()
			: PqRobloxConfig::getProfileOutboundBudgetPerMinuteAnon();
		if ( $max <= 0 ) {
			return true;
		}

		$ident = $viewer->isRegistered()
			? 'u:' . $viewer->getId()
			: 'ip:' . $req->getIP();
		$bucket = (int)floor( time() / 60 );
		$cache = MediaWikiServices::getInstance()->getLocalServerObjectCache();
		$key = $cache->makeGlobalKey( 'pqroblox', 'profileout', md5( $ident ), (string)$bucket );

		$cur = $cache->get( $key );
		$n = is_int( $cur ) ? $cur : 0;
		if ( $n >= $max ) {
			return false;
		}
		$cache->set( $key, $n + 1, 120 );
		return true;
	}
}
