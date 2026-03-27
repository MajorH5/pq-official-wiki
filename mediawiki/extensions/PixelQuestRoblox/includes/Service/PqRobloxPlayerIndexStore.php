<?php

namespace PixelQuestRoblox\Service;

use MediaWiki\MediaWikiServices;
use Wikimedia\Rdbms\IDatabase;

/**
 * userid -> username index (game API + profile view refresh). Not a copy of Roblox save data.
 */
final class PqRobloxPlayerIndexStore {

	/** @var bool|null Cached for this request */
	private static $tableExists = null;

	private function dbHasTable(): bool {
		if ( self::$tableExists !== null ) {
			return self::$tableExists;
		}
		$dbr = MediaWikiServices::getInstance()->getDBLoadBalancer()->getConnection( DB_REPLICA );
		self::$tableExists = $dbr->tableExists( 'pq_roblox_player_index', __METHOD__ );
		return self::$tableExists;
	}

	private function normalizeUsername( string $name ): string {
		$name = trim( $name );
		return strtolower( str_replace( '_', ' ', $name ) );
	}

	public function upsert( int $robloxUserId, ?string $username ): void {
		if ( !$this->dbHasTable() ) {
			return;
		}
		if ( $robloxUserId <= 0 ) {
			return;
		}
		$display = $username !== null && $username !== '' ? trim( $username ) : '';
		if ( $display === '' ) {
			$display = (string)$robloxUserId;
		}
		$norm = $this->normalizeUsername( $display );
		$dbw = MediaWikiServices::getInstance()->getDBLoadBalancer()->getConnection( DB_PRIMARY );
		$ts = $dbw->timestamp();
		$exists = $dbw->newSelectQueryBuilder()
			->select( 'roblox_user_id' )
			->from( 'pq_roblox_player_index' )
			->where( [ 'roblox_user_id' => $robloxUserId ] )
			->caller( __METHOD__ )
			->fetchField();
		if ( $exists ) {
			$dbw->newUpdateQueryBuilder()
				->update( 'pq_roblox_player_index' )
				->set( [
					'username_normalized' => $norm,
					'username_display' => $display,
					'updated_at' => $ts,
				] )
				->where( [ 'roblox_user_id' => $robloxUserId ] )
				->caller( __METHOD__ )
				->execute();
		} else {
			$dbw->newInsertQueryBuilder()
				->insertInto( 'pq_roblox_player_index' )
				->row( [
					'roblox_user_id' => $robloxUserId,
					'username_normalized' => $norm,
					'username_display' => $display,
					'updated_at' => $ts,
				] )
				->caller( __METHOD__ )
				->execute();
		}
	}

	/**
	 * @return array{robloxUserId:int, username_display:string}|null
	 */
	public function findByUsername( string $name ): ?array {
		if ( !$this->dbHasTable() ) {
			return null;
		}
		$norm = $this->normalizeUsername( $name );
		if ( $norm === '' ) {
			return null;
		}
		$dbr = MediaWikiServices::getInstance()->getDBLoadBalancer()->getConnection( DB_REPLICA );
		$row = $dbr->newSelectQueryBuilder()
			->select( [ 'roblox_user_id', 'username_display' ] )
			->from( 'pq_roblox_player_index' )
			->where( [ 'username_normalized' => $norm ] )
			->caller( __METHOD__ )
			->fetchRow();
		if ( !$row ) {
			return null;
		}
		return [
			'robloxUserId' => (int)$row->roblox_user_id,
			'username_display' => (string)$row->username_display,
		];
	}

	/**
	 * Prefix match on normalized username (for OpenSearch). Query may contain underscores.
	 *
	 * @return list<array{robloxUserId:int, username_display:string}>
	 */
	public function searchPrefix( string $q, int $limit ): array {
		if ( !$this->dbHasTable() ) {
			return [];
		}
		$limit = max( 1, min( 50, $limit ) );
		$norm = $this->normalizeUsername( $q );
		if ( $norm === '' ) {
			return [];
		}
		$dbr = MediaWikiServices::getInstance()->getDBLoadBalancer()->getConnection( DB_REPLICA );
		$pattern = $dbr->escapeLike( $norm ) . '%';
		$res = $dbr->newSelectQueryBuilder()
			->select( [ 'roblox_user_id', 'username_display' ] )
			->from( 'pq_roblox_player_index' )
			->where( 'username_normalized LIKE ' . $dbr->addQuotes( $pattern ) )
			->orderBy( 'username_display', IDatabase::SORT_ASC )
			->limit( $limit )
			->caller( __METHOD__ )
			->fetchResultSet();
		$out = [];
		foreach ( $res as $row ) {
			$out[] = [
				'robloxUserId' => (int)$row->roblox_user_id,
				'username_display' => (string)$row->username_display,
			];
		}
		return $out;
	}

	/**
	 * Match indexed Roblox user ids by numeric prefix (e.g. "321" → 32163212).
	 *
	 * @return list<array{robloxUserId:int, username_display:string}>
	 */
	public function searchRobloxIdsByPrefix( string $digits, int $limit ): array {
		if ( !$this->dbHasTable() ) {
			return [];
		}
		if ( !preg_match( '/^\d+$/', $digits ) ) {
			return [];
		}
		$limit = max( 1, min( 50, $limit ) );
		$dbr = MediaWikiServices::getInstance()->getDBLoadBalancer()->getConnection( DB_REPLICA );
		$pattern = $dbr->escapeLike( $digits ) . '%';
		$res = $dbr->newSelectQueryBuilder()
			->select( [ 'roblox_user_id', 'username_display' ] )
			->from( 'pq_roblox_player_index' )
			->where( 'CAST(roblox_user_id AS CHAR) LIKE ' . $dbr->addQuotes( $pattern ) )
			->orderBy( 'roblox_user_id', IDatabase::SORT_ASC )
			->limit( $limit )
			->caller( __METHOD__ )
			->fetchResultSet();
		$out = [];
		foreach ( $res as $row ) {
			$out[] = [
				'robloxUserId' => (int)$row->roblox_user_id,
				'username_display' => (string)$row->username_display,
			];
		}
		return $out;
	}
}
