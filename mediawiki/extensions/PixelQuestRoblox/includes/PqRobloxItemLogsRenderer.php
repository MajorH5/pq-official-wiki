<?php

namespace PixelQuestRoblox;

use MediaWiki\Context\IContextSource;
use MediaWiki\Html\Html;
use MediaWiki\Title\Title;
use PixelQuestRoblox\Service\PqRobloxDataStoreClient;
use PixelQuestRoblox\Service\PqRobloxLookupIndex;

final class PqRobloxItemLogsRenderer {

	private const MAX_SLOT_LOGS = 10000;
	private const MAX_TRADE_LOGS = 2000;
	private const LOGS_PER_PAGE = 50;
	private const TRACE_MAX_PLAYERS = 20;

	private const ACTION_TEXT = [
		'pickup' => 'picked up',
		'drop' => 'dropped',
		'deposit' => 'deposited',
		'withdraw' => 'withdrew',
		'consume' => 'used',
		'delete' => 'deleted',
		'receive' => 'received',
		'give' => 'gave',
		'trade' => 'traded',
		'droppedPickup' => 'had a dropped item picked up',
	];

	private const LOCATION_TEXT = [
		'inventory' => 'inventory',
		'equipment' => 'equipment',
		'vault' => 'vault',
		'giftBox' => 'gift box',
		'guildVault' => 'guild vault',
		'guildGiftBox' => 'guild gift box',
		'loot' => 'loot',
		'world' => 'world',
		'trade' => 'trade',
		'task' => 'task',
		'death' => 'death',
		'system' => 'system',
	];

	/**
	 * @param array<string, mixed>|null $itemLogData
	 * @param array{page:int,type:string,q:string,traceUid:string} $params
	 */
	public static function renderPanel(
		IContextSource $ctx,
		PqRobloxLookupIndex $lookup,
		Title $title,
		int $robloxUserId,
		?array $itemLogData,
		array $params
	): string {
		$data = self::normalizeLogsRoot( $itemLogData );
		$page = max( 1, (int)( $params['page'] ?? 1 ) );
		$type = (string)( $params['type'] ?? 'all' );
		if ( !in_array( $type, [ 'all', 'slot', 'trade' ], true ) ) {
			$type = 'all';
		}
		$q = trim( (string)( $params['q'] ?? '' ) );
		$traceUid = trim( (string)( $params['traceUid'] ?? '' ) );

		$rows = self::collectRows( $data, $type, true );
		if ( $q !== '' ) {
			$needle = strtolower( $q );
			$rows = array_values( array_filter(
				$rows,
				static fn ( array $row ): bool => str_contains( self::rowSearchText( $row ), $needle )
			) );
		}

		$total = count( $rows );
		$pages = (int)max( 1, ceil( $total / self::LOGS_PER_PAGE ) );
		$page = min( $page, $pages );
		$slice = array_slice( $rows, ( $page - 1 ) * self::LOGS_PER_PAGE, self::LOGS_PER_PAGE );

		$form = self::filterFormHtml( $title, $type, $q, $traceUid, $total );
		$pager = self::pagerHtml( $title, $page, $pages, $type, $q, $traceUid );
		$table = self::logsTableHtml( $ctx, $lookup, $slice );
		$trace = $traceUid !== ''
			? self::traceHtml( $ctx, $lookup, $robloxUserId, $data, $traceUid )
			: '';

		$summary = Html::rawElement(
			'p',
			[ 'class' => 'pq-roblox-muted' ],
			'Showing ' . htmlspecialchars( $ctx->getLanguage()->formatNum( $total ), ENT_QUOTES )
				. ' matching log entries. Slot logs and trade logs are only visible to admins.'
		);

		return Html::rawElement( 'div', [ 'class' => 'pq-roblox-logs-panel' ],
			$form . $summary . $trace . $pager . $table . $pager );
	}

