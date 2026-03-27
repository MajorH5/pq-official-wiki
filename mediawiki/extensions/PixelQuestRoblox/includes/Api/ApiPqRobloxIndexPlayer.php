<?php

namespace PixelQuestRoblox\Api;

use MediaWiki\Api\ApiBase;
use MediaWiki\Request\WebRequest;
use PixelQuestRoblox\PqRobloxApiSecurity;
use PixelQuestRoblox\PqRobloxConfig;
use PixelQuestRoblox\Service\PqRobloxPlayerIndexStore;
use Wikimedia\ParamValidator\ParamValidator;

/**
 * Game server: register or refresh a Roblox user id + optional username in the wiki search index.
 */
final class ApiPqRobloxIndexPlayer extends ApiBase {

	public function execute(): void {
		$this->requirePostedParameters( [ 'userid' ] );

		$req = $this->getRequest();
		$this->assertSecret( $req );

		$robloxUserId = (int)$this->getParameter( 'userid' );
		if ( $robloxUserId <= 0 ) {
			$this->dieWithError( 'pqroblox-api-error-bad-roblox-id' );
		}

		$username = trim( (string)$this->getParameter( 'username' ) );
		if ( $username !== '' && strlen( $username ) > 64 ) {
			$this->dieWithError( 'pqroblox-api-error-bad-username' );
		}
		if ( $username === '' ) {
			$username = null;
		}

		$store = new PqRobloxPlayerIndexStore();
		$store->upsert( $robloxUserId, $username );

		// Use integer, not boolean: legacy format=json maps true to "" (BC empty-string-as-true).
		$this->getResult()->addValue( null, 'pqroblox', [
			'indexed' => 1,
			'robloxUserId' => $robloxUserId,
		] );
	}

	private function assertSecret( WebRequest $request ): void {
		if ( PqRobloxConfig::getApiSecret() === '' ) {
			$this->dieWithError( 'pqroblox-api-error-no-secret' );
		}
		if ( !PqRobloxApiSecurity::secretMatches( $request ) ) {
			$this->dieWithError( 'pqroblox-api-error-invalid-secret' );
		}
	}

	public function mustBePosted(): bool {
		return true;
	}

	public function isWriteMode(): bool {
		return false;
	}

	public function needsToken(): bool {
		return false;
	}

	public function getAllowedParams(): array {
		return [
			'userid' => [
				ParamValidator::PARAM_TYPE => 'integer',
				ParamValidator::PARAM_REQUIRED => true,
			],
			'username' => [
				ParamValidator::PARAM_TYPE => 'string',
				ParamValidator::PARAM_DEFAULT => '',
			],
		];
	}
}
