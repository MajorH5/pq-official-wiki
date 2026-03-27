<?php

namespace PixelQuestRoblox;

use MediaWiki\Context\RequestContext;
use MediaWiki\Installer\DatabaseUpdater;
use MediaWiki\MediaWikiServices;
use MediaWiki\Output\OutputPage;
use MediaWiki\Skin\Skin;
use MediaWiki\Title\Title;
use MediaWiki\User\User;
use PixelQuestRoblox\Service\PqRobloxDataStoreClient;
use PixelQuestRoblox\Service\PqRobloxFriendService;
use PixelQuestRoblox\Service\PqRobloxLinkStore;
use PixelQuestRoblox\Service\PqRobloxLookupIndex;
use PixelQuestRoblox\Service\PqRobloxPlayerIndexStore;
use PixelQuestRoblox\Service\PqRobloxUsersApi;

final class Hooks {

	public static function onLoadExtensionSchemaUpdates( DatabaseUpdater $updater ): void {
		$base = dirname( __DIR__ ) . '/sql/' . $updater->getDB()->getType();
		$updater->addExtensionTable(
			'pq_roblox_link_codes',
			"$base/pq_roblox_link_codes.sql"
		);
		$updater->addExtensionTable(
			'pq_roblox_link',
			"$base/pq_roblox_link.sql"
		);
		// If pq_roblox_player_index exists but is the wrong shape (manual / legacy),
		// addExtensionTable would skip CREATE — drop first so the table matches extension code.
		$updater->addExtensionUpdate( [
			[ self::class, 'fixPqRobloxPlayerIndexTable' ],
		] );
		$updater->addExtensionTable(
			'pq_roblox_player_index',
			"$base/pq_roblox_player_index.sql"
		);
	}

	/**
	 * Drop pq_roblox_player_index when required columns are missing so addExtensionTable can CREATE.
	 *
	 * @return bool
	 */
	public static function fixPqRobloxPlayerIndexTable( DatabaseUpdater $updater ) {
		$db = $updater->getDB();
		if ( !$db->tableExists( 'pq_roblox_player_index', __METHOD__ ) ) {
			return true;
		}
		$required = [ 'roblox_user_id', 'username_normalized', 'username_display', 'updated_at' ];
		foreach ( $required as $field ) {
			if ( !$db->fieldExists( 'pq_roblox_player_index', $field, __METHOD__ ) ) {
				$updater->output(
					"PixelQuestRoblox: pq_roblox_player_index has unexpected schema (missing column $field); dropping for recreate.\n"
				);
				$db->dropTable( 'pq_roblox_player_index', __METHOD__ );

				return true;
			}
		}

		return true;
	}

	/**
	 * @param array<string, mixed> &$def
	 */
	public static function onUserGetDefaultOptions( &$def ): void {
		// Multi-state privacy values:
		// - 'everyone'
		// - 'friends'
		// - 'none'
		// - 'guildmates' (placeholder; visibility rules may be added later)
		$def['pqroblox-pub-valor'] = 'everyone';
		$def['pqroblox-pub-last-seen'] = 'everyone';
		$def['pqroblox-pub-characters'] = 'everyone';
		$def['pqroblox-pub-characters-detail'] = 'everyone';
		$def['pqroblox-pub-characters-inventory'] = 'none';
		$def['pqroblox-pub-graveyard'] = 'everyone';
		$def['pqroblox-pub-skins'] = 'none';
		$def['pqroblox-pub-badges'] = 'none';
		$def['pqroblox-pub-honor'] = 'everyone';
		$def['pqroblox-pub-vault'] = 'none';
		$def['pqroblox-pub-account-stats'] = 'none';
	}