	/**
	 * @param array<string, mixed>|null $raw
	 * @return array<string, mixed>
	 */
	private static function normalizeLogsRoot( ?array $raw ): array {
		if ( $raw === null ) {
			return [];
		}
		if ( isset( $raw['Data'] ) && is_array( $raw['Data'] ) ) {
			return $raw['Data'];
		}
		if ( isset( $raw['value'] ) && is_array( $raw['value'] ) ) {
			$v = $raw['value'];
			return isset( $v['Data'] ) && is_array( $v['Data'] ) ? $v['Data'] : $v;
		}
		return $raw;
	}

	/**
	 * @param array<string, mixed> $data
	 * @return list<array{type:string,entry:array<string,mixed>,time:int}>
	 */
	private static function collectRows( array $data, string $type, bool $reverse ): array {
		$rows = [];
		if ( $type === 'all' || $type === 'slot' ) {
			foreach ( self::orderedEntries( $data['slotLogs'] ?? null, self::MAX_SLOT_LOGS, $reverse ) as $entry ) {
				$rows[] = [ 'type' => 'slot', 'entry' => $entry, 'time' => (int)( $entry['t'] ?? 0 ) ];
			}
		}
		if ( $type === 'all' || $type === 'trade' ) {
			foreach ( self::orderedEntries( $data['tradeLogs'] ?? null, self::MAX_TRADE_LOGS, $reverse ) as $entry ) {
				$rows[] = [ 'type' => 'trade', 'entry' => $entry, 'time' => (int)( $entry['t'] ?? 0 ) ];
			}
		}
		usort( $rows, static function ( array $a, array $b ) use ( $reverse ): int {
			$cmp = ( (int)$a['time'] ) <=> ( (int)$b['time'] );
			if ( $cmp === 0 ) {
				$cmp = strcmp( (string)$a['type'], (string)$b['type'] );
			}
			return $reverse ? -$cmp : $cmp;
		} );
		return $rows;
	}

	/**
	 * @return list<array<string, mixed>>
	 */
	private static function orderedEntries( mixed $log, int $max, bool $reverse ): array {
		if ( !is_array( $log ) || !isset( $log['entries'] ) || !is_array( $log['entries'] ) ) {
			return [];
		}
		$entries = array_values( array_filter( $log['entries'], 'is_array' ) );
		$count = count( $entries );
		if ( $count === 0 ) {
			return [];
		}
		if ( $count >= $max ) {
			$head = max( 1, min( $max, (int)( $log['headIndex'] ?? 1 ) ) ) - 1;
			$entries = array_merge( array_slice( $entries, $head ), array_slice( $entries, 0, $head ) );
		}
		if ( $reverse ) {
			$entries = array_reverse( $entries );
		}
		return $entries;
	}

	private static function filterFormHtml( Title $title, string $type, string $q, string $traceUid, int $total ): string {
		$options = [
			'all' => 'All logs',
			'slot' => 'Slot logs',
			'trade' => 'Trade logs',
		];
		$typeOptions = '';
		foreach ( $options as $value => $label ) {
			$typeOptions .= Html::element( 'option', [
				'value' => $value,
				'selected' => $value === $type ? 'selected' : null,
			], $label );
		}
		return Html::rawElement(
			'form',
			[
				'method' => 'get',
				'action' => $title->getLocalURL(),
				'class' => 'pq-roblox-log-filters',
			],
			Html::hidden( 'tab', 'pq-roblox-panel-logs' )
			. Html::hidden( 'logspage', '1' )
			. Html::rawElement( 'select', [ 'name' => 'logsType', 'class' => 'pq-roblox-control-input' ], $typeOptions )
			. Html::element( 'input', [
				'type' => 'text',
				'name' => 'logsQ',
				'value' => $q,
				'placeholder' => 'Search items, actions, players, UID...',
				'class' => 'pq-roblox-control-input pq-roblox-log-search',
			] )
			. Html::element( 'input', [
				'type' => 'text',
				'name' => 'traceUid',
				'value' => $traceUid,
				'placeholder' => 'Trace item UID',
				'class' => 'pq-roblox-control-input pq-roblox-log-trace',
			] )
			. Html::element( 'button', [ 'type' => 'submit', 'class' => 'pq-roblox-control-btn' ], 'Apply' )
			. Html::element( 'span', [ 'class' => 'pq-roblox-muted' ], number_format( $total ) . ' results' )
		);
	}

