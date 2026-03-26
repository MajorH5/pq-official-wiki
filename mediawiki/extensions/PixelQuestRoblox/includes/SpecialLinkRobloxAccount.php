<?php

namespace PixelQuestRoblox;

use HTMLForm;
use MediaWiki\Html\Html;
use MediaWiki\SpecialPage\SpecialPage;
use MediaWiki\Status\Status;
use MediaWiki\User\User;
use PixelQuestRoblox\Service\PqRobloxLinkStore;
use PixelQuestRoblox\Service\PqRobloxMessaging;

final class SpecialLinkRobloxAccount extends SpecialPage {

	public function __construct() {
		parent::__construct( 'LinkRobloxAccount' );
	}

	public function execute( $subPage ): void {
		$this->requireLogin();
		$this->setHeaders();

		$out = $this->getOutput();
		$user = $this->getUser();
		$req = $this->getRequest();
		$store = new PqRobloxLinkStore();

		if ( $req->wasPosted() && $req->getVal( 'pqrobloxaction' ) === 'unlink' ) {
			if ( !$this->getUser()->matchEditToken( $req->getVal( 'token' ) ?? '' ) ) {
				$out->addWikiMsg( 'sessionfailure' );
				return;
			}
			$this->doUnlink( $store, $user );
			$out->redirect( $this->getPageTitle()->getFullURL() );
			return;
		}

		$link = $store->getLinkForWikiUser( $user->getId() );
		if ( $link !== null ) {
			$out->addWikiMsg( 'pqroblox-wiki-current-link', $link['robloxUserId'] );
			$out->addWikiMsg( 'pqroblox-wiki-goto-profile' );
			$out->addHTML( $this->getUnlinkFormHtml() );
			return;
		}

		$formDescriptor = [
			'code' => [
				'type' => 'text',
				'label-message' => 'pqroblox-form-code-label',
				'help-message' => 'pqroblox-form-code-help',
				'required' => true,
				'autocomplete' => false,
			],
		];

		$htmlForm = HTMLForm::factory( 'ooui', $formDescriptor, $this->getContext(), 'pqrobloxlink' );
		$htmlForm
			->setSubmitTextMsg( 'pqroblox-form-submit' )
			->setSubmitCallback( [ $this, 'onSubmitLink' ] )
			->setWrapperLegendMsg( 'pqroblox-form-legend' )
			->prepareForm()
			->show();
	}

	/**
	 * @param array{code:string} $data
	 * @return bool|Status
	 */
	public function onSubmitLink( $data ) {
		$store = new PqRobloxLinkStore();
		$user = $this->getUser();
		try {
			$robloxUserId = $store->redeemCode( $data['code'], $user->getId() );
		} catch ( PqRobloxLinkException $e ) {
			return Status::newFatal( $e->msgKey );
		}

		PqRobloxMessaging::publish( [
			'event' => 'linked',
			'robloxUserId' => $robloxUserId,
			'wikiUserName' => $user->getName(),
			'wikiUserId' => $user->getId(),
		] );

		$this->getOutput()->addWikiMsg( 'pqroblox-wiki-success', $robloxUserId );
		return true;
	}

	private function doUnlink( PqRobloxLinkStore $store, User $user ): void {
		$link = $store->getLinkForWikiUser( $user->getId() );
		if ( $link === null ) {
			return;
		}
		$rid = $link['robloxUserId'];
		$store->unlinkWikiUser( $user->getId() );
		PqRobloxMessaging::publish( [
			'event' => 'unlinked',
			'robloxUserId' => $rid,
			'wikiUserName' => $user->getName(),
			'wikiUserId' => $user->getId(),
		] );
	}

	private function getUnlinkFormHtml(): string {
		$token = $this->getUser()->getEditToken();
		return Html::rawElement(
			'form',
			[
				'method' => 'post',
				'action' => $this->getPageTitle()->getLocalURL(),
				'class' => 'mw-htmlform',
			],
			Html::element( 'input', [
				'type' => 'hidden',
				'name' => 'pqrobloxaction',
				'value' => 'unlink',
			] )
			. Html::element( 'input', [
				'type' => 'hidden',
				'name' => 'token',
				'value' => $token,
			] )
			. Html::element( 'input', [
				'type' => 'submit',
				'name' => 'unlink',
				'value' => $this->msg( 'pqroblox-unlink-submit' )->text(),
			] )
		);
	}
}
