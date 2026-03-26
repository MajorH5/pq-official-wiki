<?php

namespace PixelQuestRoblox;

use MediaWiki\Context\IContextSource;
use MediaWiki\Html\Html;
use MediaWiki\Output\OutputPage;
use MediaWiki\Title\Title;
use MediaWiki\User\User;
use MediaWiki\Utils\MWTimestamp;
use PixelQuestRoblox\Service\PqRobloxLookupIndex;
use PixelQuestRoblox\Service\PqRobloxPlayerDataParser;
use PixelQuestRoblox\PqRobloxConfig;
use PixelQuestRoblox\PqRobloxTextureNames;
use PixelQuestRoblox\PqRobloxWikiFileUrl;

final class RobloxProfileRenderer {

	private const ICON_PX = 40;
	private const SKIN_ICON_PX = 50;
	private const VALOR_ICON_PX = 18;

	/** Canonical stat keys in display order (4 + 4 columns). */
	private const STAT_ORDER = [
		'health', 'mana', 'defense', 'vitality', 'speed', 'wisdom', 'attack', 'dexterity',
	];

	/** @var array<string, string> */
	private const STAT_ABBR = [
		'health' => 'HP',
		'mana' => 'MP',
		'defense' => 'DEF',
		'vitality' => 'VIT',
		'speed' => 'SPD',
		'wisdom' => 'WIS',
		'attack' => 'ATK',
		'dexterity' => 'DEX',
	];

	/**
	 * Graveyard death snapshot: stats array index order (matches game CharacterStats enum order).
	 *
	 * @var string[]
	 */
	private const GRAVE_STAT_ORDER = [
		'attack', 'defense', 'vitality', 'wisdom', 'health', 'mana', 'dexterity', 'speed',
	];

	private static function mwTimestampFromUnix( int $unix ): MWTimestamp {
		return new MWTimestamp( wfTimestamp( TS_MW, $unix ) );
	}

	/**
	 * Short relative time for last-seen (e.g. "3m ago", "5h ago", "12y 13m ago").
	 * Uses UTC; DateInterval: y/m = years/months, i = minutes.
	 */
	private static function formatLastSeenRelativeAgo( int $unixTs ): string {
		$then = new \DateTimeImmutable( '@' . $unixTs, new \DateTimeZone( 'UTC' ) );
		$now = new \DateTimeImmutable( 'now', new \DateTimeZone( 'UTC' ) );
		if ( $then >= $now ) {
			return '0s ago';
		}
		$d = $then->diff( $now );
		if ( $d->y > 0 ) {
			$parts = [ $d->y . 'y' ];
			if ( $d->m > 0 ) {
				$parts[] = $d->m . 'm';
			}
			return implode( ' ', $parts ) . ' ago';
		}
		if ( $d->m > 0 ) {
			return $d->m . 'mo ago';
		}
		if ( $d->d > 0 ) {
			return $d->d . 'd ago';
		}
		if ( $d->h > 0 ) {
			return $d->h . 'h ago';
		}
		if ( $d->i > 0 ) {
			return $d->i . 'm ago';
		}
		if ( $d->s > 0 ) {
			return $d->s . 's ago';
		}
		return '0s ago';
	}

	/**
	 * @param array<string, bool> $show
	 * @param array{name: string, displayName: string}|null $robloxPublic from users.roblox.com (cached)
	 */
	public static function render(
		OutputPage $out,
		IContextSource $ctx,
		User $viewer,
		User $target,
		int $robloxUserId,
		?array $playerData,
		PqRobloxLookupIndex $lookup,
		array $show,
		int $charPage = 1,
		int $gravePage = 1,
		string $graveSort = 'time',
		string $graveDir = 'desc',
		?int $graveMinValor = null,
		int $vaultPage = 1,
		bool $vaultHideEmpty = false,
		string $vaultTier = '',
		string $vaultType = '',
		string $vaultQ = '',
		?string $activeTab = null,
		?array $robloxPublic = null
	): void {
		$out->addModuleStyles( 'ext.pqroblox.profile' );
		$out->addModules( [ 'ext.pqroblox.profile' ] );
		$isOwner = $viewer->isRegistered() && $viewer->getId() === $target->getId();
		$out->addHTML( self::htmlProfileLead( $ctx, $robloxUserId, $robloxPublic ) );

		if ( $playerData === null ) {
			$out->addHTML( Html::rawElement( 'div', [ 'class' => 'warningbox' ],
				$ctx->msg( 'pqroblox-profile-nodata' )->escaped() ) );
			return;
		}

		if ( $isOwner || !empty( $show['valor'] ) ) {
			$valor = PqRobloxPlayerDataParser::getAccountValor( $playerData );
			if ( $valor !== null ) {
				$out->addHTML( Html::rawElement(
					'p',
					[ 'class' => 'pq-roblox-account-valor' ],
					'Account valor: ' . self::valorWithIconHtml( (int)$valor )
				) );
			}
		} elseif ( !$isOwner ) {
			$out->addHTML( Html::element( 'p', [ 'class' => 'pq-roblox-account-valor pq-roblox-muted' ],
				$ctx->msg( 'pqroblox-profile-account-valor-hidden' )->text() ) );
		}

		$out->addHTML( self::htmlLastSeenBlock( $ctx, $playerData, $show, $isOwner ) );

		$lang = $ctx->getLanguage();
		$title = $out->getTitle() ?? $ctx->getTitle();
		if ( !$title instanceof Title ) {
			$title = Title::newFromText( 'Special:RobloxProfile' );
		}

		if ( $isOwner ) {
			$panels = [
				[
					'id' => 'pq-roblox-panel-characters',
					'labelKey' => 'pqroblox-tab-characters',
					'html' => self::htmlCharacters( $ctx, $lookup, $playerData, $show, $target, $title, $charPage ),
				],
				[
					'id' => 'pq-roblox-panel-graveyard',
					'labelKey' => 'pqroblox-tab-graveyard',
					'html' => self::htmlGraveyard(
						$ctx,
						$lookup,
						$lang,
						$playerData,
						$gravePage,
						$target,
						$title,
						$graveSort,
						$graveDir,
						$graveMinValor
					),
				],
				[
					'id' => 'pq-roblox-panel-skins',
					'labelKey' => 'pqroblox-tab-skins',
					'html' => self::htmlSkinGrid( $ctx, $lookup, $playerData ),
				],
				[
					'id' => 'pq-roblox-panel-vault',
					'labelKey' => 'pqroblox-tab-vault',
					'html' => self::htmlVault( $ctx, $lookup, $playerData, $title, $vaultPage, $vaultHideEmpty, $vaultTier, $vaultType, $vaultQ ),
				],
				[
					'id' => 'pq-roblox-panel-account-stats',
					'labelKey' => 'pqroblox-tab-account-stats',
					'html' => self::htmlAccountStats( $ctx, $lookup, $playerData ),
				],
				[
					'id' => 'pq-roblox-panel-settings',
					'labelKey' => 'pqroblox-tab-settings',
					'html' => self::htmlSettingsPanel( $ctx ),
				],
			];
		} else {
			$hiddenHtml = self::htmlPanelHidden( $ctx );
			$panels = [
				[
					'id' => 'pq-roblox-panel-characters',
					'labelKey' => 'pqroblox-tab-characters',
					'html' => !empty( $show['characters'] )
						? self::htmlCharacters( $ctx, $lookup, $playerData, $show, $target, $title, $charPage )
						: $hiddenHtml,
				],
				[
					'id' => 'pq-roblox-panel-graveyard',
					'labelKey' => 'pqroblox-tab-graveyard',
					'html' => !empty( $show['graveyard'] )
						? self::htmlGraveyard(
							$ctx,
							$lookup,
							$lang,
							$playerData,
							$gravePage,
							$target,
							$title,
							$graveSort,
							$graveDir,
							$graveMinValor
						)
						: $hiddenHtml,
				],
				[
					'id' => 'pq-roblox-panel-skins',
					'labelKey' => 'pqroblox-tab-skins',
					'html' => !empty( $show['skins'] )
						? self::htmlSkinGrid( $ctx, $lookup, $playerData )
						: $hiddenHtml,
				],
				[
					'id' => 'pq-roblox-panel-vault',
					'labelKey' => 'pqroblox-tab-vault',
					'html' => !empty( $show['vault'] )
						? self::htmlVault( $ctx, $lookup, $playerData, $title, $vaultPage, $vaultHideEmpty, $vaultTier, $vaultType, $vaultQ )
						: $hiddenHtml,
				],
				[
					'id' => 'pq-roblox-panel-account-stats',
					'labelKey' => 'pqroblox-tab-account-stats',
					'html' => !empty( $show['account_stats'] )
						? self::htmlAccountStats( $ctx, $lookup, $playerData )
						: $hiddenHtml,
				],
			];
		}

		if ( count( $panels ) === 1 ) {
			$out->addHTML( $panels[0]['html'] );
			return;
		}

		$out->addHTML( self::wrapTabPanels( $ctx, $panels, $activeTab ) );
	}

	private static function htmlPanelHidden( IContextSource $ctx ): string {
		return Html::element( 'p', [ 'class' => 'pq-roblox-muted pq-roblox-panel-hidden' ],
			$ctx->msg( 'pqroblox-profile-hidden' )->text() );
	}

