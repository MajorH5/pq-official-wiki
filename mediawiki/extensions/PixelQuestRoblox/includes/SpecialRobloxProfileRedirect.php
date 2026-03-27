<?php

namespace PixelQuestRoblox;

use MediaWiki\SpecialPage\SpecialPage;
use MediaWiki\Title\Title;

/**
 * Legacy Special:RobloxProfile → Special:PQProfile (same subpage).
 * Implemented without SpecialRedirectToSpecial for compatibility across MediaWiki builds.
 */
final class SpecialRobloxProfileRedirect extends SpecialPage {

	public function __construct() {
		parent::__construct( 'RobloxProfile' );
	}

	public function execute( $subPage ): void {
		$sub = is_string( $subPage ) ? trim( $subPage ) : '';
		if ( $sub === '' ) {
			$target = Title::makeTitle( \NS_SPECIAL, 'PQProfile' );
		} else {
			$target = Title::makeTitle( \NS_SPECIAL, 'PQProfile/' . $sub );
		}
		$this->getOutput()->redirect( $target->getFullURL() );
	}
}
