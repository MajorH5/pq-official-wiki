<?php

namespace PixelQuestRoblox\Service;

use MediaWiki\MediaWikiServices;
use Wikimedia\Rdbms\SelectQueryBuilder;

/**
 * userid -> username index (game API + profile view refresh). Not a copy of Roblox save data.
 */
final class PqRobloxPlayerIndexStore {

	/** @var bool|null Cached for this request */
	private static $tableReady = null;

	/** Table exists and has the columns this code expects (avoids 1054 on legacy/wrong schemas). */
	private function dbPlayerIndexReady(): bool {
		if ( self::$tableReady !== null ) {
			return self::$tableReady;
		}
		$dbr = MediaWikiServices::getInstance()->getDBLoadBalancer()->getConnection( DB_REPLICA );
		if ( !$dbr->tableExists( 'pq_roblox_player_index', __METHOD__ ) ) {
			self::$tableReady = false;

			return false;
		}
		foreach ( [ 'roblox_user_id', 'username_normalized', 'username_display', 'updated_at' ] as $field ) {
			if ( !$dbr->fieldExists( 'pq_roblox_player_index', $field, __METHOD__ ) ) {
				self::$tableReady = false;

				return false;
			}
		}
		self::$tableReady = true;

		return true;
	}

	private function normalizeUsername( string $name ): string {
		$name = trim( $name );
		return strtolower( str_replace( '_', ' ', $name ) );
	}

	/**
	 * Escape a literal for SQL LIKE (MySQL default escape: \ % _).
	 * Replaces removed IDatabase::escapeLike() (not on Database in MW 1.45+).
	 */
	private static function escapeLikeValue( string $s ): string {
		$s = str_replace( '\\', '\\\\', $s );
		$s = str_replace( '%', '\\%', $s );
		$s = str_replace( '_', '\\_', $s );

		return $s;
	}

	public function upsert( int $robloxUserId, ?string $username ): void {
		if ( !$this->dbPlayerIndexReady() ) {
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
		if ( !$this->dbPlayerIndexReady() ) {
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
		if ( !$this->dbPlayerIndexReady() ) {
			return [];
		}
		$limit = max( 1, min( 50, $limit ) );
		$norm = $this->normalizeUsername( $q );
		if ( $norm === '' ) {
			return [];
		}
		$dbr = MediaWikiServices::getInstance()->getDBLoadBalancer()->getConnection( DB_REPLICA );
		$pattern = self::escapeLikeValue( $norm ) . '%';
		$res = $dbr->newSelectQueryBuilder()
			->select( [ 'roblox_user_id', 'username_display' ] )
			->from( 'pq_roblox_player_index' )
			->where( 'username_normalized LIKE ' . $dbr->addQuotes( $pattern ) )
			->orderBy( 'username_display', SelectQueryBuilder::SORT_ASC )
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
		if ( !$this->dbPlayerIndexReady() ) {
			return [];
		}
		if ( !preg_match( '/^\d+$/', $digits ) ) {
			return [];
		}
		$limit = max( 1, min( 50, $limit ) );
		$dbr = MediaWikiServices::getInstance()->getDBLoadBalancer()->getConnection( DB_REPLICA );
		$pattern = self::escapeLikeValue( $digits ) . '%';
		$res = $dbr->newSelectQueryBuilder()
			->select( [ 'roblox_user_id', 'username_display' ] )
			->from( 'pq_roblox_player_index' )
			->where( 'CAST(roblox_user_id AS CHAR) LIKE ' . $dbr->addQuotes( $pattern ) )
			->orderBy( 'roblox_user_id', SelectQueryBuilder::SORT_ASC )
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