	/**
	 * @param \MediaWiki\User\User $user
	 * @param array<string, array<string, mixed>> &$prefs
	 */
	public static function onGetPreferences( $user, &$prefs ): void {
		$ctx = RequestContext::getMain();
		$userOptionsLookup = MediaWikiServices::getInstance()->getUserOptionsLookup();

		$optEveryone = $ctx->msg( 'pqroblox-privacy-everyone' )->text();
		$optFriends = $ctx->msg( 'pqroblox-privacy-friends' )->text();
		$optNone = $ctx->msg( 'pqroblox-privacy-none' )->text();
		$optGuild = $ctx->msg( 'pqroblox-privacy-guildmates' )->text();

		$options = [
			$optEveryone => 'everyone',
			$optFriends => 'friends',
			$optNone => 'none',
			$optGuild => 'guildmates',
		];

		$makeSelect = static function ( string $key, string $labelMessage, string $helpMessage, string $default ) use ( &$prefs, $user, $userOptionsLookup, $options ) : void {
			$current = (string)$userOptionsLookup->getOption( $user, $key, $default );
			// Legacy support for old boolean toggles ('1'/'0').
			if ( $current === '1' ) {
				$current = 'everyone';
			} elseif ( $current === '0' ) {
				$current = 'none';
			}
			$prefs[$key] = [
				'type' => 'select',
				'options' => $options,
				'default' => $current,
				'label-message' => $labelMessage,
				'help-message' => $helpMessage,
				'section' => 'pqroblox',
			];
		};

		$makeSelect(
			'pqroblox-pub-valor',
			'pqroblox-pref-valor',
			'pqroblox-pref-valor-help',
			'everyone'
		);
		$makeSelect(
			'pqroblox-pub-last-seen',
			'pqroblox-pref-last-seen',
			'pqroblox-pref-last-seen-help',
			'everyone'
		);
		$makeSelect(
			'pqroblox-pub-characters',
			'pqroblox-pref-characters',
			'pqroblox-pref-characters-help',
			'everyone'
		);
		$makeSelect(
			'pqroblox-pub-characters-detail',
			'pqroblox-pref-characters-detail',
			'pqroblox-pref-characters-detail-help',
			'everyone'
		);
		$makeSelect(
			'pqroblox-pub-characters-inventory',
			'pqroblox-pref-characters-inventory',
			'pqroblox-pref-characters-inventory-help',
			'none'
		);
		$makeSelect(
			'pqroblox-pub-graveyard',
			'pqroblox-pref-graveyard',
			'pqroblox-pref-graveyard-help',
			'everyone'
		);
		$makeSelect(
			'pqroblox-pub-skins',
			'pqroblox-pref-skins',
			'pqroblox-pref-skins-help',
			'none'
		);
		$makeSelect(
			'pqroblox-pub-badges',
			'pqroblox-pref-badges',
			'pqroblox-pref-badges-help',
			'none'
		);
		$makeSelect(
			'pqroblox-pub-honor',
			'pqroblox-pref-honor',
			'pqroblox-pref-honor-help',
			'everyone'
		);
		$makeSelect(
			'pqroblox-pub-vault',
			'pqroblox-pref-vault',
			'pqroblox-pref-vault-help',
			'none'
		);
		$makeSelect(
			'pqroblox-pub-account-stats',
			'pqroblox-pref-account-stats',
			'pqroblox-pref-account-stats-help',
			'none'
		);
	}

	/**
	 * Badge sprite size (20×20) for wiki pages: add class pq-roblox-badge-ico to badge images in infoboxes.
	 */
	public static function onBeforePageDisplay( OutputPage $out, Skin $skin ): void {
		if ( strtolower( (string)$out->getRequest()->getVal( 'action', 'view' ) ) !== 'view' ) {
			return;
		}
		$t = $out->getTitle();
		if ( !$t instanceof Title ) {
			return;
		}
		$n = $t->getNamespace();
		if ( $n !== \NS_MAIN && $n !== \NS_FILE ) {
			return;
		}
		$out->addModuleStyles( 'ext.pqroblox.badge' );
	}

	/**
	 * Auto-inject a protected Pixel Quest profile preview on User: pages.
	 * Keeps page editable (preview only on view mode).
	 *
	 * @param string &$text
	 */
	public static function onOutputPageBeforeHTML( OutputPage $out, &$text ): void {
		$title = $out->getTitle();
		if ( !$title instanceof Title || $title->getNamespace() !== \NS_USER ) {
			return;
		}
		if ( $title->isSubpage() ) {
			return;
		}
		$req = RequestContext::getMain()->getRequest();
		if ( strtolower( (string)$req->getVal( 'action', 'view' ) ) !== 'view' ) {
			return;
		}

		$target = User::newFromName( $title->getText(), false );
		if ( !$target || !$target->isRegistered() ) {
			return;
		}

		$store = new PqRobloxLinkStore();
		$link = $store->getLinkForWikiUser( $target->getId() );
		if ( $link === null ) {
			return;
		}

		$viewer = $out->getUser();
		$robloxId = (int)$link['robloxUserId'];
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

		$viewerRobloxId = null;
		if ( $viewer->isRegistered() ) {
			$vlink = $store->getLinkForWikiUser( $viewer->getId() );
			if ( $vlink !== null ) {
				$viewerRobloxId = (int)$vlink['robloxUserId'];
			}
		}

		$isOwner = $viewer->isRegistered() && $viewer->getId() === $target->getId();
		$show = self::resolveProfileVisibility( $viewer, $target, $isOwner, $viewerRobloxId, $robloxId );
		$playerData = PqRobloxDataStoreClient::getPlayerDataForRobloxUser( $robloxId, false );
		$lookup = PqRobloxLookupIndex::instance();

		$special = Title::makeTitle( \NS_SPECIAL, 'PQProfile/' . (int)$robloxId );
		$openLabel = htmlspecialchars( $out->getContext()->msg( 'pqroblox-userpage-preview-open' )->text(), ENT_QUOTES );
		$openHref = $special ? htmlspecialchars( $special->getFullURL(), ENT_QUOTES ) : '#';

		$out->addInlineStyle(
			'.pqroblox-userpage-preview{border:1px solid #c8ccd1;border-radius:4px;padding:.75rem;margin:1rem 0 0;background:#fff;}'
			. '.pqroblox-userpage-preview-divider{margin:0 0 .75rem;border:0;border-top:1px solid #c8ccd1;}'
			. '.pqroblox-userpage-preview p{margin:.2rem 0 .6rem;}'
		);
		$out->addInlineScript(
			"(function(){"
			. "function place(){"
			. "var preview=document.querySelector('.pqroblox-userpage-preview');"
			. "var parser=document.querySelector('.mw-parser-output');"
			. "if(!preview||!parser){return;}"
			. "parser.appendChild(preview);"
			. "}"
			. "if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',place);}else{place();}"
			. "})();"
		);
		$out->addHTML(
			'<section class="pqroblox-userpage-preview">'
			. '<hr class="pqroblox-userpage-preview-divider" />'
			. '<p><a href="' . $openHref . '">' . $openLabel . '</a></p>'
		);
		RobloxProfileRenderer::render(
			$out,
			$out->getContext(),
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
			$isOwner
		);
		$out->addHTML( '</section>' );
	}