	/**
	 * External link to roblox.com profile; link text is i18n ("Roblox profile").
	 */
	private static function htmlRobloxProfileLink( IContextSource $ctx, int $robloxUserId ): string {
		$url = 'https://www.roblox.com/users/' . $robloxUserId . '/profile';
		$label = $ctx->msg( 'pqroblox-profile-roblox-link-label' )->text();
		return Html::element( 'a', [
			'href' => $url,
			'class' => 'external',
			'rel' => 'nofollow noopener noreferrer',
			'target' => '_blank',
		], $label );
	}

	/**
	 * @param array{name: string, displayName: string}|null $robloxPublic
	 */
	private static function htmlProfileLead(
		IContextSource $ctx,
		int $robloxUserId,
		?array $robloxPublic
	): string {
		$profileLink = self::htmlRobloxProfileLink( $ctx, $robloxUserId );
		if ( $robloxPublic !== null && $robloxPublic['name'] !== '' ) {
			$n = $robloxPublic['name'];
			$dn = $robloxPublic['displayName'] ?? '';
			$inner = Html::element( 'strong', [], $n );
			if ( $dn !== '' && $dn !== $n ) {
				$inner .= ' ' . Html::element( 'span', [ 'class' => 'pq-roblox-muted' ], '(' . $dn . ')' );
			}
			$inner .= ' · ' . $profileLink;
			return Html::rawElement( 'p', [ 'class' => 'pq-roblox-profile-lead' ], $inner );
		}
		return Html::rawElement( 'p', [ 'class' => 'pq-roblox-profile-lead' ], $profileLink );
	}

	/**
	 * @param array<string, bool> $show
	 */
	private static function htmlLastSeenBlock(
		IContextSource $ctx,
		array $playerData,
		array $show,
		bool $isOwner
	): string {
		if ( !$isOwner && empty( $show['last_seen'] ) ) {
			return Html::element( 'p', [ 'class' => 'pq-roblox-last-seen pq-roblox-muted' ],
				$ctx->msg( 'pqroblox-profile-last-seen-hidden' )->text() );
		}

		$online = null; // null means: extraction failed / unknown
		$meta = $playerData['MetaData'] ?? $playerData['metadata'] ?? $playerData['Metadata'] ?? null;
		if ( $meta === null ) {
			// Be tolerant of casing differences.
			foreach ( $playerData as $k => $v ) {
				if ( is_string( $k ) && strtolower( $k ) === 'metadata' ) {
					$meta = $v;
					break;
				}
			}
		}
		if ( is_array( $meta ) ) {
			$active = $meta['ActiveSession'] ?? $meta['activeSession'] ?? $meta['activesession'] ?? null;
			if ( $active === null ) {
				foreach ( $meta as $k => $v ) {
					if ( is_string( $k ) && strtolower( $k ) === 'activesession' ) {
						$active = $v;
						break;
					}
				}
			}
			if ( is_array( $active ) ) {
				$online = count( $active ) > 0;
			} elseif ( is_numeric( $active ) ) {
				$online = ( (int)$active ) > 0;
			} elseif ( is_bool( $active ) ) {
				$online = $active;
			}
			if ( $online === null ) {
				wfDebugLog(
					'pqroblox',
					'[LastSeen] online dot not computed (activeSession missing/unknown). meta_keys='
					. implode( ',', array_keys( $meta ) )
				);
			}
		}

		// Requirement: if online extraction fails, show offline red dot.
		if ( $online === null ) {
			$online = false;
		}

		$joined = null;
		if ( array_key_exists( 'ProfileCreateTime', $playerData ) && is_numeric( $playerData['ProfileCreateTime'] ) ) {
			$t = (float)$playerData['ProfileCreateTime'];
			while ( $t > 1e12 ) {
				$t /= 1000.0;
			}
			$ti = (int)floor( $t );
			if ( $ti > 0 ) {
				$joined = gmdate( 'Y-m-d', $ti );
			}
		}

		$dotClass = $online ? 'pq-roblox-online-dot is-online' : 'pq-roblox-online-dot is-offline';
		$label = $online ? 'Online' : 'Offline';
		$onlineDot = Html::rawElement( 'span', [
			'class' => $dotClass,
			'title' => $label,
			'aria-label' => $label,
		], '' );
		$statusLine = Html::rawElement(
			'p',
			[ 'class' => 'pq-roblox-last-seen-line' ],
			'Status: ' . htmlspecialchars( $label, ENT_QUOTES ) . ' ' . $onlineDot
		);
		$resolved = PqRobloxPlayerDataParser::resolveLastSeenForDisplay( $playerData );
		$cls = 'pq-roblox-last-seen';
		if ( $online ) {
			$lastSeenNow = Html::element( 'p', [ 'class' => 'pq-roblox-last-seen-line' ], 'Last seen (approx.): now' );
			$joinedLine = $joined !== null
				? Html::element( 'p', [ 'class' => 'pq-roblox-last-seen-line pq-roblox-muted' ], 'Joined: ' . $joined )
				: '';
			return Html::rawElement( 'div', [ 'class' => $cls ], $statusLine . $lastSeenNow . $joinedLine );
		}

		if ( $resolved === null ) {
			// lastSeen missing: still show join date if available.
			$lastSeenText = $joined !== null ? ( 'Joined: ' . $joined ) : 'Last seen: —';
			return Html::rawElement( 'div', [ 'class' => $cls ],
				$statusLine . Html::element( 'p', [ 'class' => 'pq-roblox-last-seen-line' ], $lastSeenText ) );
		}

		$formatted = self::formatLastSeenRelativeAgo( $resolved['unix'] );
		$lastSeenText = '';
		if ( !empty( $resolved['approximate'] ) ) {
			$formatted = self::formatApproxLastSeenDays( $resolved['unix'] );
			$lastSeenText = 'Last seen (approx.): ' . $formatted;
		} else {
			$lastSeenText = 'Last seen: ' . $formatted;
		}
		$joinedLine = $joined !== null
			? Html::element( 'p', [ 'class' => 'pq-roblox-last-seen-line pq-roblox-muted' ], 'Joined: ' . $joined )
			: '';
		return Html::rawElement( 'div', [ 'class' => $cls ],
			$statusLine
			. Html::element( 'p', [ 'class' => 'pq-roblox-last-seen-line' ], $lastSeenText )
			. $joinedLine );
	}

	private static function formatApproxLastSeenDays( int $unixMidnight ): string {
		$then = new \DateTimeImmutable( '@' . $unixMidnight, new \DateTimeZone( 'UTC' ) );
		$now = new \DateTimeImmutable( 'now', new \DateTimeZone( 'UTC' ) );
		$secs = $now->getTimestamp() - $then->getTimestamp();
		if ( $secs <= 0 ) {
			return 'today';
		}
		$days = (int)ceil( $secs / 86400 );
		if ( $days <= 0 ) {
			return 'today';
		}
		if ( $days === 1 ) {
			return '1d ago';
		}
		return $days . 'd ago';
	}

	private static function htmlPrefsHintBlock( IContextSource $ctx, bool $isBottom ): string {
		$prefTitle = Title::newFromText( 'Special:Preferences' );
		$href = $prefTitle ? $prefTitle->getFullURL( [ 'returntoquery' => 'mw-prefsection-pqroblox' ] ) : '#';
		$classes = 'pq-roblox-prefs-hint' . ( $isBottom ? ' is-bottom' : ' is-top' );
		$text = Html::element( 'span', [ 'class' => 'pq-roblox-muted' ],
			'Privacy settings control what others can see on your profile.' );
		$btn = Html::element( 'a', [ 'class' => 'pq-roblox-control-link', 'href' => $href ],
			'Open Pixel Quest privacy settings' );
		return Html::rawElement( 'div', [ 'class' => $classes ], $text . ' ' . $btn );
	}

	private static function htmlSettingsPanel( IContextSource $ctx ): string {
		$prefTitle = Title::newFromText( 'Special:Preferences' );
		$href = $prefTitle ? ( $prefTitle->getFullURL() . '#mw-prefsection-pqroblox' ) : '#';
		$btn = Html::element( 'a', [ 'class' => 'pq-roblox-control-link', 'href' => $href ],
			'Open Pixel Quest profile privacy settings' );
		$lead = Html::element( 'p', [ 'class' => 'pq-roblox-muted' ],
			'Control who can view each profile section (Everyone, Friends, No one, Guildmates).' );
		return Html::rawElement( 'div', [ 'class' => 'pq-roblox-settings-panel' ], $lead . $btn );
	}

	private static function numericFromUnknown( mixed $raw ): ?float {
		if ( is_numeric( $raw ) ) {
			return (float)$raw;
		}
		if ( is_array( $raw ) ) {
			foreach ( [ 'value', 'Value', 'amount', 'Amount', 'current', 'Current' ] as $k ) {
				if ( array_key_exists( $k, $raw ) && is_numeric( $raw[$k] ) ) {
					return (float)$raw[$k];
				}
			}
		}
		return null;
	}