	private static function pagerHtml( Title $title, int $page, int $pages, string $type, string $q, string $traceUid ): string {
		$base = [
			'tab' => 'pq-roblox-panel-logs',
			'logsType' => $type,
			'logsQ' => $q,
			'traceUid' => $traceUid,
		];
		$prevDisabled = $page <= 1;
		$nextDisabled = $page >= $pages;
		$prev = Html::element( 'a', [
			'class' => 'pq-roblox-control-link' . ( $prevDisabled ? ' is-disabled' : '' ),
			'href' => $prevDisabled ? '#' : $title->getFullURL( $base + [ 'logspage' => max( 1, $page - 1 ) ] ),
			'aria-disabled' => $prevDisabled ? 'true' : 'false',
			'tabindex' => $prevDisabled ? '-1' : null,
		], 'Prev' );
		$next = Html::element( 'a', [
			'class' => 'pq-roblox-control-link' . ( $nextDisabled ? ' is-disabled' : '' ),
			'href' => $nextDisabled ? '#' : $title->getFullURL( $base + [ 'logspage' => min( $pages, $page + 1 ) ] ),
			'aria-disabled' => $nextDisabled ? 'true' : 'false',
			'tabindex' => $nextDisabled ? '-1' : null,
		], 'Next' );
		return Html::rawElement( 'div', [ 'class' => 'pq-roblox-pager-links' ],
			$prev . Html::element( 'span', [ 'class' => 'pq-roblox-muted pq-roblox-pager-mid' ], "Page $page / $pages" ) . $next );
	}

	/**
	 * @param list<array{type:string,entry:array<string,mixed>,time:int}> $rows
	 */
	private static function logsTableHtml( IContextSource $ctx, PqRobloxLookupIndex $lookup, array $rows ): string {
		$body = '';
		if ( $rows === [] ) {
			$body = Html::rawElement( 'tr', [], Html::element( 'td', [
				'colspan' => '4',
				'class' => 'pq-roblox-muted',
			], 'No log entries found.' ) );
		}
		foreach ( $rows as $row ) {
			$entry = $row['entry'];
			$time = (int)$row['time'];
			$body .= Html::rawElement( 'tr', [],
				Html::element( 'td', [ 'class' => 'pq-roblox-log-time' ], $time > 0 ? gmdate( 'Y-m-d H:i:s', $time ) . ' UTC' : 'unknown' )
				. Html::element( 'td', [ 'class' => 'pq-roblox-log-type' ], $row['type'] === 'trade' ? 'Trade' : 'Slot' )
				. Html::element( 'td', [ 'class' => 'pq-roblox-log-action' ], (string)( $entry['a'] ?? 'log' ) )
				. Html::rawElement( 'td', [ 'class' => 'pq-roblox-log-detail' ], self::entryHtml( $lookup, $entry, $row['type'] ) )
			);
		}
		$head = Html::rawElement( 'thead', [], Html::rawElement( 'tr', [],
			Html::element( 'th', [], 'Time' )
			. Html::element( 'th', [], 'Log' )
			. Html::element( 'th', [], 'Action' )
			. Html::element( 'th', [], 'Details' )
		) );
		return Html::rawElement( 'div', [ 'class' => 'pq-roblox-log-table-wrap' ],
			Html::rawElement( 'table', [ 'class' => 'wikitable pq-roblox-log-table' ], $head . Html::rawElement( 'tbody', [], $body ) ) );
	}

