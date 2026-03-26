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
		$out->setPageTitle( $this->msg( 'linkrobloxaccount' )->text() );
		$out->addModules( [ 'ext.multimediaViewer.bootstrap' ] );
		$out->addModules( [ 'oojs-ui-core', 'oojs-ui-widgets' ] );
		$out->addModuleStyles( [
			'oojs-ui-core.styles',
			'oojs-ui.styles.icons-content',
			'oojs-ui.styles.icons-interactions',
			'oojs-ui.styles.indicators',
		] );
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
			$out->addHTML(
				Html::rawElement(
					'p',
					[],
					Html::element(
						'a',
						[
							'href' => 'https://www.roblox.com/users/' . (int)$link['robloxUserId'] . '/profile',
							'class' => 'external',
							'rel' => 'nofollow noopener noreferrer',
							'target' => '_blank',
						],
						'Open Roblox profile'
					)
				)
			);
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
		$out->addHTML( $this->getPlaceholderGuideHtml() );
		$out->addInlineStyle(
			'.pqroblox-link-guide-image img{cursor:zoom-in;max-width:100%;height:auto}'
			. '.pqroblox-guide-zoom{position:fixed;inset:0;background:rgba(0,0,0,.86);display:flex;align-items:center;justify-content:center;z-index:10000;padding:1rem}'
			. '.pqroblox-guide-zoom img{max-width:95vw;max-height:95vh;box-shadow:0 10px 28px rgba(0,0,0,.55)}'
			. '.pqroblox-guide-zoom-close{position:absolute;top:12px;right:12px;background:#fff;border:1px solid #a2a9b1;border-radius:4px;padding:.35rem .6rem;cursor:pointer;font:inherit}'
		);
		$out->addInlineScript(
			"(function(){"
			. "function close(){var o=document.querySelector('.pqroblox-guide-zoom');if(o){o.remove();}}"
			. "document.addEventListener('click',function(ev){"
			. "var a=ev.target&&ev.target.closest&&ev.target.closest('.pqroblox-link-guide-image a.image');"
			. "if(!a){return;}"
			. "ev.preventDefault();"
			. "var img=a.querySelector('img');if(!img){return;}"
			. "close();"
			. "var ov=document.createElement('div');ov.className='pqroblox-guide-zoom';ov.setAttribute('role','dialog');ov.setAttribute('aria-label','Image preview');"
			. "var big=document.createElement('img');big.src=img.currentSrc||img.src;big.alt=img.alt||'';"
			. "var btn=document.createElement('button');btn.type='button';btn.className='pqroblox-guide-zoom-close';btn.textContent='Close';"
			. "btn.addEventListener('click',close);ov.addEventListener('click',function(e){if(e.target===ov){close();}});"
			. "ov.appendChild(big);ov.appendChild(btn);document.body.appendChild(ov);"
			. "});"
			. "document.addEventListener('keydown',function(e){if(e.key==='Escape'){close();}});"
			. "})();"
		);
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
		$label = $this->msg( 'pqroblox-unlink-submit' )->text();
		$button = Html::rawElement(
			'span',
			[
				'class' => 'mw-htmlform-submit oo-ui-widget oo-ui-widget-enabled oo-ui-inputWidget '
					. 'oo-ui-buttonElement oo-ui-buttonElement-framed oo-ui-labelElement '
					. 'oo-ui-flaggedElement-primary oo-ui-flaggedElement-progressive oo-ui-buttonInputWidget',
			],
			Html::rawElement(
				'button',
				[
					'type' => 'submit',
					'tabindex' => '0',
					'value' => $label,
					'name' => 'unlink',
					'class' => 'oo-ui-inputWidget-input oo-ui-buttonElement-button',
				],
				Html::rawElement( 'span', [ 'class' => 'oo-ui-iconElement-icon oo-ui-iconElement-noIcon oo-ui-image-invert' ], '' )
				. Html::element( 'span', [ 'class' => 'oo-ui-labelElement-label' ], $label )
				. Html::rawElement( 'span', [ 'class' => 'oo-ui-indicatorElement-indicator oo-ui-indicatorElement-noIndicator oo-ui-image-invert' ], '' )
			)
		);
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
			. Html::rawElement( 'div', [ 'class' => 'mw-htmlform-submit-buttons' ], $button )
		);
	}

	private function getPlaceholderGuideHtml(): string {
		$steps = [
			[
				'title' => 'Step 1: Open Pixel Quest',
				'text' => 'Navigate to the <a href="https://www.roblox.com/games/80003276594057/Pixel-Quest" target="_blank">Pixel Quest game in Roblox</a>. Click the "Play" button to open the game.',
				'image' => '[[File:wikicode-img-1.png|640px]]',
			],
			[
				'title' => 'Step 2: Enter into the game',
				'text' => 'Once you have loaded into Roblox, click the "Play" button to join Haven. If this is your first time playing, you will need to complete the tutorial first.',
				'image' => '[[File:wikicode-img-2.png|640px]]',
			],
			[
				'title' => 'Step 3: Run /wikicode command',
				'text' => 'Press the "/" key or click the chat box. Type "/wikicode" and press enter. <b>You may be asked to read the warning and enter the command again. Do not share the code with anyone.</b>',
				'image' => '[[File:wikicode-img-3.png|640px]]',
			],
			[
				'title' => 'Step 4: Copy the code',
				'text' => 'Wait for the code to appear in the chat. Copy the code to your clipboard. <b>The chat message with the code is selectable/copyable for you.</b>',
				'image' => '[[File:wikicode-img-4.png|640px]]',
			],
			[
				'title' => 'Step 5: Paste the code',
				'text' => 'Paste the code into the field above and click "Link account".',
				'image' => '[[File:wikicode-img-5.png|640px]]',
			],
		];

		$html = Html::rawElement( 'h2', [], 'How to generate your wiki code' );
		foreach ( $steps as $s ) {
			$html .= Html::rawElement(
				'div',
				[ 'class' => 'pqroblox-link-guide-step' ],
				Html::rawElement( 'h3', [], $s['title'] )
				. Html::rawElement( 'p', [], $s['text'] )
				. Html::rawElement( 'p', [ 'class' => 'pqroblox-link-guide-image' ], $this->getOutput()->parseAsInterface( $s['image'] ) )
			);
		}
		return Html::rawElement( 'div', [ 'class' => 'pqroblox-link-guide mw-parser-output' ], $html );
	}
}