	/**
	 * @param array<string, mixed> $playerData
	 * @return array<string, mixed>
	 */
	private static function resolveAccountStatsMap( array $playerData ): array {
		// Expected shape: value.Data.progressTrackers.accountStats (string id keys).
		$candidates = [];
		$candidates[] = $playerData;
		if ( isset( $playerData['Data'] ) && is_array( $playerData['Data'] ) ) {
			$candidates[] = $playerData['Data'];
		}
		if ( isset( $playerData['value'] ) && is_array( $playerData['value'] ) ) {
			$candidates[] = $playerData['value'];
			if ( isset( $playerData['value']['Data'] ) && is_array( $playerData['value']['Data'] ) ) {
				$candidates[] = $playerData['value']['Data'];
			}
		}

		foreach ( $candidates as $root ) {
			$trackers = $root['progressTrackers'] ?? $root['ProgressTrackers'] ?? null;
			if ( !is_array( $trackers ) ) {
				continue;
			}
			$accountStats = $trackers['accountStats'] ?? $trackers['AccountStats'] ?? null;
			if ( is_array( $accountStats ) ) {
				return $accountStats;
			}
		}
		return [];
	}

	private static function accountStatValueForId( array $accountStats, int $id ): int {
		// Canonical shape: accountStats.progress["id"].
		$progress = $accountStats['progress'] ?? $accountStats['Progress'] ?? null;
		if ( is_array( $progress ) ) {
			$key = (string)$id;
			if ( array_key_exists( $key, $progress ) ) {
				$n = self::numericFromUnknown( $progress[$key] );
				if ( $n !== null ) {
					return (int)floor( $n );
				}
			}
			if ( array_key_exists( $id, $progress ) ) {
				$n = self::numericFromUnknown( $progress[$id] );
				if ( $n !== null ) {
					return (int)floor( $n );
				}
			}
		}

		// Compatibility fallback: some older payloads may have direct id-key maps.
		$key = (string)$id;
		if ( array_key_exists( $key, $accountStats ) ) {
			$n = self::numericFromUnknown( $accountStats[$key] );
			if ( $n !== null ) {
				return (int)floor( $n );
			}
		}

		return 0;
	}

	/**
	 * @param array<string, mixed> $playerData
	 */
	private static function htmlAccountStats(
		IContextSource $ctx,
		PqRobloxLookupIndex $lookup,
		array $playerData
	): string {
		$defs = $lookup->getAllAccountStatsOrdered();
		if ( $defs === [] ) {
			return Html::element( 'p', [ 'class' => 'pq-roblox-muted' ], $ctx->msg( 'pqroblox-profile-none' )->text() );
		}

		$accountStats = self::resolveAccountStatsMap( $playerData );

		$rows = '';
		$lang = $ctx->getLanguage();
		foreach ( $defs as $id => $row ) {
			$name = (string)( $row['Name'] ?? ( 'Account Stat ' . $id ) );
			$category = (string)( $row['Category'] ?? '' );
			$title = Title::newFromText( $lookup->getAccountStatPageTitle( (int)$id ) );
			$nameHtml = $title ? Html::element( 'a', [ 'href' => $title->getFullURL() ], $name ) : htmlspecialchars( $name, ENT_QUOTES );
			if ( $category !== '' ) {
				$nameHtml .= Html::element( 'span', [ 'class' => 'pq-roblox-muted' ], ' (' . $category . ')' );
			}

			$val = self::accountStatValueForId( $accountStats, (int)$id );
			$rows .= Html::rawElement(
				'tr',
				[],
				Html::rawElement( 'td', [ 'class' => 'pq-roblox-td-tight' ], $nameHtml )
				. Html::element( 'td', [ 'class' => 'pq-roblox-td-c pq-roblox-td-tight' ], $lang->formatNum( $val ) )
			);
		}

		$head = Html::rawElement(
			'thead',
			[],
			Html::rawElement(
				'tr',
				[],
				Html::element( 'th', [], $ctx->msg( 'pqroblox-accountstats-col-stat' )->text() )
				. Html::element( 'th', [ 'class' => 'pq-roblox-td-c' ], $ctx->msg( 'pqroblox-accountstats-col-value' )->text() )
			)
		);
		return Html::rawElement( 'table', [ 'class' => 'wikitable pq-roblox-account-stats' ],
			$head . Html::rawElement( 'tbody', [], $rows ) );
	}

	/**
	 * @param array<int, array{id:string,labelKey:string,html:string}> $panels
	 */
	private static function wrapTabPanels( IContextSource $ctx, array $panels, ?string $activeTab ): string {
		$nav = '';
		$activeId = $activeTab;
		if ( $activeId === null ) {
			$activeId = $panels[0]['id'] ?? null;
		} else {
			$ids = array_map( static function ( $p ) { return $p['id']; }, $panels );
			if ( !in_array( $activeId, $ids, true ) ) {
				$activeId = $panels[0]['id'] ?? null;
			}
		}
		$activeId = $activeId ?? ( $panels[0]['id'] ?? '' );
		foreach ( $panels as $i => $p ) {
			$isActive = $p['id'] === $activeId;
			$nav .= Html::element( 'button', [
				'type' => 'button',
				'class' => 'pq-roblox-tab' . ( $isActive ? ' is-active' : '' ),
				'data-tab' => $p['id'],
				'role' => 'tab',
				'aria-selected' => $isActive ? 'true' : 'false',
			], $ctx->msg( $p['labelKey'] )->text() );
		}
		$body = '';
		foreach ( $panels as $i => $p ) {
			$attrs = [
				'id' => $p['id'],
				'class' => 'pq-roblox-tabpanel',
				'role' => 'tabpanel',
			];
			if ( $p['id'] !== $activeId ) {
				$attrs['hidden'] = 'hidden';
			}
			$body .= Html::rawElement( 'div', $attrs, $p['html'] );
		}
		return Html::rawElement( 'div', [ 'class' => 'pq-roblox-profile-tabs' ],
			Html::rawElement( 'div', [ 'class' => 'pq-roblox-tablist', 'role' => 'tablist' ], $nav )
			. $body
		);
	}

	/**
	 * @param array<string, bool> $show
	 * @param array<string, mixed> $playerData
	 */
	private static function htmlCharacters(
		IContextSource $ctx,
		PqRobloxLookupIndex $lookup,
		array $playerData,
		array $show,
		User $target,
		Title $title,
		int $charPage
	): string {
		$chars = PqRobloxPlayerDataParser::getCharactersMap( $playerData );
		$html = '';
		if ( $chars === [] ) {
			return Html::element( 'p', [ 'class' => 'pq-roblox-muted' ], $ctx->msg( 'pqroblox-profile-none' )->text() );
		}

		$accLvl = PqRobloxPlayerDataParser::getAccountLevel( $playerData );
		if ( $accLvl !== null ) {
			$html .= Html::element( 'p', [ 'class' => 'pq-roblox-account-level' ],
				$ctx->msg( 'pqroblox-profile-account-level', $accLvl )->text() );
		}

		$detail = !empty( $show['characters_detail'] );
		$invPref = !empty( $show['characters_inventory'] );

		$headCells = [
			Html::element( 'th', [ 'class' => 'pq-roblox-col-name' ], $ctx->msg( 'pqroblox-profile-col-name' )->text() ),
			Html::element( 'th', [ 'class' => 'pq-roblox-col-lvl' ], $ctx->msg( 'pqroblox-profile-col-level' )->text() ),
			Html::element( 'th', [ 'class' => 'pq-roblox-col-valor' ], $ctx->msg( 'pqroblox-profile-col-valor' )->text() ),
		];
		if ( $detail ) {
			$headCells[] = Html::element( 'th', [ 'class' => 'pq-roblox-col-eq' ],
				$ctx->msg( 'pqroblox-profile-col-equipment' )->text() );
			$headCells[] = Html::element( 'th', [ 'class' => 'pq-roblox-col-stats' ],
				$ctx->msg( 'pqroblox-profile-col-stats' )->text() );
		}
		if ( $invPref ) {
			$headCells[] = Html::element( 'th', [ 'class' => 'pq-roblox-col-inv' ],
				$ctx->msg( 'pqroblox-profile-col-inventory' )->text() );
		}

		$thead = Html::rawElement( 'thead', [], Html::rawElement( 'tr', [], implode( '', $headCells ) ) );
		$charPage = max( 1, $charPage );
		$per = 15;
		$total = count( $chars );
		$pages = (int)max( 1, ceil( $total / $per ) );
		$charPage = min( $charPage, $pages );
		$offset = ( $charPage - 1 ) * $per;
		$slice = array_slice( $chars, $offset, $per, true );

		$rows = '';
		foreach ( $slice as $slot => $char ) {
			if ( !is_array( $char ) ) {
				continue;
			}
			$rows .= self::characterRow( $lookup, $char, $slot, $detail, $invPref );
		}

		$base = [ 'tab' => 'pq-roblox-panel-characters' ];
		$prevDisabled = ( $charPage <= 1 );
		$nextDisabled = ( $charPage >= $pages );
		$prevHref = $title->getFullURL( $base + [ 'charpage' => max( 1, $charPage - 1 ) ] );
		$nextHref = $title->getFullURL( $base + [ 'charpage' => min( $pages, $charPage + 1 ) ] );
		$prev = Html::element(
			'a',
			[
				'class' => 'pq-roblox-control-link' . ( $prevDisabled ? ' is-disabled' : '' ),
				'href' => $prevDisabled ? '#' : $prevHref,
				'aria-disabled' => $prevDisabled ? 'true' : 'false',
				'tabindex' => $prevDisabled ? '-1' : null,
			],
			'Prev'
		);
		$next = Html::element(
			'a',
			[
				'class' => 'pq-roblox-control-link' . ( $nextDisabled ? ' is-disabled' : '' ),
				'href' => $nextDisabled ? '#' : $nextHref,
				'aria-disabled' => $nextDisabled ? 'true' : 'false',
				'tabindex' => $nextDisabled ? '-1' : null,
			],
			'Next'
		);
		$mid = Html::element( 'span', [ 'class' => 'pq-roblox-muted pq-roblox-pager-mid' ], 'Page ' . $charPage . ' / ' . $pages );
		$pager = Html::rawElement( 'div', [ 'class' => 'pq-roblox-pager-links' ], $prev . $mid . $next );

		$html .= $pager;
		$html .= Html::rawElement( 'div', [ 'class' => 'pq-roblox-characters-wrap' ],
			Html::rawElement( 'table', [ 'class' => 'wikitable pq-roblox-characters' ],
				$thead . Html::rawElement( 'tbody', [], $rows ) ) );
		$html .= $pager;
		return $html;
	}

