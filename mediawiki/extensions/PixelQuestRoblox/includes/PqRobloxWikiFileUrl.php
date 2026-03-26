<?php

namespace PixelQuestRoblox;

use MediaWiki\MediaWikiServices;
use MediaWiki\Title\Title;

/**
 * Resolve PQ_tex_* uploads to a URL served by this wiki (no Roblox CDN).
 */
final class PqRobloxWikiFileUrl {

	public static function forFilename( string $fname ): ?string {
		if ( $fname === '' ) {
			return null;
		}
		// Be tolerant of first-letter capitalization differences.
		// Some wikis canonicalize File: titles to an initial capital (Skin_...), while the bot
		// generates lowercase bases (skin_...). Repo lookups can be sensitive here depending
		// on configuration and backend.
		foreach ( [ $fname, ucfirst( $fname ) ] as $try ) {
			$title = Title::makeTitle( \NS_FILE, $try );
			$file = MediaWikiServices::getInstance()->getRepoGroup()->findFile( $title );
			if ( $file && $file->exists() ) {
				return $file->getUrl();
			}
		}
		return null;
	}
}
