<?php

namespace PixelQuestRoblox;

use MediaWiki\MediaWikiServices;
use MediaWiki\SpecialPage\SpecialPage;
use MediaWiki\User\User;
use PixelQuestRoblox\Service\PqRobloxDataStoreClient;
use PixelQuestRoblox\Service\PqRobloxFriendService;
use PixelQuestRoblox\Service\PqRobloxLinkStore;
use PixelQuestRoblox\Service\PqRobloxLookupIndex;
use PixelQuestRoblox\Service\PqRobloxUsersApi;

final class SpecialRobloxProfile extends SpecialPage {

	public function __construct() {
		parent::__construct( 'RobloxProfile' );
	}

	public function execute( $subPage ): void {
		$this->setHeaders();
		$out = $this->getOutput();
		$out->setPageTitle( $this->msg( 'robloxprofile' )->text() );
		// Allow same-origin embedding for User: page profile preview iframe.
		$out->setPreventClickjacking( false );
		$viewer = $this->getUser();
		$req = $this->getRequest();
		$isEmbed = $req->getBool( 'embed' ) || strtolower( (string)$req->getVal( 'action', '' ) ) === 'render';
		if ( $isEmbed ) {
			// Render only the special-page content (no skin chrome/sidebar/toolboxes).
			$out->setArticleBodyOnly( true );
		}
		$charPage = max( 1, (int)$req->getInt( 'charpage', 1 ) );
		$gravePage = max( 1, (int)$req->getInt( 'gravepage', 1 ) );
		$graveSort = (string)$req->getText( 'graveSort', 'time' );
		if ( !in_array( $graveSort, [ 'time', 'level', 'valor' ], true ) ) {
			$graveSort = 'time';
		}
		$graveDir = strtolower( (string)$req->getText( 'graveDir', 'desc' ) );
		if ( $graveDir !== 'asc' && $graveDir !== 'desc' ) {
			$graveDir = 'desc';
		}
		$graveMinValorRaw = $req->getText( 'graveMinValor', '' );
		$graveMinValor = null;
		if ( is_string( $graveMinValorRaw ) && $graveMinValorRaw !== '' && is_numeric( $graveMinValorRaw ) ) {
			$graveMinValor = max( 0, (int)floor( (float)$graveMinValorRaw ) );
		}

		$vaultPage = max( 1, (int)$req->getInt( 'vaultpage', 1 ) );
		$vaultHideEmpty = $req->getText( 'vaultHideEmpty', '' ) !== '';
		$vaultTier = (string)$req->getText( 'vaultTier', '' );
		if ( $vaultTier !== '' && !in_array( $vaultTier, [ '1', '2', '3', '4', '5', '6', 'legendary' ], true ) ) {
			$vaultTier = '';
		}
		$vaultType = trim( (string)$req->getText( 'vaultType', '' ) );
		$vaultQ = trim( (string)$req->getText( 'vaultQ', '' ) );

		$activeTab = trim( (string)$req->getText( 'tab', '' ) );
		$allowedTabs = [
			'pq-roblox-panel-characters',
			'pq-roblox-panel-graveyard',
			'pq-roblox-panel-skins',
			'pq-roblox-panel-vault',
			'pq-roblox-panel-account-stats',
			'pq-roblox-panel-settings',
		];
		if ( $activeTab === '' || !in_array( $activeTab, $allowedTabs, true ) ) {
			$activeTab = null;
		}

		$sub = is_string( $subPage ) ? trim( $subPage ) : '';
		if ( $sub === '' ) {
			if ( !$viewer->isRegistered() ) {
				$this->requireLogin();
				return;
			}
			$target = $viewer;
		} else {
			$name = str_replace( '_', ' ', $sub );
			$u = User::newFromName( $name, false );
			if ( !$u || !$u->isRegistered() ) {
				$out->addWikiMsg( 'pqroblox-profile-user-not-found' );
				return;
			}
			$target = $u;
		}

		$store = new PqRobloxLinkStore();
		$link = $store->getLinkForWikiUser( $target->getId() );
		if ( $link === null ) {
			$out->addWikiMsg( 'pqroblox-profile-not-linked', $target->getName() );
			return;
		}
		$robloxId = (int)$link['robloxUserId'];

		$viewerRobloxId = null;
		if ( $viewer->isRegistered() ) {
			$vlink = $store->getLinkForWikiUser( $viewer->getId() );
			if ( $vlink !== null ) {
				$viewerRobloxId = (int)$vlink['robloxUserId'];
			}
		}

		$robloxPublic = PqRobloxUsersApi::getPublicUser( $robloxId );
		if ( $robloxPublic !== null && $robloxPublic['name'] !== '' ) {
			$out->setPageTitle(
				$this->msg( 'pqroblox-special-profile-pagetitle', $robloxPublic['name'] )->text()
			);
		} else {
			$out->setPageTitle( $this->msg( 'special-robloxprofile' )->text() );
		}

		$isOwner = $viewer->isRegistered() && $viewer->getId() === $target->getId();
		$forceRefresh = $req->getBool( 'pqroblox_refresh' )
			&& ( $isOwner || $viewer->isAllowed( 'userrights' ) );

		$playerData = PqRobloxDataStoreClient::getPlayerDataForRobloxUser( $robloxId, $forceRefresh );
		$show = self::resolveVisibility( $viewer, $target, $isOwner, $viewerRobloxId, $robloxId );
		$lookup = PqRobloxLookupIndex::instance();

		RobloxProfileRenderer::render(
			$out,
			$this->getContext(),
			$viewer,
			$target,
			$robloxId,
			$playerData,
			$lookup,
			$show,
			$charPage,
			$gravePage,
			$graveSort,
			$graveDir,
			$graveMinValor,
			$vaultPage,
			$vaultHideEmpty,
			$vaultTier,
			$vaultType,
			$vaultQ,
			$activeTab,
			$robloxPublic
		);

		// Owner hint is rendered in RobloxProfileRenderer (top + bottom blocks).
	}