	/**
	 * @param array<string, mixed> $char
	 */
	private static function characterRow(
		PqRobloxLookupIndex $lookup,
		array $char,
		string $slot,
		bool $detail,
		bool $invPref
	): string {
		$name = (string)( $char['characterName'] ?? $char['CharacterName'] ?? ( 'Character ' . $slot ) );
		$skinId = (int)( $char['characterSkinId'] ?? $char['CharacterSkinId'] ?? 0 );
		$skinTitle = Title::newFromText( $lookup->getSkinPageTitle( $skinId ) );
		$skinUrl = $skinId > 0 ? $lookup->getSkinGridIconUrl( $skinId ) : null;
		$skinPart = $skinId > 0
			? self::iconOnlyLink( $skinTitle, $skinUrl, 'pq-roblox-char-skin-ico', self::SKIN_ICON_PX )
			: '';
		$nameCell = Html::rawElement( 'div', [ 'class' => 'pq-roblox-name-cell' ],
			Html::element( 'span', [ 'class' => 'pq-roblox-char-name' ], $name )
			. ( $skinPart !== '' ? ' ' . $skinPart : '' )
		);

		$cLvl = PqRobloxPlayerDataParser::getCharacterLevel( $char );
		$lvlCell = Html::element( 'td', [ 'class' => 'pq-roblox-td-c pq-roblox-td-tight pq-roblox-col-lvl' ],
			$cLvl !== null ? (string)$cLvl : '—' );

		$valorInt = (int)floor( PqRobloxPlayerDataParser::characterValorFromExp( $char ) );
		$valorHtml = self::valorWithIconHtml( $valorInt );
		$valorCell = Html::rawElement(
			'td',
			[ 'class' => 'pq-roblox-td-c pq-roblox-td-tight pq-roblox-col-valor' ],
			$valorHtml
		);

		$cells = [
			Html::rawElement( 'td', [ 'class' => 'pq-roblox-td-tight pq-roblox-col-name' ], $nameCell ),
			$lvlCell,
			$valorCell,
		];

		if ( $detail ) {
			$cells[] = Html::rawElement( 'td', [ 'class' => 'pq-roblox-td-c pq-roblox-td-tight pq-roblox-col-eq' ],
				self::equipmentIconsHtml( $lookup, $char ) );
			$statsRaw = $char['characterStats'] ?? $char['CharacterStats'] ?? null;
			$stats = PqRobloxPlayerDataParser::normalizeStats( $statsRaw );
			$cells[] = Html::rawElement( 'td', [ 'class' => 'pq-roblox-td-tight pq-roblox-td-stats pq-roblox-col-stats' ],
				self::statsBlockHtml( $lookup, $stats ) );
		}

		if ( $invPref ) {
			$invSlots = PqRobloxPlayerDataParser::getInventorySlotCount( $char );
			$inv = $char['inventory'] ?? [];
			if ( !is_array( $inv ) ) {
				$inv = [];
			}
			$cells[] = Html::rawElement( 'td', [ 'class' => 'pq-roblox-td-tight pq-roblox-col-inv' ],
				self::inventoryChunksHtml( $lookup, $inv, $invSlots ) );
		}

		return Html::rawElement( 'tr', [], implode( '', $cells ) );
	}

	/**
	 * @param array<string, mixed> $char
	 */
	private static function equipmentIconsHtml( PqRobloxLookupIndex $lookup, array $char ): string {
		$norms = [
			self::normalizeEquippedField( $char['equippedPrimary'] ?? $char['EquippedPrimary'] ?? null ),
			self::normalizeEquippedField( $char['equippedSecondary'] ?? $char['EquippedSecondary'] ?? null ),
			self::normalizeEquippedField( $char['equippedArmor'] ?? $char['EquippedArmor'] ?? null ),
			self::normalizeEquippedField( $char['equippedAccessory'] ?? $char['EquippedAccessory'] ?? null ),
		];
		return self::equipmentIconsFromIds( $lookup, $norms );
	}

	/**
	 * @return array{id:int, quantity:int, metadata:mixed}|null
	 */
	private static function normalizeEquippedField( mixed $raw ): ?array {
		if ( $raw === null || $raw === 'nil' ) {
			return null;
		}
		if ( is_array( $raw ) ) {
			return PqRobloxPlayerDataParser::normalizeItemBlob( $raw );
		}
		return PqRobloxPlayerDataParser::normalizeItemBlob( [ 'id' => (int)$raw, 'quantity' => 1 ] );
	}

	/**
	 * @param array<int, array{id:int, quantity:int, metadata:mixed}|null> $norms
	 */
	private static function equipmentIconsFromIds( PqRobloxLookupIndex $lookup, array $norms ): string {
		$parts = [];
		foreach ( $norms as $norm ) {
			$id = ( $norm !== null && (int)( $norm['id'] ?? 0 ) > 0 ) ? (int)$norm['id'] : 0;
			$meta = is_array( $norm ) ? ( $norm['metadata'] ?? null ) : null;
			if ( $id <= 0 ) {
				$parts[] = Html::rawElement( 'span', [ 'class' => 'pq-roblox-eq-empty' ], "\u{00A0}" );
			} else {
				// Skin items: show the actual skin icon (metadata.rid) instead of the generic "Skin" item texture.
				$rid = self::metadataSkinRid( $meta );
				if ( $rid !== null && $lookup->isSkinItem( $id ) ) {
					$t = Title::newFromText( $lookup->getSkinPageTitle( $rid ) );
					$url = $lookup->getSkinGridIconUrl( $rid );
					// Item slots/equipment use the shared 40px sizing.
					$iconPx = self::ICON_PX;
				} else {
					$t = Title::newFromText( $lookup->getItemPageTitle( $id ) );
					$url = $lookup->getItemTextureWikiUrl( $id );
					$iconPx = self::ICON_PX;
				}
				$link = self::iconOnlyLink( $t, $url, 'pq-roblox-eq-ico', $iconPx );
				$tier = self::tierCornerImgHtml( $lookup, $id, $meta );
				$parts[] = Html::rawElement( 'div', [ 'class' => 'pq-roblox-eq-slot' ], $link . $tier );
			}
		}
		return Html::rawElement( 'div', [ 'class' => 'pq-roblox-eq-row pq-roblox-eq-cell' ], implode( '', $parts ) );
	}

	/** metadata.rid → CharacterSkin id (bot/shared.py skin drops). */
	private static function metadataSkinRid( mixed $meta ): ?int {
		if ( !is_array( $meta ) ) {
			return null;
		}
		foreach ( [ 'rid', 'Rid', 'RID' ] as $k ) {
			if ( isset( $meta[$k] ) && is_numeric( $meta[$k] ) ) {
				$i = (int)$meta[$k];
				return $i > 0 ? $i : null;
			}
		}
		return null;
	}

	/**
	 * Bottom-right: skin rarity (Skin item + metadata.rid) per skin_drops.py / skin_rarity_icons.py;
	 * else item TierIcon or loot chest tier.
	 *
	 * @param mixed $metadata
	 */
	private static function tierCornerImgHtml( PqRobloxLookupIndex $lookup, int $id, $metadata = null ): string {
		if ( $id <= 0 ) {
			return '';
		}
		$rid = self::metadataSkinRid( $metadata );
		if ( $rid !== null && $lookup->isSkinItem( $id ) ) {
			$skinRow = $lookup->getSkinRow( $rid );
			if ( $skinRow ) {
				$rarity = (int)( $skinRow['Rarity'] ?? 0 );
				$rareUrl = $lookup->getSkinRarityIconUrl( $rarity );
				if ( $rareUrl ) {
					return Html::element( 'img', [
						'src' => $rareUrl,
						'alt' => '',
						'title' => 'Rarity',
						'class' => 'pq-roblox-inv-tier',
						'width' => 16,
						'height' => 16,
						'loading' => 'lazy',
					] );
				}
			}
		}
		$tierUrl = $lookup->getItemTierIconWikiUrl( $id );
		if ( !$tierUrl ) {
			$tier = $lookup->getItemDropTierType( $id );
			if ( $tier > 0 ) {
				$tierUrl = $lookup->getLootTierIconUrl( $tier, 'chest' );
			}
		}
		if ( !$tierUrl ) {
			return '';
		}
		return Html::element( 'img', [
			'src' => $tierUrl,
			'alt' => '',
			'title' => 'Tier',
			'class' => 'pq-roblox-inv-tier',
			'width' => 20,
			'height' => 20,
			'loading' => 'lazy',
		] );
	}

