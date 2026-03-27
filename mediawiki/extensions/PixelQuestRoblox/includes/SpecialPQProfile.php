<?php

namespace PixelQuestRoblox;

use MediaWiki\Html\Html;
use MediaWiki\MediaWikiServices;
use MediaWiki\SpecialPage\SpecialPage;
use MediaWiki\Title\Title;
use MediaWiki\User\User;
use PixelQuestRoblox\Service\PqRobloxDataStoreClient;
use PixelQuestRoblox\Service\PqRobloxFriendService;
use PixelQuestRoblox\Service\PqRobloxLinkStore;
use PixelQuestRoblox\Service\PqRobloxLookupIndex;
use PixelQuestRoblox\Service\PqRobloxPlayerIndexStore;
use PixelQuestRoblox\Service\PqRobloxUsersApi;

final class SpecialPQProfile extends SpecialPage {

	public function __construct() {
		parent::__construct( 'PQProfile' );
	}

	public function execute( $subPage ): void {
		$this->setHeaders();
		$out = $this->getOutput();
		$out->setPageTitle( $this->msg( 'pqprofile' )->text() );
		$out->setPreventClickjacking( false );
		$viewer = $this->getUser();
		$req = $this->getRequest();
		$isEmbed = $req->getBool( 'embed' ) || strtolower( (string)$req->getVal( 'action', '' ) ) === 'render';
		if ( $isEmbed ) {
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
			'pq-roblox-panel-badges',
			'pq-roblox-panel-vault',
			'pq-roblox-panel-account-stats',
			'pq-roblox-panel-settings',
		];
		if ( $activeTab === '' || !in_array( $activeTab, $allowedTabs, true ) ) {
			$activeTab = null;
		}

		$store = new PqRobloxLinkStore();
		$indexStore = new PqRobloxPlayerIndexStore();

		$sub = is_string( $subPage ) ? trim( $subPage ) : '';
		if ( $sub === '' ) {
			if ( !$viewer->isRegistered() ) {
				$this->requireLogin();
				return;
			}
			$target = $viewer;
			$link = $store->getLinkForWikiUser( $target->getId() );
			if ( $link === null ) {
				$out->addWikiMsg( 'pqroblox-profile-not-linked', $target->getName() );
				return;
			}
			$robloxId = (int)$link['robloxUserId'];
		} else {
			$subLower = strtolower( $sub );
			if ( str_starts_with( $subLower, 'wiki/' ) ) {
				$wikiName = trim( str_replace( '_', ' ', substr( $sub, strlen( 'wiki/' ) ) ) );
				$u = User::newFromName( $wikiName, false );
				if ( !$u || !$u->isRegistered() ) {
					$out->addWikiMsg( 'pqroblox-profile-user-not-found' );
					return;
				}
				$link = $store->getLinkForWikiUser( $u->getId() );
				if ( $link === null ) {
					$out->addWikiMsg( 'pqroblox-profile-not-linked', $u->getName() );
					return;
				}
				$rid = (int)$link['robloxUserId'];
				$out->redirect( Title::makeTitle( NS_SPECIAL, 'PQProfile/' . $rid )->getFullURL() );
				return;
			}

			$name = str_replace( '_', ' ', $sub );
			if ( preg_match( '/^\d+$/', $name ) ) {
				$robloxId = (int)$name;
				if ( $robloxId <= 0 ) {
					$out->addWikiMsg( 'pqroblox-profile-not-found-roblox' );
					return;
				}
			} else {
				$row = $indexStore->findByUsername( $name );
				if ( $row !== null ) {
					$robloxId = (int)$row['robloxUserId'];
				} else {
					$out->addWikiMsg( 'pqroblox-profile-not-found-roblox' );
					return;
				}
			}
		}

		$linkedWikiId = $store->getWikiUserIdForRoblox( $robloxId );
		if ( $linkedWikiId !== null ) {
			$target = User::newFromId( $linkedWikiId );
		} else {
			$target = User::newFromId( 0 );
		}

		$viewerRobloxId = null;
		if ( $viewer->isRegistered() ) {
			$vlink = $store->getLinkForWikiUser( $viewer->getId() );
			if ( $vlink !== null ) {
				$viewerRobloxId = (int)$vlink['robloxUserId'];
			}
		}

		$isProfileOwner = self::computeProfileOwner( $viewer, $target, $viewerRobloxId, $robloxId );
		$forceRefresh = $req->getBool( 'pqroblox_refresh' )
			&& ( $isProfileOwner || $viewer->isAllowed( 'userrights' ) );

		$playerData = PqRobloxDataStoreClient::getPlayerDataForRobloxUser( $robloxId, $forceRefresh );
		if ( $playerData === null ) {
			$out->setPageTitle( $this->msg( 'special-pqprofile' )->text() );
			$out->addHTML( Html::rawElement( 'div', [ 'class' => 'warningbox' ],
				$this->msg( 'pqroblox-profile-not-found-save' )->escaped() ) );
			return;
		}

		$robloxPublic = PqRobloxUsersApi::getPublicUser( $robloxId );
		if ( $robloxPublic !== null && $robloxPublic['name'] !== '' ) {
			$out->setPageTitle( $this->msg( 'pqroblox-special-profile-pagetitle', $robloxPublic['name'] )->text() );
		} elseif ( $linkedWikiId !== null && $target->isRegistered() ) {
			$out->setPageTitle( $this->msg( 'pqroblox-special-profile-pagetitle', $target->getName() )->text() );
		} else {
			$out->setPageTitle( $this->msg( 'special-pqprofile' )->text() );
		}

		$indexName = null;
		if ( $robloxPublic !== null && isset( $robloxPublic['name'] ) && $robloxPublic['name'] !== '' ) {
			$indexName = $robloxPublic['name'];
		} elseif ( $linkedWikiId !== null && $target->isRegistered() ) {
			$indexName = $target->getName();
		}
		$indexStore->upsert( $robloxId, $indexName );
		$show = self::resolveVisibility( $viewer, $target, $isProfileOwner, $viewerRobloxId, $robloxId );
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
			$robloxPublic,
			$isProfileOwner
		);
	}

	private static function computeProfileOwner(
		User $viewer,
		User $target,
		?int $viewerRobloxId,
		int $targetRobloxId
	): bool {
		if ( $viewer->isRegistered() && $target->isRegistered() && $viewer->getId() === $target->getId() ) {
			return true;
		}
		return $viewerRobloxId !== null && $viewerRobloxId > 0 && $viewerRobloxId === $targetRobloxId;
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
		if ( !$target->isRegistered() ) {
			if ( $isOwner ) {
				return [
					'valor' => true,
					'last_seen' => true,
					'characters' => true,
					'characters_detail' => true,
					'characters_inventory' => true,
					'graveyard' => true,
					'skins' => true,
					'badges' => true,
					'honor' => true,
					'vault' => true,
					'account_stats' => true,
				];
			}
			return [
				'valor' => false,
				'last_seen' => true,
				'characters' => true,
				'characters_detail' => false,
				'characters_inventory' => false,
				'graveyard' => true,
				'skins' => false,
				'badges' => false,
				'honor' => true,
				'vault' => false,
				'account_stats' => false,
			];
		}
		if ( $isOwner ) {
			return [
				'valor' => true,
				'last_seen' => true,
				'characters' => true,
				'characters_detail' => true,
				'characters_inventory' => true,
				'graveyard' => true,
				'skins' => true,
				'badges' => true,
				'honor' => true,
				'vault' => true,
				'account_stats' => true,
			];
		}
		$userOptionsLookup = MediaWikiServices::getInstance()->getUserOptionsLookup();

		$getState = static function ( string $key ) use ( $target, $userOptionsLookup ): string {
			return (string)$userOptionsLookup->getOption( $target, $key, '0' );
		};

		$stateValor = $getState( 'pqroblox-pub-valor' );
		$stateLastSeen = $getState( 'pqroblox-pub-last-seen' );
		$stateChars = $getState( 'pqroblox-pub-characters' );
		$stateCharsDetail = $getState( 'pqroblox-pub-characters-detail' );
		$stateCharsInv = $getState( 'pqroblox-pub-characters-inventory' );
		$stateGrave = $getState( 'pqroblox-pub-graveyard' );
		$stateSkins = $getState( 'pqroblox-pub-skins' );
		$stateBadges = $getState( 'pqroblox-pub-badges' );
		$stateHonor = $getState( 'pqroblox-pub-honor' );
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
			|| $stateBadges === 'friends'
			|| $stateHonor === 'friends'
			|| $stateVault === 'friends'
			|| $stateAccountStats === 'friends';

		$friendOk = false;
		if ( $needFriend && $viewerRobloxId !== null && $viewerRobloxId > 0 ) {
			$friendOk = PqRobloxFriendService::areRobloxUsersFriends( $viewerRobloxId, $targetRobloxId );
		}

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
			return false;
		};

		$chars = $stateToVisible( $stateChars );
		$badgesVisible = $stateToVisible( $stateBadges );
		if ( !$viewer->isRegistered() && !$isOwner ) {
			$badgesVisible = false;
		}
		return [
			'valor' => $stateToVisible( $stateValor ),
			'last_seen' => $stateToVisible( $stateLastSeen ),
			'characters' => $chars,
			'characters_detail' => $chars && $stateToVisible( $stateCharsDetail ),
			'characters_inventory' => $chars && $stateToVisible( $stateCharsInv ),
			'graveyard' => $stateToVisible( $stateGrave ),
			'skins' => $stateToVisible( $stateSkins ),
			'badges' => $badgesVisible,
			'honor' => $stateToVisible( $stateHonor ),
			'vault' => $stateToVisible( $stateVault ),
			'account_stats' => $stateToVisible( $stateAccountStats ),
		];
	}
}
