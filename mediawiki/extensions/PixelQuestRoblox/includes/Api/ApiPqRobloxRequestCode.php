<?php

namespace PixelQuestRoblox\Api;

use MediaWiki\Api\ApiBase;
use MediaWiki\Request\WebRequest;
use PixelQuestRoblox\PqRobloxApiSecurity;
use PixelQuestRoblox\PqRobloxConfig;
use PixelQuestRoblox\PqRobloxLinkException;
use PixelQuestRoblox\Service\PqRobloxLinkStore;
use PixelQuestRoblox\Service\PqRobloxMessaging;
use Wikimedia\ParamValidator\ParamValidator;

final class ApiPqRobloxRequestCode extends ApiBase {

	public function execute(): void {
		$this->requirePostedParameters( [ 'robloxuserid' ] );

		$req = $this->getRequest();
		$this->assertSecret( $req );

		$robloxUserId = (int)$this->getParameter( 'robloxuserid' );
		$store = new PqRobloxLinkStore();

		try {
			$result = $store->requestCode( $robloxUserId );
		} catch ( PqRobloxLinkException $e ) {
			$this->dieWithError( $e->msgKey );
		}

		PqRobloxMessaging::publish( [
			'event' => 'code_created',
			'robloxUserId' => $robloxUserId,
			'expiresUnix' => $result['expiresUnix'],
		] );

		$this->getResult()->addValue( null, 'pqroblox', [
			'code' => $result['code'],
			'expiresUnix' => $result['expiresUnix'],
			'ttlSeconds' => PqRobloxConfig::getCodeTTL(),
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
		// Game servers call this without a logged-in wiki user; avoid requiring the writeapi right.
		return false;
	}

	public function needsToken(): bool {
		return false;
	}

	public function getAllowedParams(): array {
		return [
			'robloxuserid' => [
				ParamValidator::PARAM_TYPE => 'integer',
				ParamValidator::PARAM_REQUIRED => true,
			],
		];
	}
}