	/**
	 * @param array<string, scalar|string> $stats
	 */
	private static function statsBlockHtml( PqRobloxLookupIndex $lookup, array $stats ): string {
		if ( $stats === [] ) {
			return Html::element( 'span', [ 'class' => 'pq-roblox-muted' ], '—' );
		}
		$leftCol = '';
		$rightCol = '';
		for ( $i = 0; $i < 4; $i++ ) {
			$lk = self::STAT_ORDER[$i];
			$rk = self::STAT_ORDER[$i + 4];
			$leftCol .= self::statLineHtml( $lookup, $stats, $lk );
			$rightCol .= self::statLineHtml( $lookup, $stats, $rk );
		}
		return Html::rawElement( 'div', [ 'class' => 'pq-roblox-stats-block' ],
			Html::rawElement( 'div', [ 'class' => 'pq-roblox-stats-col' ], $leftCol )
			. Html::rawElement( 'div', [ 'class' => 'pq-roblox-stats-col' ], $rightCol )
		);
	}

	/**
	 * @param array<string, scalar|string> $stats
	 */
	private static function statLineHtml( PqRobloxLookupIndex $lookup, array $stats, string $canonical ): string {
		$v = self::statValueForKey( $stats, $canonical );
		$abbr = self::STAT_ABBR[$canonical] ?? strtoupper( substr( $canonical, 0, 3 ) );
		$icon = $lookup->statIconHtmlForKey( $canonical );
		$valS = $v !== null && is_scalar( $v ) ? (string)$v : '—';
		$labelTitle = ucfirst( $canonical );
		$label = Html::element( 'span', [
			'class' => 'pq-roblox-stat-abbr',
			'title' => $labelTitle,
		], $abbr );
		return Html::rawElement( 'div', [ 'class' => 'pq-roblox-stat-line' ],
			$icon . $label . Html::element( 'span', [ 'class' => 'pq-roblox-stat-val' ], $valS )
		);
	}

	/**
	 * @param array<string, scalar|string> $stats
	 */
	private static function statValueForKey( array $stats, string $canonical ): mixed {
		foreach ( $stats as $k => $v ) {
			if ( strcasecmp( (string)$k, $canonical ) === 0 ) {
				return is_scalar( $v ) ? $v : null;
			}
		}
		return null;
	}

	/**
	 * @param array<string, mixed> $inv
	 */
	private static function inventoryChunksHtml( PqRobloxLookupIndex $lookup, array $inv, int $totalSlots ): string {
		$totalSlots = max( 1, $totalSlots );
		$numChunks = (int)ceil( $totalSlots / 8 );
		$chunks = [];
		for ( $c = 0; $c < $numChunks; $c++ ) {
			if ( $c * 8 >= $totalSlots ) {
				break;
			}
			$chunkHtml = self::inventoryChunkGrid( $lookup, $inv, $c, $totalSlots );
			$cls = 'pq-roblox-inv-chunk' . ( $c >= 1 ? ' pq-roblox-inv-chunk-backpack' : '' );
			$chunks[] = Html::rawElement( 'div', [ 'class' => $cls ], $chunkHtml );
		}
		return Html::rawElement( 'div', [ 'class' => 'pq-roblox-inv-bundles' ], implode( '', $chunks ) );
	}

	/**
	 * One 4×2 grid (8 slots), row-major.
	 *
	 * @param array<string, mixed> $inv
	 */
	private static function inventoryChunkGrid(
		PqRobloxLookupIndex $lookup,
		array $inv,
		int $chunkIndex,
		int $totalSlots
	): string {
		$cells = '';
		for ( $local = 0; $local < 8; $local++ ) {
			$global = $chunkIndex * 8 + $local;
			if ( $global >= $totalSlots ) {
				break;
			}
			$cells .= self::inventorySlotCell( $lookup, $inv, $global );
		}
		return Html::rawElement( 'div', [ 'class' => 'pq-roblox-inv-grid-4x2' ], $cells );
	}

	/**
	 * @param array<string, mixed> $inv
	 */
	private static function inventorySlotCell( PqRobloxLookupIndex $lookup, array $inv, int $slotZeroBased ): string {
		$blob = self::inventoryBlobForSlot( $inv, $slotZeroBased );
		if ( $blob === null ) {
			return Html::rawElement( 'div', [ 'class' => 'pq-roblox-inv-slot pq-roblox-inv-slot-empty' ], '' );
		}
		$norm = PqRobloxPlayerDataParser::normalizeItemBlob( $blob );
		if ( $norm === null || $norm['id'] === 0 ) {
			return Html::rawElement( 'div', [ 'class' => 'pq-roblox-inv-slot pq-roblox-inv-slot-empty' ], '' );
		}
		return self::itemSlotFilledHtml( $lookup, $norm['id'], $norm['quantity'], true, $norm['metadata'] ?? null );
	}

	/**
	 * Shared item cell: icon, optional qty (if stackable), optional tier (inventory / vault / equipment).
	 *
	 * @param mixed $metadata
	 */
	private static function itemSlotFilledHtml(
		PqRobloxLookupIndex $lookup,
		int $id,
		int $qty,
		bool $showTier,
		$metadata = null
	): string {
		// Skin items: show the actual skin icon (metadata.rid) instead of the generic "Skin" item texture.
		$rid = self::metadataSkinRid( $metadata );
		if ( $rid !== null && $lookup->isSkinItem( $id ) ) {
			$t = Title::newFromText( $lookup->getSkinPageTitle( $rid ) );
			$icon = $lookup->getSkinGridIconUrl( $rid );
			$iconPx = self::ICON_PX;
		} else {
			$t = Title::newFromText( $lookup->getItemPageTitle( $id ) );
			$icon = $lookup->getItemTextureWikiUrl( $id );
			$iconPx = self::ICON_PX;
		}
		$link = self::iconOnlyLink( $t, $icon, 'pq-roblox-inv-ico', $iconPx );
		$qtyHtml = '';
		if ( $lookup->isItemStackable( $id ) ) {
			$qtyHtml = Html::element( 'span', [ 'class' => 'pq-roblox-inv-qty' ], '×' . (string)$qty );
		}
		$tierImg = $showTier ? self::tierCornerImgHtml( $lookup, $id, $metadata ) : '';
		return Html::rawElement( 'div', [ 'class' => 'pq-roblox-inv-slot' ], $link . $qtyHtml . $tierImg );
	}

	/**
	 * @param array<string, mixed> $inv
	 */
	private static function inventoryBlobForSlot( array $inv, int $slotZeroBased ): ?array {
		// Game uses 1-based slot keys in JSON ("1","2",…); do not also read 0-based keys or slot 1 duplicates into UI slot 0.
		$oneBased = $slotZeroBased + 1;
		foreach ( [ $oneBased, (string)$oneBased ] as $k ) {
			if ( isset( $inv[$k] ) && is_array( $inv[$k] ) ) {
				return $inv[$k];
			}
		}
		return null;
	}

	private static function graveScalarCell( mixed $v ): string {
		if ( $v === null ) {
			return '—';
		}
		if ( is_scalar( $v ) ) {
			return (string)$v;
		}
		return '—';
	}

	private static function valorWithIconHtml( mixed $valor ): string {
		$num = is_numeric( $valor ) ? (int)$valor : 0;
		$text = number_format( $num );
		$fname = PqRobloxTextureNames::valorIconBase() . '.png';
		$url = PqRobloxWikiFileUrl::forFilename( $fname );
		if ( $url === null ) {
			return $text;
		}
		$urlEsc = htmlspecialchars( $url, ENT_QUOTES );
		return '<span class="pq-roblox-valor-with-ico">'
			. '<img src="' . $urlEsc . '" alt="" title="Valor" width="' . self::VALOR_ICON_PX
			. '" height="' . self::VALOR_ICON_PX . '" class="pq-roblox-valor-ico-img" loading="lazy" />'
			. '<span class="pq-roblox-valor-text">' . $text . '</span>'
			. '</span>';
	}

	private static function iconLabel(
		?string $url,
		string $fallbackText,
		string $imgClass = 'pq-roblox-ico',
		int $size = self::ICON_PX
	): string {
		if ( $url ) {
			return '<span class="pq-roblox-ico-wrap"><img class="' . htmlspecialchars( $imgClass, ENT_QUOTES )
				. '" src="' . htmlspecialchars( $url ) . '" alt="" width="' . $size . '" height="' . $size . '" loading="lazy" /> '
				. htmlspecialchars( $fallbackText ) . '</span>';
		}
		return htmlspecialchars( $fallbackText );
	}