	private static function entryHtml( PqRobloxLookupIndex $lookup, array $entry, string $type ): string {
		if ( $type === 'trade' || (string)( $entry['a'] ?? '' ) === 'trade' ) {
			$p1 = self::playerLink( $entry['p1'] ?? null, 'Player 1' );
			$p2 = self::playerLink( $entry['p2'] ?? null, 'Player 2' );
			return 'Trade: ' . $p1 . ' gave ' . self::itemListHtml( $lookup, $entry['from1'] ?? null )
				. ' to ' . $p2 . '; ' . $p2 . ' gave ' . self::itemListHtml( $lookup, $entry['from2'] ?? null )
				. ' to ' . $p1;
		}

		$actionKey = (string)( $entry['a'] ?? 'moved' );
		$item = is_array( $entry['item'] ?? null ) ? $entry['item'] : null;
		if ( $actionKey === 'droppedPickup' ) {
			return 'Player had dropped ' . self::itemHtml( $lookup, $item )
				. ' picked up by ' . self::playerLink( $entry['pickedUpBy'] ?? null, 'another player' )
				. self::locationPhrase( ' from ', $entry['from'] ?? null );
		}

		$player = self::playerLink( $entry['player'] ?? null, 'Player' );
		$action = self::ACTION_TEXT[$actionKey] ?? $actionKey;
		$detail = $player . ' ' . htmlspecialchars( $action, ENT_QUOTES ) . ' ' . self::itemHtml( $lookup, $item )
			. self::locationPhrase( ' from ', $entry['from'] ?? null )
			. self::locationPhrase( ' to ', $entry['to'] ?? null );
		if ( isset( $entry['other'] ) ) {
			$detail .= ' with ' . self::playerLink( $entry['other'], 'another player' );
		}
		if ( isset( $entry['droppedBy'] ) ) {
			$detail .= ' (dropped by ' . self::playerLink( $entry['droppedBy'], 'unknown' ) . ')';
		} elseif ( isset( $entry['reason'] ) && is_scalar( $entry['reason'] ) ) {
			$detail .= ' (' . htmlspecialchars( (string)$entry['reason'], ENT_QUOTES ) . ')';
		}
		return $detail;
	}

	private static function rowSearchText( array $row ): string {
		$entry = $row['entry'] ?? [];
		$json = json_encode( $entry );
		return strtolower( (string)$row['type'] . ' ' . ( $json === false ? '' : $json ) );
	}

	private static function itemListHtml( PqRobloxLookupIndex $lookup, mixed $items ): string {
		if ( !is_array( $items ) || $items === [] ) {
			return 'nothing';
		}
		$parts = [];
		foreach ( $items as $item ) {
			$parts[] = self::itemHtml( $lookup, is_array( $item ) ? $item : null );
		}
		return implode( ', ', $parts );
	}

	private static function itemHtml( PqRobloxLookupIndex $lookup, ?array $item ): string {
		if ( $item === null ) {
			return Html::element( 'span', [ 'class' => 'pq-roblox-muted' ], 'None' );
		}
		$id = (int)( $item['id'] ?? $item['Id'] ?? 0 );
		$qty = (int)( $item['quantity'] ?? $item['Quantity'] ?? 1 );
		$name = (string)( $item['name'] ?? $item['Name'] ?? ( $id > 0 ? 'Item ' . $id : 'Item' ) );
		$metadata = $item['metadata'] ?? $item['Metadata'] ?? null;
		$title = null;
		$icon = null;
		$rid = self::metadataSkinRid( $metadata );
		if ( $id > 0 && $rid !== null && $lookup->isSkinItem( $id ) ) {
			$title = Title::newFromText( $lookup->getSkinPageTitle( $rid ) );
			$icon = $lookup->getSkinGridIconUrl( $rid );
			$skinRow = $lookup->getSkinRow( $rid );
			if ( is_array( $skinRow ) && isset( $skinRow['Name'] ) ) {
				$name = (string)$skinRow['Name'];
			}
		} elseif ( $id > 0 ) {
			$title = Title::newFromText( $lookup->getItemPageTitle( $id ) );
			$icon = $lookup->getItemTextureWikiUrl( $id );
		}

		$label = ( $qty > 1 ? $qty . 'x ' : '' ) . $name;
		$labelHtml = htmlspecialchars( $label, ENT_QUOTES );
		if ( $title instanceof Title ) {
			$labelHtml = Html::element( 'a', [ 'href' => $title->getFullURL() ], $label );
		}
		$iconHtml = '';
		if ( $icon !== null && $icon !== '' && $title instanceof Title ) {
			$iconHtml = Html::rawElement( 'a', [ 'href' => $title->getFullURL(), 'class' => 'pq-roblox-log-item-icon' ],
				Html::element( 'img', [
					'src' => $icon,
					'alt' => '',
					'width' => 24,
					'height' => 24,
					'loading' => 'lazy',
				] ) );
		}
		$uid = self::itemUid( $item );
		$uidHtml = $uid !== '' ? ' ' . Html::element( 'code', [ 'class' => 'pq-roblox-log-uid' ], $uid ) : '';
		return Html::rawElement( 'span', [ 'class' => 'pq-roblox-log-item' ], $iconHtml . $labelHtml . $uidHtml );
	}

