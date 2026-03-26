<?php

namespace PixelQuestRoblox;

/**
 * Semantic wiki texture basenames (must match bot/pq_wiki/texture_names.py).
 */
final class PqRobloxTextureNames {

	/** @var array<int, string> */
	private const TIER_ROW_TO_THEME = [
		0 => 'tier_star',
		2 => 'tier_pixelween',
		8 => 'tier_pixelmas',
		9 => 'tier_gamemode',
	];

	public static function slug( string $text ): string {
		$t = strtolower( trim( $text ) );
		$t = preg_replace( '/[^a-z0-9]+/', '-', $t ) ?? '';
		$t = preg_replace( '/-+/', '-', $t ) ?? '';
		$t = trim( $t, '-' );
		return $t !== '' ? $t : 'x';
	}

	public static function sanitizeBase( string $name ): string {
		$s = strtolower( trim( $name ) );
		$s = preg_replace( '/[^a-z0-9_.-]/', '_', $s ) ?? '';
		$s = preg_replace( '/_+/', '_', $s ) ?? '';
		$s = trim( $s, '_' );
		return $s !== '' ? $s : 'asset';
	}

	public static function itemSpriteBase( int $itemId, string $name ): string {
		return self::sanitizeBase( 'item_' . self::slug( $name ) . '_' . $itemId );
	}

	/**
	 * @param array<string, mixed> $tierIcon
	 */
	public static function tierIconBaseFromSprite( array $tierIcon ): string {
		$frames = $tierIcon['Frames'] ?? [];
		$row = 0;
		if ( is_array( $frames ) && $frames !== [] ) {
			$cell = $frames[0];
			if ( is_array( $cell ) && isset( $cell[1] ) ) {
				$row = (int)$cell[1];
			}
		}
		$theme = self::TIER_ROW_TO_THEME[$row] ?? ( 'tier_row_' . $row );
		return self::sanitizeBase( $theme );
	}

	public static function skinNameBase( int $skinId, string $name ): string {
		return self::sanitizeBase( 'skin_' . self::slug( $name ) . '_' . $skinId );
	}

	public static function skinAnimationBase( int $skinId, string $name, string $animKey ): string {
		return self::sanitizeBase( self::skinNameBase( $skinId, $name ) . '_' . $animKey );
	}

	public static function skinSpritePreviewBase( int $skinId, string $name ): string {
		return self::sanitizeBase( self::skinNameBase( $skinId, $name ) . '_sprite' );
	}

	public static function skinIdlePreviewBase( int $skinId, string $name ): string {
		return self::sanitizeBase( self::skinNameBase( $skinId, $name ) . '_idle_preview' );
	}

	public static function lootDropBase( string $kind, int $tier ): string {
		$k = $kind === 'chest' ? 'chest' : 'bag';
		return self::sanitizeBase( "drop_{$k}_{$tier}" );
	}

	public static function skinRarityBase( int $rarity ): string {
		return self::sanitizeBase( 'skin_rarity_' . max( 0, min( 4, $rarity ) ) );
	}

	public static function statIconBase( string $statLower ): string {
		return self::sanitizeBase( 'stat_' . strtolower( trim( $statLower ) ) );
	}

	public static function valorIconBase(): string {
		return 'valor_icon';
	}

	public static function difficultySkullBase(): string {
		return 'skull_difficulty';
	}

	/**
	 * One file per unique rendered projectile (sheet + animation or static rect), not per descriptor id.
	 * Must match bot/pq_wiki/texture_names.py projectile_sprite_base().
	 *
	 * @param array<string, mixed> $sprite ProjectileDescriptor.Sprite from the datadump
	 */
	public static function projectileSpriteBase( array $sprite ): string {
		$t = $sprite['texture'] ?? $sprite['Texture'] ?? null;
		$aid = PqRobloxWikiTexture::parseAssetIdFromTextureString( is_string( $t ) ? $t : null );
		$payload = self::projectileVisualSignaturePayload( $sprite, $aid );
		$sorted = PqRobloxWikiTexture::jsonSortKeys( $payload );
		$flags = JSON_UNESCAPED_SLASHES;
		$json = json_encode( $sorted, $flags );
		if ( $json === false ) {
			$json = '{}';
		}
		$short = substr( hash( 'sha256', $json, false ), 0, 12 );
		if ( $aid !== null && $aid !== '' ) {
			return self::sanitizeBase( 'projectile_tex_' . $aid . '_' . $short );
		}
		return self::sanitizeBase( 'projectile_' . $short );
	}

	/**
	 * @deprecated Use projectileSpriteBase() — same texture can be reused with different ids.
	 */
	public static function projectileBase( int $projectileId ): string {
		return self::sanitizeBase( 'projectile_' . $projectileId );
	}

	/**
	 * @param array<string, mixed> $sprite
	 */
	private static function projectileVisualSignaturePayload( array $sprite, ?string $aid ): array {
		$anim = $sprite['Animation'] ?? null;
		if ( is_array( $anim ) && $anim !== [] ) {
			return [
				'asset_id' => $aid,
				'fps_scale' => 0.5,
				'animation' => PqRobloxWikiTexture::jsonSortKeys( $anim ),
			];
		}
		return [
			'asset_id' => $aid,
			'static' => PqRobloxWikiTexture::jsonSortKeys( [
				'imageRectOffset' => $sprite['imageRectOffset'] ?? $sprite['ImageRectOffset'] ?? null,
				'imageRectSize' => $sprite['imageRectSize'] ?? $sprite['ImageRectSize'] ?? null,
			] ),
		];
	}
}