	private static function iconOnlyLink( Title $title, ?string $url, string $imgClass, int $size ): string {
		$attrs = [ 'href' => $title->getFullURL() ];
		$attrs['title'] = $title->getText();
		if ( !$title->exists() ) {
			$attrs['class'] = 'new';
		}
		if ( !$url ) {
			return Html::rawElement( 'span', [ 'class' => 'pq-roblox-icon-empty' ], '—' );
		}
		$img = Html::element( 'img', [
			'src' => $url,
			'alt' => '',
			'width' => $size,
			'height' => $size,
			'class' => $imgClass,
			'loading' => 'lazy',
		] );
		return Html::rawElement( 'a', $attrs, $img );
	}

	private static function makeIconLink(
		Title $title,
		?string $iconUrl,
		string $labelText,
		string $imgClass = 'pq-roblox-ico',
		int $size = self::ICON_PX
	): string {
		$inner = self::iconLabel( $iconUrl, $labelText, $imgClass, $size );
		$attrs = [ 'href' => $title->getFullURL() ];
		if ( !$title->exists() ) {
			$attrs['class'] = 'new';
		}
		return Html::rawElement( 'a', $attrs, $inner );
	}

	/**
	 * @param array<string, mixed> $playerData
	 */
	private static function htmlGraveyard(
		IContextSource $ctx,
		PqRobloxLookupIndex $lookup,
		$lang,
		array $playerData,
		int $gravePage,
		User $target,
		Title $title,
		string $graveSort,
		string $graveDir,
		?int $graveMinValor
	): string {
		$allRaw = PqRobloxPlayerDataParser::getGraveyardList( $playerData );
		$graveSort = in_array( $graveSort, [ 'time', 'level', 'valor' ], true ) ? $graveSort : 'time';
		$graveDir = $graveDir === 'asc' ? 'asc' : 'desc';
		$dirMul = $graveDir === 'asc' ? 1 : -1;

		$rows = [];
		foreach ( $allRaw as $rec ) {
			if ( !is_array( $rec ) ) {
				continue;
			}
			$t = (int)( PqRobloxPlayerDataParser::graveField( $rec, 1 ) ?? 0 );
			$level = (int)( PqRobloxPlayerDataParser::graveField( $rec, 3 ) ?? 0 );
			$valor = (int)( PqRobloxPlayerDataParser::graveField( $rec, 4 ) ?? 0 );
			if ( $graveMinValor !== null && $valor < $graveMinValor ) {
				continue;
			}
			$rows[] = [
				'rec' => $rec,
				'time' => $t,
				'level' => $level,
				'valor' => $valor,
			];
		}

		// Sort the entire graveyard list before slicing for pagination.
		usort( $rows, static function ( $a, $b ) use ( $graveSort, $dirMul ) {
			$cmp = ( (int)$a[$graveSort] ) <=> ( (int)$b[$graveSort] );
			if ( $cmp !== 0 ) {
				return $cmp * $dirMul;
			}
			// Tie-breaker: time, then valor, then level.
			$cmp2 = ( (int)$a['time'] ) <=> ( (int)$b['time'] );
			if ( $cmp2 !== 0 ) {
				return $cmp2 * $dirMul;
			}
			$cmp3 = ( (int)$a['valor'] ) <=> ( (int)$b['valor'] );
			if ( $cmp3 !== 0 ) {
				return $cmp3 * $dirMul;
			}
			$cmp4 = ( (int)$a['level'] ) <=> ( (int)$b['level'] );
			return $cmp4 * $dirMul;
		} );

		$all = array_map( static function ( $r ) { return $r['rec']; }, $rows );
		$per = PqRobloxConfig::getGraveyardPerPage();
		$total = count( $all );
		$offset = max( 0, ( $gravePage - 1 ) * $per );
		$slice = array_slice( $all, $offset, $per );

		$mkSortHref = static function ( string $sortKey ) use ( $title, $graveSort, $graveDir, $graveMinValor ) : string {
			$dir = $graveDir;
			if ( $graveSort === $sortKey ) {
				$dir = $graveDir === 'asc' ? 'desc' : 'asc';
			} else {
				$dir = 'desc';
			}
			$params = [
				'tab' => 'pq-roblox-panel-graveyard',
				'gravepage' => 1,
				'graveSort' => $sortKey,
				'graveDir' => $dir,
			];
			if ( $graveMinValor !== null ) {
				$params['graveMinValor'] = (string)$graveMinValor;
			}
			return $title->getFullURL( $params );
		};

		$timeLabel = $ctx->msg( 'pqroblox-grave-col-time' )->text();
		$causeLabel = $ctx->msg( 'pqroblox-grave-col-cause' )->text();
		$levelLabel = $ctx->msg( 'pqroblox-grave-col-level' )->text();
		$valorLabel = $ctx->msg( 'pqroblox-grave-col-valor' )->text();
		$skinLabel = $ctx->msg( 'pqroblox-grave-col-skin' )->text();
		$eqLabel = $ctx->msg( 'pqroblox-grave-col-equipment' )->text();
		$statsLabel = $ctx->msg( 'pqroblox-grave-col-stats' )->text();

		$sortedArrow = static function ( string $key ) use ( $graveSort, $graveDir ): string {
			if ( $graveSort !== $key ) {
				return '';
			}
			return $graveDir === 'asc' ? ' ▲' : ' ▼';
		};
		$timeLabelSorted = $timeLabel . $sortedArrow( 'time' );
		$levelLabelSorted = $levelLabel . $sortedArrow( 'level' );
		$valorLabelSorted = $valorLabel . $sortedArrow( 'valor' );

		$head = Html::rawElement( 'thead', [], Html::rawElement( 'tr', [],
			Html::rawElement( 'th', [], Html::element( 'a', [ 'href' => $mkSortHref( 'time' ) ], $timeLabelSorted ) )
			. Html::element( 'th', [], $causeLabel )
			. Html::rawElement( 'th', [], Html::element( 'a', [ 'href' => $mkSortHref( 'level' ) ], $levelLabelSorted ) )
			. Html::rawElement( 'th', [], Html::element( 'a', [ 'href' => $mkSortHref( 'valor' ) ], $valorLabelSorted ) )
			. Html::element( 'th', [], $skinLabel )
			. Html::element( 'th', [], $eqLabel )
			. Html::element( 'th', [], $statsLabel )
		) );
		$rows = '';
		foreach ( $slice as $rec ) {
			$rows .= self::graveRow( $lookup, $lang, $rec, $target );
		}
		$pager = self::graveyardPagerHtml( $title, $ctx, $gravePage, $total, $graveSort, $graveDir, $graveMinValor );

		$filterVals = [ 0, 1000, 2500, 5000, 10000 ];
		$curMin = $graveMinValor ?? 0;
		$filterParts = [];
		$valorIcon = self::valorIconOnlyHtml();
		foreach ( $filterVals as $v ) {
			$params = [
				'tab' => 'pq-roblox-panel-graveyard',
				'gravepage' => 1,
				'graveSort' => $graveSort,
				'graveDir' => $graveDir,
				'graveMinValor' => (string)$v,
			];
			$href = $title->getFullURL( $params );
			$label = ( $v === 0 )
				? 'All'
				: ( '≥ ' . $ctx->getLanguage()->formatNum( $v ) );
			if ( $v === $curMin ) {
				$filterParts[] = Html::element(
					'span',
					[ 'class' => 'pq-roblox-tab is-active pq-roblox-filter-tab' ],
					$label
				);
			} else {
				$filterParts[] = Html::rawElement(
					'a',
					[ 'href' => $href, 'class' => 'pq-roblox-tab pq-roblox-filter-tab' ],
					htmlspecialchars( $label, ENT_QUOTES )
				);
			}
		}
		$filterBar = Html::rawElement(
			'div',
			[ 'class' => 'pq-roblox-filterbar' ],
			Html::rawElement(
				'div',
				[ 'class' => 'pq-roblox-filterbar-title' ],
				$valorIcon . ' ' . htmlspecialchars( $ctx->msg( 'pqroblox-profile-col-valor' )->text(), ENT_QUOTES )
			)
			. Html::rawElement( 'div', [ 'class' => 'pq-roblox-tablist pq-roblox-filter-tabs', 'role' => 'tablist' ], implode( '', $filterParts ) )
		);

		if ( $total === 0 ) {
			$rows = Html::rawElement(
				'tr',
				[],
				Html::rawElement(
					'td',
					[ 'colspan' => '7', 'class' => 'pq-roblox-td-tight pq-roblox-muted' ],
					$ctx->msg( 'pqroblox-profile-none' )->text()
				)
			);
		}

		$html = Html::rawElement(
			'div',
			[],
			$filterBar
			. $pager
			. Html::rawElement( 'table', [ 'class' => 'wikitable pq-roblox-grave' ],
				$head . Html::rawElement( 'tbody', [], $rows ) )
			. $pager
		);
		return $html;
	}