	/**
	 * @return array<string, bool>
	 */
	private static function resolveVisibility(
		User $viewer,
		User $target,
		bool $isOwner,
		?int $viewerRobloxId,
		int $targetRobloxId
	): array {
		if ( $isOwner ) {
			return [
				'valor' => true,
				'last_seen' => true,
				'characters' => true,
				'characters_detail' => true,
				'characters_inventory' => true,
				'graveyard' => true,
				'skins' => true,
				'vault' => true,
				'account_stats' => true,
			];
		}
		$userOptionsLookup = MediaWikiServices::getInstance()->getUserOptionsLookup();

		$getState = static function ( string $key ) use ( $target, $userOptionsLookup ): string {
			// Legacy support: old boolean toggles were stored as '1'/'0'.
			return (string)$userOptionsLookup->getOption( $target, $key, '0' );
		};

		$stateValor = $getState( 'pqroblox-pub-valor' );
		$stateLastSeen = $getState( 'pqroblox-pub-last-seen' );
		$stateChars = $getState( 'pqroblox-pub-characters' );
		$stateCharsDetail = $getState( 'pqroblox-pub-characters-detail' );
		$stateCharsInv = $getState( 'pqroblox-pub-characters-inventory' );
		$stateGrave = $getState( 'pqroblox-pub-graveyard' );
		$stateSkins = $getState( 'pqroblox-pub-skins' );
		$stateVault = $getState( 'pqroblox-pub-vault' );
		$stateAccountStats = $getState( 'pqroblox-pub-account-stats' );

		$needFriend =
			$stateValor === 'friends'
			|| $stateLastSeen === 'friends'
			|| $stateChars === 'friends'
			|| $stateCharsDetail === 'friends'
			|| $stateCharsInv === 'friends'
			|| $stateGrave === 'friends'
			|| $stateSkins === 'friends'
			|| $stateVault === 'friends'
			|| $stateAccountStats === 'friends';

		$friendOk = false;
		if ( $needFriend && $viewerRobloxId !== null && $viewerRobloxId > 0 ) {
			$friendOk = PqRobloxFriendService::areRobloxUsersFriends( $viewerRobloxId, $targetRobloxId );
		}

		// Placeholder: guild-mates logic will be added later.
		$guildOk = false;

		$stateToVisible = static function ( string $state ) use ( $friendOk, $guildOk ): bool {
			if ( $state === '1' || $state === 'everyone' ) {
				return true;
			}
			if ( $state === '0' || $state === '' || $state === 'none' ) {
				return false;
			}
			if ( $state === 'friends' ) {
				return $friendOk;
			}
			if ( $state === 'guildmates' ) {
				return $guildOk;
			}
			// Unknown values are treated as "no".
			return false;
		};

		$chars = $stateToVisible( $stateChars );
		return [
			'valor' => $stateToVisible( $stateValor ),
			'last_seen' => $stateToVisible( $stateLastSeen ),
			'characters' => $chars,
			'characters_detail' => $chars && $stateToVisible( $stateCharsDetail ),
			'characters_inventory' => $chars && $stateToVisible( $stateCharsInv ),
			'graveyard' => $stateToVisible( $stateGrave ),
			'skins' => $stateToVisible( $stateSkins ),
			'vault' => $stateToVisible( $stateVault ),
			'account_stats' => $stateToVisible( $stateAccountStats ),
		];
	}
}
