<?php

namespace PixelQuestRoblox;

use MediaWiki\Html\Html;
use MediaWiki\MediaWikiServices;
use MediaWiki\SpecialPage\SpecialPage;
use MediaWiki\Title\Title;

final class SpecialRobloxProfiles extends SpecialPage {

	public function __construct() {
		parent::__construct( 'RobloxProfiles' );
	}

	public function execute( $subPage ): void {
		$this->setHeaders();
		$out = $this->getOutput();
		$out->addWikiMsg( 'pqroblox-profiles-intro' );

		$dbr = MediaWikiServices::getInstance()->getDBLoadBalancer()->getConnection( DB_REPLICA );
		$res = $dbr->newSelectQueryBuilder()
			->select( [ 'user_name', 'prl_roblox_user_id' ] )
			->from( 'pq_roblox_link' )
			->join( 'user', null, 'prl_user_id = user_id' )
			->orderBy( 'user_name' )
			->caller( __METHOD__ )
			->fetchResultSet();

		if ( !$res->numRows() ) {
			$out->addWikiMsg( 'pqroblox-profiles-empty' );
			return;
		}

		$rows = '';
		foreach ( $res as $row ) {
			$name = (string)$row->user_name;
			$rid = (int)$row->prl_roblox_user_id;
			$t = Title::newFromText( 'RobloxProfile/' . str_replace( ' ', '_', $name ), \NS_SPECIAL );
			$link = Html::element( 'a', [ 'href' => $t->getFullURL() ], $name );
			$rows .= Html::rawElement( 'tr', [],
				Html::element( 'td', [], $link )
				. Html::element( 'td', [], (string)$rid )
			);
		}
		$out->addHTML(
			Html::rawElement( 'table', [ 'class' => 'wikitable sortable' ],
				Html::rawElement( 'thead', [], Html::rawElement( 'tr', [],
					Html::element( 'th', [], $this->msg( 'pqroblox-profiles-col-user' )->text() )
					. Html::element( 'th', [], $this->msg( 'pqroblox-profiles-col-roblox' )->text() )
				) )
				. Html::rawElement( 'tbody', [], $rows )
			)
		);
	}
}