	private static function graveyardPagerHtml(
		Title $title,
		IContextSource $ctx,
		int $gravePage,
		int $total,
		string $graveSort,
		string $graveDir,
		?int $graveMinValor
	): string {
		$per = PqRobloxConfig::getGraveyardPerPage();
		$pages = (int)max( 1, ceil( $total / $per ) );
		// Always render both buttons (disabled when at ends) so layout doesn't jump.
		$base = [
			'tab' => 'pq-roblox-panel-graveyard',
			'graveSort' => $graveSort,
			'graveDir' => $graveDir,
			'graveMinValor' => (string)( $graveMinValor ?? 0 ),
		];

		$prevHref = $title->getFullURL( $base + [ 'gravepage' => max( 1, $gravePage - 1 ) ] );
		$nextHref = $title->getFullURL( $base + [ 'gravepage' => min( $pages, $gravePage + 1 ) ] );

		$prevDisabled = ( $gravePage <= 1 );
		$nextDisabled = ( $gravePage >= $pages );

		$prev = Html::element(
			'a',
			[
				'class' => 'pq-roblox-control-link' . ( $prevDisabled ? ' is-disabled' : '' ),
				'href' => $prevDisabled ? '#' : $prevHref,
				'aria-disabled' => $prevDisabled ? 'true' : 'false',
				'tabindex' => $prevDisabled ? '-1' : null,
			],
			$ctx->msg( 'pqroblox-pager-prev' )->text()
		);
		$next = Html::element(
			'a',
			[
				'class' => 'pq-roblox-control-link' . ( $nextDisabled ? ' is-disabled' : '' ),
				'href' => $nextDisabled ? '#' : $nextHref,
				'aria-disabled' => $nextDisabled ? 'true' : 'false',
				'tabindex' => $nextDisabled ? '-1' : null,
			],
			$ctx->msg( 'pqroblox-pager-next' )->text()
		);

		if ( $pages <= 1 ) {
			return Html::rawElement( 'div', [ 'class' => 'pq-roblox-pager-links' ], $prev . $next );
		}
		$mid = Html::element( 'span', [ 'class' => 'pq-roblox-muted pq-roblox-pager-mid' ], 'Page ' . $gravePage . ' / ' . $pages );
		return Html::rawElement( 'div', [ 'class' => 'pq-roblox-pager-links' ], $prev . $mid . $next );
	}

	private static function valorIconOnlyHtml(): string {
		$fname = PqRobloxTextureNames::valorIconBase() . '.png';
		$url = PqRobloxWikiFileUrl::forFilename( $fname );
		if ( $url === null ) {
			return '';
		}
		$urlEsc = htmlspecialchars( $url, ENT_QUOTES );
		return '<img src="' . $urlEsc . '" alt="" title="Valor" width="' . self::VALOR_ICON_PX
			. '" height="' . self::VALOR_ICON_PX . '" class="pq-roblox-valor-ico-img" loading="lazy" />';
	}

	private static function graveRow(
		PqRobloxLookupIndex $lookup,
		$lang,
		mixed $rec,
		User $forTimeUser
	): string {
		if ( !is_array( $rec ) ) {
			return '';
		}
		// List-shaped row: [ time, cause, level, valor, accolades, skinId, primary, secondary, armor, accessory, stats, … ]
		$t = PqRobloxPlayerDataParser::graveField( $rec, 1 );
		$time = is_numeric( $t ) ? (int)$t : 0;
		// Fixed format for consistent sorting + readability.
		$timeS = $time > 0 ? gmdate( 'Y-m-d H:i', $time ) : '—';
		$causeRaw = PqRobloxPlayerDataParser::graveField( $rec, 2 );
		$cause = is_scalar( $causeRaw ) ? trim( (string)$causeRaw ) : '';
		$lvl = PqRobloxPlayerDataParser::graveField( $rec, 3 );
		$valor = PqRobloxPlayerDataParser::graveField( $rec, 4 );
		$skinId = (int)( PqRobloxPlayerDataParser::graveField( $rec, 6 ) ?? 0 );
		$skinT = Title::newFromText( $lookup->getSkinPageTitle( $skinId ) );
		$skinUrl = $skinId > 0 ? $lookup->getSkinGridIconUrl( $skinId ) : null;
		$skinCell = $skinId > 0
			? Html::rawElement( 'td', [ 'class' => 'pq-roblox-td-c pq-roblox-td-tight' ],
				self::iconOnlyLink( $skinT, $skinUrl, 'pq-roblox-grave-ico', self::SKIN_ICON_PX ) )
			: Html::element( 'td', [ 'class' => 'pq-roblox-td-c pq-roblox-td-tight' ], '—' );

		$eqNorms = [];
		foreach ( [ 7, 8, 9, 10 ] as $luaIdx ) {
			$eqNorms[] = self::normalizeEquippedField( PqRobloxPlayerDataParser::graveField( $rec, $luaIdx ) );
		}
		$eqCell = Html::rawElement( 'td', [ 'class' => 'pq-roblox-td-c pq-roblox-td-tight' ],
			self::equipmentIconsFromIds( $lookup, $eqNorms ) );

		$statsRaw = PqRobloxPlayerDataParser::graveField( $rec, 11 );
		$statsCell = Html::rawElement( 'td', [ 'class' => 'pq-roblox-td-tight pq-roblox-td-stats' ],
			self::graveStatsBlockHtml( $lookup, $statsRaw ) );

		return Html::rawElement( 'tr', [],
			Html::element( 'td', [ 'class' => 'pq-roblox-td-tight' ], $timeS )
			. Html::element( 'td', [ 'class' => 'pq-roblox-td-tight' ], $cause !== '' ? $cause : '—' )
			. Html::element( 'td', [ 'class' => 'pq-roblox-td-c pq-roblox-td-tight' ], self::graveScalarCell( $lvl ) )
			. Html::rawElement(
				'td',
				[ 'class' => 'pq-roblox-td-c pq-roblox-td-tight' ],
				self::valorWithIconHtml( (int)$valor )
			)
			. $skinCell
			. $eqCell
			. $statsCell
		);
	}

	/**
	 * @param mixed $statsRaw List of 8 numbers: ATK, DEF, VIT, WIS, HP, MP, DEX, SPD
	 */
	private static function graveStatsBlockHtml( PqRobloxLookupIndex $lookup, mixed $statsRaw ): string {
		if ( !is_array( $statsRaw ) ) {
			return Html::element( 'span', [ 'class' => 'pq-roblox-muted' ], '—' );
		}
		$list = array_values( $statsRaw );
		$stats = [];
		foreach ( self::GRAVE_STAT_ORDER as $i => $key ) {
			if ( !array_key_exists( $i, $list ) ) {
				continue;
			}
			$v = $list[$i];
			if ( is_numeric( $v ) ) {
				$stats[$key] = $v;
			}
		}
		if ( $stats === [] ) {
			return Html::element( 'span', [ 'class' => 'pq-roblox-muted' ], '—' );
		}
		$keys = self::GRAVE_STAT_ORDER;
		$leftCol = '';
		$rightCol = '';
		for ( $i = 0; $i < 4; $i++ ) {
			$leftCol .= self::statLineHtml( $lookup, $stats, $keys[$i] );
			$rightCol .= self::statLineHtml( $lookup, $stats, $keys[$i + 4] );
		}
		return Html::rawElement( 'div', [ 'class' => 'pq-roblox-stats-block pq-roblox-grave-stats' ],
			Html::rawElement( 'div', [ 'class' => 'pq-roblox-stats-col' ], $leftCol )
			. Html::rawElement( 'div', [ 'class' => 'pq-roblox-stats-col' ], $rightCol )
		);
	}

	/**
	 * @param array<string, mixed> $playerData
	 */
	private static function htmlSkinGrid(
		IContextSource $ctx,
		PqRobloxLookupIndex $lookup,
		array $playerData
	): string {
		$owned = PqRobloxPlayerDataParser::getSkinsQuantityMap( $playerData );
		$ids = $lookup->getAllSkinIdsOrdered();
		if ( $ids === [] ) {
			return Html::element( 'p', [ 'class' => 'pq-roblox-muted' ], $ctx->msg( 'pqroblox-profile-no-datadump-skins' )->text() );
		}

		$lang = $ctx->getLanguage();
		$html = '';
		foreach ( $ids as $sid ) {
			$qty = $owned[(string)$sid] ?? $owned[(string)(int)$sid] ?? 0;
			$has = $qty > 0;
			$t = Title::newFromText( $lookup->getSkinPageTitle( $sid ) );
			$url = $lookup->getSkinGridIconUrl( $sid );
			$link = self::iconOnlyLink( $t, $url, 'pq-roblox-inv-ico', self::SKIN_ICON_PX );
			$qtyHtml = '';
			if ( $has ) {
				$qtyHtml = Html::element( 'span', [ 'class' => 'pq-roblox-inv-qty' ],
					'×' . $lang->formatNum( $qty ) );
			}
			$cls = 'pq-roblox-skin-cell' . ( $has ? '' : ' pq-roblox-skin-locked' );
			$slot = Html::rawElement( 'div', [ 'class' => 'pq-roblox-inv-slot' ], $link . $qtyHtml );
			$html .= Html::rawElement( 'div', [ 'class' => $cls ], $slot );
		}
		return Html::rawElement( 'div', [ 'class' => 'pq-roblox-skin-grid' ], $html );
	}

