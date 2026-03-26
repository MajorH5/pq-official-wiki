<?php

namespace PixelQuestRoblox;

use Throwable;

final class PqRobloxLinkException extends \RuntimeException {

	/** @var array<int|string, string|int|float> */
	private array $params;

	/**
	 * @param array<int|string, string|int|float> $params
	 */
	public function __construct(
		public readonly string $msgKey,
		array $params = [],
		string $message = '',
		int $code = 0,
		?Throwable $previous = null
	) {
		parent::__construct( $message !== '' ? $message : $msgKey, $code, $previous );
		$this->params = $params;
	}

	/**
	 * @return array<int|string, string|int|float>
	 */
	public function getParams(): array {
		return $this->params;
	}
}