	private static function playerLink( mixed $player, string $fallback ): string {
		if ( !is_array( $player ) ) {
			return htmlspecialchars( $fallback, ENT_QUOTES );
		}
		$userId = (int)( $player['userId'] ?? $player['UserId'] ?? 0 );
		$name = (string)( $player['name'] ?? $player['Name'] ?? ( $userId > 0 ? (string)$userId : $fallback ) );
		if ( $userId <= 0 ) {
			return htmlspecialchars( $name, ENT_QUOTES );
		}
		$title = Title::makeTitle( \NS_SPECIAL, 'PQProfile/' . $userId );
		return Html::element( 'a', [ 'href' => $title->getFullURL() ], $name );
	}

	private static function locationPhrase( string $prefix, mixed $location ): string {
		if ( !is_array( $location ) ) {
			return '';
		}
		return htmlspecialchars( $prefix, ENT_QUOTES ) . self::locationHtml( $location );
	}

	private static function locationHtml( array $location ): string {
		$kind = (string)( $location['kind'] ?? $location['Kind'] ?? 'unknown' );
		$text = htmlspecialchars( self::LOCATION_TEXT[$kind] ?? $kind, ENT_QUOTES );
		if ( isset( $location['slot'] ) ) {
			$text .= ' slot ' . htmlspecialchars( (string)$location['slot'], ENT_QUOTES );
		}
		if ( isset( $location['objectId'] ) ) {
			$text .= ' obj ' . htmlspecialchars( (string)$location['objectId'], ENT_QUOTES );
		}
		if ( isset( $location['characterId'] ) ) {
			$text .= ' char ' . Html::element(
				'code',
				[ 'class' => 'pq-roblox-log-uid' ],
				(string)$location['characterId']
			);
		}
		return $text;
	}

	private static function metadataSkinRid( mixed $metadata ): ?int {
		if ( !is_array( $metadata ) ) {
			return null;
		}
		foreach ( [ 'rid', 'Rid', 'RID' ] as $key ) {
			if ( isset( $metadata[$key] ) && is_numeric( $metadata[$key] ) ) {
				$rid = (int)$metadata[$key];
				return $rid > 0 ? $rid : null;
			}
		}
		return null;
	}

	private static function itemUid( array $item ): string {
		$uid = $item['uid'] ?? $item['UID'] ?? null;
		if ( is_scalar( $uid ) && (string)$uid !== '' ) {
			return (string)$uid;
		}
		$metadata = $item['metadata'] ?? $item['Metadata'] ?? null;
		if ( is_array( $metadata ) ) {
			$uid = $metadata['uid'] ?? $metadata['UID'] ?? null;
			if ( is_scalar( $uid ) && (string)$uid !== '' ) {
				return (string)$uid;
			}
		}
		return '';
	}