	/**
	 * @param array<string, mixed> $playerData
	 */
	private static function htmlVault(
		IContextSource $ctx,
		PqRobloxLookupIndex $lookup,
		array $playerData,
		Title $title,
		int $vaultPage,
		bool $vaultHideEmpty,
		string $vaultTier,
		string $vaultType,
		string $vaultQ
	): string {
		$slots = PqRobloxPlayerDataParser::getVaultSlots( $playerData );
		$max = max( 1, (int)( $playerData['totalVaultSlots'] ?? 8 ) );
		$vaultPage = max( 1, $vaultPage );
		$perPage = 64; // 8 columns × 8 rows

		$q = strtolower( trim( $vaultQ ) );
		$typeWant = strtolower( trim( $vaultType ) );

		$entries = [];
		for ( $i = 1; $i <= $max; $i++ ) {
			$blob = $slots[$i] ?? $slots[(string)$i] ?? null;
			$norm = is_array( $blob ) ? PqRobloxPlayerDataParser::normalizeItemBlob( $blob ) : null;
			$isEmpty = ( $norm === null || (int)$norm['id'] === 0 );
			if ( $vaultHideEmpty && $isEmpty ) {
				continue;
			}

			$id = $isEmpty ? 0 : (int)$norm['id'];
			$qty = $isEmpty ? 0 : (int)$norm['quantity'];
			$meta = $isEmpty ? null : ( $norm['metadata'] ?? null );

			// Filters that require a non-empty slot.
			if ( !$isEmpty ) {
				// Tier filter (uses DropTierType; Skin items treated as tier 6).
				$tier = $lookup->isSkinItem( $id ) ? 6 : $lookup->getItemDropTierType( $id );
				if ( $vaultTier === 'legendary' && $tier < 5 ) {
					continue;
				}
				if ( $vaultTier !== '' && $vaultTier !== 'legendary' && $tier !== (int)$vaultTier ) {
					continue;
				}

				// Type filter (best-effort from TypeHierarchy, tolerant of casing/plurals).
				if ( $typeWant !== '' ) {
					$row = $lookup->getItemRow( $id );
					$hier = is_array( $row ) ? ( $row['TypeHierarchy'] ?? $row['typeHierarchy'] ?? null ) : null;
					$top = '';
					if ( $lookup->isSkinItem( $id ) ) {
						$top = 'skin';
					} else {
						// Hierarchy can be array-of-strings or a single string; sometimes values are plural ("Weapons").
						$first = '';
						if ( is_array( $hier ) && $hier !== [] ) {
							$first = strtolower( trim( (string)( $hier[0] ?? '' ) ) );
						} elseif ( is_string( $hier ) ) {
							$first = strtolower( trim( $hier ) );
						}
						if ( $first !== '' ) {
							if ( str_contains( $first, 'weapon' ) ) {
								$top = 'weapon';
							} elseif ( str_contains( $first, 'armor' ) ) {
								$top = 'armor';
							} elseif ( str_contains( $first, 'accessor' ) ) {
								$top = 'accessory';
							} elseif ( str_contains( $first, 'consum' ) ) {
								$top = 'consumable';
							}
						}
					}
					if ( $top !== $typeWant ) {
						continue;
					}
				}

				// Name search (item name or skin name for Skin items w/ rid).
				if ( $q !== '' ) {
					$name = '';
					$rid = self::metadataSkinRid( $meta );
					if ( $rid !== null && $lookup->isSkinItem( $id ) ) {
						$skinRow = $lookup->getSkinRow( $rid );
						$name = is_array( $skinRow ) ? (string)( $skinRow['Name'] ?? '' ) : '';
					} else {
						$row = $lookup->getItemRow( $id );
						$name = is_array( $row ) ? (string)( $row['Name'] ?? '' ) : '';
					}
					if ( strpos( strtolower( $name ), $q ) === false ) {
						continue;
					}
				}
			} else {
				// If any non-empty-only filters are set, hide empties automatically.
				if ( $vaultTier !== '' || $typeWant !== '' || $q !== '' ) {
					continue;
				}
			}

			$entries[] = [ 'id' => $id, 'qty' => $qty, 'meta' => $meta ];
		}

		$total = count( $entries );
		$pages = (int)max( 1, ceil( $total / $perPage ) );
		$vaultPage = min( $vaultPage, $pages );
		$offset = ( $vaultPage - 1 ) * $perPage;
		$slice = array_slice( $entries, $offset, $perPage );

		// Filter bar (simple, URL-driven).
		$baseParams = [
			'tab' => 'pq-roblox-panel-vault',
			'vaultTier' => $vaultTier,
			'vaultType' => $vaultType,
			'vaultQ' => $vaultQ,
		];
		if ( $vaultHideEmpty ) {
			$baseParams['vaultHideEmpty'] = '1';
		}

		$tierOpts = [
			'' => 'All tiers',
			'legendary' => 'Legendary+',
			'1' => 'Tier 1',
			'2' => 'Tier 2',
			'3' => 'Tier 3',
			'4' => 'Tier 4',
			'5' => 'Tier 5',
			'6' => 'Tier 6',
		];
		$typeOpts = [
			'' => 'All types',
			'weapon' => 'Weapon',
			'armor' => 'Armor',
			'accessory' => 'Accessory',
			'consumable' => 'Consumable',
			'skin' => 'Skin',
		];

		$filterForm = Html::rawElement(
			'form',
			[
				'method' => 'get',
				'action' => $title->getLocalURL(),
				'class' => 'pq-roblox-vault-filters',
			],
			Html::hidden( 'tab', 'pq-roblox-panel-vault' )
			. Html::hidden( 'vaultpage', '1' )
			. Html::element( 'input', [
				'type' => 'text',
				'name' => 'vaultQ',
				'value' => $vaultQ,
				'placeholder' => 'Search…',
				'class' => 'pq-roblox-control-input',
			] )
			. Html::rawElement(
				'select',
				[ 'name' => 'vaultTier', 'class' => 'pq-roblox-control-input' ],
				implode( '', array_map( static function ( $k ) use ( $tierOpts, $vaultTier ) {
					return Html::element( 'option', [ 'value' => (string)$k, 'selected' => (string)$k === (string)$vaultTier ? 'selected' : null ], $tierOpts[$k] );
				}, array_keys( $tierOpts ) ) )
			)
			. Html::rawElement(
				'select',
				[ 'name' => 'vaultType', 'class' => 'pq-roblox-control-input' ],
				implode( '', array_map( static function ( $k ) use ( $typeOpts, $vaultType ) {
					return Html::element( 'option', [ 'value' => (string)$k, 'selected' => (string)$k === (string)$vaultType ? 'selected' : null ], $typeOpts[$k] );
				}, array_keys( $typeOpts ) ) )
			)
			. Html::rawElement(
				'label',
				[],
				Html::element( 'input', [
					'type' => 'checkbox',
					'name' => 'vaultHideEmpty',
					'value' => '1',
					'checked' => $vaultHideEmpty ? 'checked' : null,
				] ) . ' Hide empty'
			)
			. Html::element( 'button', [ 'type' => 'submit', 'class' => 'pq-roblox-control-btn' ], 'Apply' )
			. Html::element( 'span', [ 'class' => 'pq-roblox-muted' ], '  ' . $ctx->getLanguage()->formatNum( $total ) . ' slots' )
		);

		// Pager (always show prev/next; disable at ends for stable layout).
		$prevDisabled = ( $vaultPage <= 1 );
		$nextDisabled = ( $vaultPage >= $pages );
		$prevHref = $title->getFullURL( $baseParams + [ 'vaultpage' => max( 1, $vaultPage - 1 ) ] );
		$nextHref = $title->getFullURL( $baseParams + [ 'vaultpage' => min( $pages, $vaultPage + 1 ) ] );
		$prev = Html::element(
			'a',
			[
				'class' => 'pq-roblox-control-link' . ( $prevDisabled ? ' is-disabled' : '' ),
				'href' => $prevDisabled ? '#' : $prevHref,
				'aria-disabled' => $prevDisabled ? 'true' : 'false',
				'tabindex' => $prevDisabled ? '-1' : null,
			],
			'Prev'
		);
		$next = Html::element(
			'a',
			[
				'class' => 'pq-roblox-control-link' . ( $nextDisabled ? ' is-disabled' : '' ),
				'href' => $nextDisabled ? '#' : $nextHref,
				'aria-disabled' => $nextDisabled ? 'true' : 'false',
				'tabindex' => $nextDisabled ? '-1' : null,
			],
			'Next'
		);
		$mid = Html::element( 'span', [ 'class' => 'pq-roblox-muted pq-roblox-pager-mid' ], 'Page ' . $vaultPage . ' / ' . $pages );
		$pager = Html::rawElement( 'div', [ 'class' => 'pq-roblox-pager-links' ], $prev . $mid . $next );

		// Render slice into a fixed 8-column grid.
		$html = '';
		foreach ( $slice as $e ) {
			if ( (int)$e['id'] === 0 ) {
				$html .= Html::rawElement( 'div', [ 'class' => 'pq-roblox-inv-slot pq-roblox-inv-slot-empty' ], '' );
				continue;
			}
			$html .= self::vaultSlotHtml( $lookup, (int)$e['id'], (int)$e['qty'], $e['meta'] ?? null );
		}
		return Html::rawElement( 'div', [], $filterForm . $pager
			. Html::rawElement( 'div', [ 'class' => 'pq-roblox-vault-grid' ], $html )
			. $pager
		);
	}

	private static function vaultSlotHtml( PqRobloxLookupIndex $lookup, int $id, int $qty, $metadata = null ): string {
		return self::itemSlotFilledHtml( $lookup, $id, $qty, true, $metadata );
	}
}
