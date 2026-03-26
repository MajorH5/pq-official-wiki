<?php

namespace PixelQuestRoblox\Service;

use PixelQuestRoblox\PqRobloxConfig;

/**
 * Roblox Open Cloud: publishMessage (Messaging Service).
 * @see https://create.roblox.com/docs/cloud/features/messaging-service
 */
final class PqRobloxMessaging {

	/**
	 * @param array<string, mixed> $payload Encoded as JSON string in the "message" field.
	 */
	public static function publish( array $payload ): void {
		$universe = PqRobloxConfig::getRobloxUniverseId();
		$key = PqRobloxConfig::getRobloxOpenCloudApiKey();
		if ( $universe === '' || $key === '' ) {
			wfDebugLog( 'pqroblox', 'Messaging skipped: ROBLOX_UNIVERSE_ID or ROBLOX_OPEN_CLOUD_API_KEY not set' );
			return;
		}

		$topic = PqRobloxConfig::getMessagingTopic();
		$url = sprintf(
			'https://apis.roblox.com/cloud/v2/universes/%s:publishMessage',
			rawurlencode( $universe )
		);

		$body = json_encode(
			[
				'topic' => $topic,
				'message' => json_encode( $payload, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE ),
			],
			JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE
		);

		if ( !function_exists( 'curl_init' ) ) {
			wfDebugLog( 'pqroblox', 'Messaging failed: PHP curl extension not available' );
			return;
		}

		$ch = curl_init( $url );
		curl_setopt_array( $ch, [
			CURLOPT_POST => true,
			CURLOPT_HTTPHEADER => [
				'Content-Type: application/json',
				'x-api-key: ' . $key,
			],
			CURLOPT_POSTFIELDS => $body,
			CURLOPT_RETURNTRANSFER => true,
			CURLOPT_TIMEOUT => 12,
		] );
		$responseBody = curl_exec( $ch );
		$httpCode = (int)curl_getinfo( $ch, CURLINFO_HTTP_CODE );
		$err = curl_error( $ch );
		curl_close( $ch );

		if ( $httpCode !== 200 ) {
			wfDebugLog(
				'pqroblox',
				"publishMessage failed HTTP $httpCode err=$err body=" . substr( (string)$responseBody, 0, 500 )
			);
		}
	}
}