	private static function traceHtml(
		IContextSource $ctx,
		PqRobloxLookupIndex $lookup,
		int $rootRobloxUserId,
		array $rootData,
		string $uid
	): string {
		$trace = self::traceUidAcrossPlayers( $rootRobloxUserId, $rootData, $uid );
		$rows = '';
		foreach ( $trace['rows'] as $row ) {
			$entry = $row['row']['entry'];
			$rows .= Html::rawElement( 'tr', [],
				Html::rawElement( 'td', [], self::playerLink( [ 'userId' => $row['playerId'], 'name' => $row['playerName'] ], (string)$row['playerId'] ) )
				. Html::element( 'td', [], (int)$row['row']['time'] > 0 ? gmdate( 'Y-m-d H:i:s', (int)$row['row']['time'] ) . ' UTC' : 'unknown' )
				. Html::element( 'td', [], (string)( $entry['a'] ?? $row['row']['type'] ) )
				. Html::rawElement( 'td', [], self::entryHtml( $lookup, $entry, $row['row']['type'] ) )
			);
		}
		if ( $rows === '' ) {
			$rows = Html::rawElement( 'tr', [], Html::element( 'td', [
				'colspan' => '4',
				'class' => 'pq-roblox-muted',
			], 'No entries found for that UID.' ) );
		}
		$final = Html::rawElement( 'p', [ 'class' => 'pq-roblox-log-trace-final' ],
			'Trace result: ' . htmlspecialchars( $trace['final'], ENT_QUOTES ) );
		$table = Html::rawElement( 'table', [ 'class' => 'wikitable pq-roblox-log-table pq-roblox-log-trace-table' ],
			Html::rawElement( 'thead', [], Html::rawElement( 'tr', [],
				Html::element( 'th', [], 'Player' )
				. Html::element( 'th', [], 'Time' )
				. Html::element( 'th', [], 'Action' )
				. Html::element( 'th', [], 'Details' )
			) )
			. Html::rawElement( 'tbody', [], $rows )
		);
		return Html::rawElement( 'div', [ 'class' => 'pq-roblox-log-trace-box' ],
			Html::element( 'h3', [], 'Item UID trace' )
			. Html::element( 'p', [ 'class' => 'pq-roblox-muted' ], $uid )
			. $final
			. $table
		);
	}

	/**
	 * @return array{rows:list<array{playerId:int,playerName:string,row:array}>,final:string}
	 */
	private static function traceUidAcrossPlayers( int $rootRobloxUserId, array $rootData, string $uid ): array {
		$visited = [];
		$currentId = $rootRobloxUserId;
		$currentData = $rootData;
		$out = [];
		$final = 'No owner found.';

		for ( $i = 0; $i < self::TRACE_MAX_PLAYERS; $i++ ) {
			if ( $currentId <= 0 || isset( $visited[$currentId] ) ) {
				$final = 'Stopped to avoid a cyclic trace.';
				break;
			}
			$visited[$currentId] = true;
			$matches = array_values( array_filter(
				self::collectRows( $currentData, 'all', false ),
				static fn ( array $row ): bool => self::rowContainsUid( $row, $uid )
			) );
			if ( $matches === [] ) {
				$final = 'No more entries for Roblox user ' . $currentId . '.';
				break;
			}

			$playerName = self::bestPlayerNameFromRows( $matches, $currentId );
			foreach ( $matches as $match ) {
				$out[] = [ 'playerId' => $currentId, 'playerName' => $playerName, 'row' => $match ];
			}

			$last = $matches[count( $matches ) - 1];
			$owner = self::ownerAfterRow( $last, $uid, $currentId, $playerName );
			$final = $owner['label'];
			if ( ( $owner['kind'] ?? '' ) !== 'player' ) {
				break;
			}
			$nextId = (int)( $owner['userId'] ?? 0 );
			if ( $nextId <= 0 || $nextId === $currentId || isset( $visited[$nextId] ) ) {
				break;
			}
			$nextData = PqRobloxDataStoreClient::getItemLogDataForRobloxUser( $nextId, false );
			if ( !is_array( $nextData ) ) {
				$final = 'Transferred to Roblox user ' . $nextId . ', but their item logs could not be loaded.';
				break;
			}
			$currentId = $nextId;
			$currentData = self::normalizeLogsRoot( $nextData );
		}

		return [ 'rows' => $out, 'final' => $final ];
	}