	/**
	 * Shared visibility resolver used by Special:PQProfile and User: page embeds.
	 *
	 * @return array<string, bool>
	 */
	private static function resolveProfileVisibility(
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

	/**
	 * Keep Pixel Quest profile suggestions after normal wiki titles; append index matches.
	 *
	 * @param array<int, array<string, mixed>> &$results
	 */
	public static function onApiOpenSearchSuggest( array &$results ): void {
		$req = RequestContext::getMain()->getRequest();
		$q = trim( (string)$req->getVal( 'search', '' ) );
		if ( $q !== '' ) {
			$dbr = MediaWikiServices::getInstance()->getDBLoadBalancer()->getConnection( DB_REPLICA );
			if ( !$dbr->tableExists( 'pq_roblox_player_index', __METHOD__ ) ) {
				self::sortPqProfileSpecialsLast( $results );
				return;
			}
			$index = new PqRobloxPlayerIndexStore();
			$matches = [];
			if ( preg_match( '/^\d+$/', $q ) ) {
				$matches = array_merge( $matches, $index->searchRobloxIdsByPrefix( $q, 5 ) );
			}
			$matches = array_merge( $matches, $index->searchPrefix( $q, 8 ) );
			$dedup = [];
			$seenRid = [];
			foreach ( $matches as $m ) {
				$rid = (int)$m['robloxUserId'];
				if ( isset( $seenRid[$rid] ) ) {
					continue;
				}
				$seenRid[$rid] = true;
				$dedup[] = $m;
			}
			$matches = $dedup;
			$seen = [];
			foreach ( $results as $r ) {
				$t = $r['title'] ?? null;
				if ( $t instanceof Title ) {
					$seen[$t->getPrefixedDBkey()] = true;
				}
			}
			foreach ( $matches as $m ) {
				$rid = (int)$m['robloxUserId'];
				$name = str_replace( ' ', '_', $m['username_display'] );
				$t = Title::makeTitle( \NS_SPECIAL, 'PQProfile/' . $name );
				$key = $t->getPrefixedDBkey();
				if ( isset( $seen[$key] ) ) {
					continue;
				}
				$seen[$key] = true;
				$results[] = [
					'title' => $t,
					'redirect from' => null,
					'extract' => 'Pixel Quest profile — ' . $m['username_display'] . ' (' . $rid . ')',
					'extract trimmed' => false,
					'image' => [],
					'url' => $t->getFullURL(),
				];
			}
		}
		self::sortPqProfileSpecialsLast( $results );
	}

	/**
	 * @param array<int, array<string, mixed>> &$results
	 */
	private static function sortPqProfileSpecialsLast( array &$results ): void {
		$pq = [];
		$rest = [];
		foreach ( $results as $r ) {
			$t = $r['title'] ?? null;
			if ( $t instanceof Title && $t->inNamespace( \NS_SPECIAL ) ) {
				$x = $t->getText();
				if ( str_starts_with( $x, 'PQProfile/' ) || str_starts_with( $x, 'RobloxProfile/' ) ) {
					$pq[] = $r;
					continue;
				}
			}
			$rest[] = $r;
		}
		$results = array_merge( $rest, $pq );
	}
}
