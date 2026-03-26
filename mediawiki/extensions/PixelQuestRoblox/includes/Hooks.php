<?php

namespace PixelQuestRoblox;

use MediaWiki\Context\RequestContext;
use MediaWiki\Installer\DatabaseUpdater;
use MediaWiki\MediaWikiServices;

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
		$def['pqroblox-pub-skins'] = 'everyone';
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
}