	private static function rowContainsUid( array $row, string $uid ): bool {
		$entry = $row['entry'] ?? [];
		if ( !is_array( $entry ) ) {
			return false;
		}
		if ( isset( $entry['item'] ) && is_array( $entry['item'] ) && self::itemUid( $entry['item'] ) === $uid ) {
			return true;
		}
		foreach ( [ 'from1', 'from2' ] as $key ) {
			if ( !isset( $entry[$key] ) || !is_array( $entry[$key] ) ) {
				continue;
			}
			foreach ( $entry[$key] as $item ) {
				if ( is_array( $item ) && self::itemUid( $item ) === $uid ) {
					return true;
				}
			}
		}
		return false;
	}

	private static function bestPlayerNameFromRows( array $rows, int $fallbackId ): string {
		foreach ( $rows as $row ) {
			$entry = $row['entry'] ?? [];
			foreach ( [ 'player', 'p1', 'p2', 'pickedUpBy', 'other' ] as $key ) {
				if ( isset( $entry[$key] ) && is_array( $entry[$key] ) ) {
					$id = (int)( $entry[$key]['userId'] ?? 0 );
					$name = (string)( $entry[$key]['name'] ?? '' );
					if ( $id === $fallbackId && $name !== '' ) {
						return $name;
					}
				}
			}
		}
		return (string)$fallbackId;
	}

	/**
	 * @return array<string, mixed>
	 */
	private static function ownerAfterRow( array $row, string $uid, int $currentId, string $currentName ): array {
		$entry = $row['entry'] ?? [];
		if ( !is_array( $entry ) ) {
			return [ 'kind' => 'unknown', 'label' => 'Unknown owner.' ];
		}
		$action = (string)( $entry['a'] ?? '' );
		if ( $action === 'trade' ) {
			foreach ( [ [ 'from1', 'p2' ], [ 'from2', 'p1' ] ] as $pair ) {
				[ $itemsKey, $ownerKey ] = $pair;
				foreach ( is_array( $entry[$itemsKey] ?? null ) ? $entry[$itemsKey] : [] as $item ) {
					if ( is_array( $item ) && self::itemUid( $item ) === $uid ) {
						return self::ownerFromPlayer( $entry[$ownerKey] ?? null );
					}
				}
			}
		}
		if ( $action === 'give' && isset( $entry['other'] ) ) {
			return self::ownerFromPlayer( $entry['other'] );
		}
		if ( $action === 'droppedPickup' && isset( $entry['pickedUpBy'] ) ) {
			return self::ownerFromPlayer( $entry['pickedUpBy'] );
		}
		if ( in_array( $action, [ 'delete', 'consume' ], true ) ) {
			return [ 'kind' => 'system', 'label' => 'Item left player ownership via ' . $action . '.' ];
		}
		if ( $action === 'drop' ) {
			return [ 'kind' => 'world', 'label' => 'Last seen dropped into the world by ' . $currentName . '.' ];
		}
		return [ 'kind' => 'player', 'userId' => $currentId, 'label' => 'Current owner appears to be ' . $currentName . ' (' . $currentId . ').' ];
	}

	private static function ownerFromPlayer( mixed $player ): array {
		if ( !is_array( $player ) ) {
			return [ 'kind' => 'unknown', 'label' => 'Transferred to an unknown player.' ];
		}
		$id = (int)( $player['userId'] ?? 0 );
		$name = (string)( $player['name'] ?? ( $id > 0 ? (string)$id : 'unknown player' ) );
		if ( $id <= 0 ) {
			return [ 'kind' => 'unknown', 'label' => 'Transferred to ' . $name . '.' ];
		}
		return [ 'kind' => 'player', 'userId' => $id, 'label' => 'Current owner appears to be ' . $name . ' (' . $id . ').' ];
	}
}
