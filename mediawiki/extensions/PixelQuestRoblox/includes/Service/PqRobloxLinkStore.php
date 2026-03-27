<?php

namespace PixelQuestRoblox\Service;

use MediaWiki\MediaWikiServices;
use PixelQuestRoblox\PqRobloxConfig;
use PixelQuestRoblox\PqRobloxLinkException;
use Wikimedia\Rdbms\IDatabase;

final class PqRobloxLinkStore {

	private function dbw(): IDatabase {
		return MediaWikiServices::getInstance()
			->getDBLoadBalancer()
			->getConnection( DB_PRIMARY );
	}

	private function dbr(): IDatabase {
		return MediaWikiServices::getInstance()
			->getDBLoadBalancer()
			->getConnection( DB_REPLICA );
	}

	public function isRobloxLinked( int $robloxUserId ): bool {
		$row = $this->dbr()->newSelectQueryBuilder()
			->select( 'prl_id' )
			->from( 'pq_roblox_link' )
			->where( [ 'prl_roblox_user_id' => $robloxUserId ] )
			->caller( __METHOD__ )
			->fetchRow();
		return $row !== false;
	}

	public function getLinkForWikiUser( int $wikiUserId ): ?array {
		$row = $this->dbr()->newSelectQueryBuilder()
			->select( [ 'prl_roblox_user_id', 'prl_created_unix' ] )
			->from( 'pq_roblox_link' )
			->where( [ 'prl_user_id' => $wikiUserId ] )
			->caller( __METHOD__ )
			->fetchRow();
		if ( !$row ) {
			return null;
		}
		return [
			'robloxUserId' => (int)$row->prl_roblox_user_id,
			'createdUnix' => (int)$row->prl_created_unix,
		];
	}

	/**
	 * @return array{code: string, expiresUnix: int}
	 */
	public function requestCode( int $robloxUserId ): array {
		if ( $robloxUserId <= 0 ) {
			throw new PqRobloxLinkException( 'pqroblox-api-error-bad-roblox-id' );
		}
		if ( $this->isRobloxLinked( $robloxUserId ) ) {
			throw new PqRobloxLinkException( 'pqroblox-api-error-roblox-already-linked' );
		}

		$dbw = $this->dbw();
		$now = time();
		$ttl = PqRobloxConfig::getCodeTTL();
		$expires = $now + $ttl;
		$code = $this->generateUniqueCode( $dbw );

		$dbw->newDeleteQueryBuilder()
			->deleteFrom( 'pq_roblox_link_codes' )
			->where( [ 'prlc_roblox_user_id' => $robloxUserId ] )
			->caller( __METHOD__ )
			->execute();

		$dbw->newInsertQueryBuilder()
			->insertInto( 'pq_roblox_link_codes' )
			->row( [
				'prlc_roblox_user_id' => $robloxUserId,
				'prlc_code' => $code,
				'prlc_expires_unix' => $expires,
				'prlc_created_unix' => $now,
			] )
			->caller( __METHOD__ )
			->execute();

		return [
			'code' => $code,
			'expiresUnix' => $expires,
		];
	}

	private function generateUniqueCode( IDatabase $dbw ): string {
		for ( $i = 0; $i < 20; $i++ ) {
			$code = strtoupper( substr( bin2hex( random_bytes( 5 ) ), 0, 10 ) );
			$exists = $dbw->newSelectQueryBuilder()
				->select( 'prlc_id' )
				->from( 'pq_roblox_link_codes' )
				->where( [ 'prlc_code' => $code ] )
				->caller( __METHOD__ )
				->fetchField();
			if ( !$exists ) {
				return $code;
			}
		}
		throw new PqRobloxLinkException( 'pqroblox-api-error-code-generation' );
	}

	/**
	 * @return int Roblox user id
	 */
	public function redeemCode( string $code, int $wikiUserId ): int {
		$code = strtoupper( preg_replace( '/\s+/', '', $code ) ?? '' );
		if ( $code === '' ) {
			throw new PqRobloxLinkException( 'pqroblox-wiki-error-empty-code' );
		}

		$dbw = $this->dbw();
		$dbw->startAtomic( __METHOD__ );
		try {
			$row = $dbw->newSelectQueryBuilder()
				->select( [ 'prlc_roblox_user_id', 'prlc_expires_unix' ] )
				->from( 'pq_roblox_link_codes' )
				->where( [ 'prlc_code' => $code ] )
				->caller( __METHOD__ )
				->fetchRow();

			if ( !$row ) {
				throw new PqRobloxLinkException( 'pqroblox-wiki-error-invalid-code' );
			}

			$robloxUserId = (int)$row->prlc_roblox_user_id;
			if ( time() > (int)$row->prlc_expires_unix ) {
				$dbw->newDeleteQueryBuilder()
					->deleteFrom( 'pq_roblox_link_codes' )
					->where( [ 'prlc_code' => $code ] )
					->caller( __METHOD__ )
					->execute();
				throw new PqRobloxLinkException( 'pqroblox-wiki-error-expired-code' );
			}

			$robloxLinked = $dbw->newSelectQueryBuilder()
				->select( 'prl_id' )
				->from( 'pq_roblox_link' )
				->where( [ 'prl_roblox_user_id' => $robloxUserId ] )
				->caller( __METHOD__ )
				->fetchRow();
			if ( $robloxLinked ) {
				throw new PqRobloxLinkException( 'pqroblox-wiki-error-roblox-already-linked' );
			}

			$wikiLinked = $dbw->newSelectQueryBuilder()
				->select( 'prl_id' )
				->from( 'pq_roblox_link' )
				->where( [ 'prl_user_id' => $wikiUserId ] )
				->caller( __METHOD__ )
				->fetchRow();
			if ( $wikiLinked ) {
				throw new PqRobloxLinkException( 'pqroblox-wiki-error-wiki-already-linked' );
			}

			$now = time();
			$dbw->newInsertQueryBuilder()
				->insertInto( 'pq_roblox_link' )
				->row( [
					'prl_user_id' => $wikiUserId,
					'prl_roblox_user_id' => $robloxUserId,
					'prl_created_unix' => $now,
				] )
				->caller( __METHOD__ )
				->execute();

			$dbw->newDeleteQueryBuilder()
				->deleteFrom( 'pq_roblox_link_codes' )
				->where( [ 'prlc_code' => $code ] )
				->caller( __METHOD__ )
				->execute();

			return $robloxUserId;
		} finally {
			$dbw->endAtomic( __METHOD__ );
		}
	}

	public function unlinkWikiUser( int $wikiUserId ): void {
		$dbw = $this->dbw();
		$dbw->newDeleteQueryBuilder()
			->deleteFrom( 'pq_roblox_link' )
			->where( [ 'prl_user_id' => $wikiUserId ] )
			->caller( __METHOD__ )
			->execute();
	}

	/**
	 * @return int|null Wiki user id linked to this Roblox account, if any.
	 */
	public function getWikiUserIdForRoblox( int $robloxUserId ): ?int {
		if ( $robloxUserId <= 0 ) {
			return null;
		}
		$row = $this->dbr()->newSelectQueryBuilder()
			->select( 'prl_user_id' )
			->from( 'pq_roblox_link' )
			->where( [ 'prl_roblox_user_id' => $robloxUserId ] )
			->caller( __METHOD__ )
			->fetchRow();
		if ( !$row ) {
			return null;
		}
		return (int)$row->prl_user_id;
	}
}
