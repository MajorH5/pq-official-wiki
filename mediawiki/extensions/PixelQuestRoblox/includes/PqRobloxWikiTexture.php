<?php

namespace PixelQuestRoblox;

/**
 * Resolves bot-uploaded wiki File: URLs. Semantic names (see docs/TEXTURE_NAMING.md);
 * legacy PQ_tex_{hash} lookups remain as fallback until wikis re-import.
 */
final class PqRobloxWikiTexture {

	/**
	 * Match Python json.dumps(x, sort_keys=True, separators=(",", ":")).
	 *
	 * @param mixed $v
	 * @return mixed
	 */
	public static function jsonSortKeys( $v ) {
		if ( !is_array( $v ) ) {
			return $v;
		}
		if ( self::isListArray( $v ) ) {
			$out = [];
			foreach ( $v as $item ) {
				$out[] = self::jsonSortKeys( $item );
			}
			return $out;
		}
		ksort( $v, SORT_STRING );
		$out = [];
		foreach ( $v as $k => $item ) {
			$out[$k] = self::jsonSortKeys( $item );
		}
		return $out;
	}

	/**
	 * @param array<mixed> $a
	 */
	private static function isListArray( array $a ): bool {
		if ( $a === [] ) {
			return true;
		}
		return array_keys( $a ) === range( 0, count( $a ) - 1 );
	}

	/**
	 * Same string as Python sprite_signature_for_hash(sprite).
	 *
	 * @param array<string, mixed> $sprite
	 */
	public static function spriteSignatureJson( array $sprite ): string {
		$sorted = self::jsonSortKeys( $sprite );
		$flags = JSON_UNESCAPED_SLASHES;
		$json = json_encode( $sorted, $flags );
		return $json !== false ? $json : '{}';
	}

	/**
	 * Same extension branch as sprites.render_sprite_object (static / tier / animation).
	 *
	 * @param array<string, mixed> $sprite
	 */
	public static function spriteOutputExtension( array $sprite ): string {
		if ( !empty( $sprite['Animation'] ) ) {
			return 'gif';
		}
		$hasRect = !empty( $sprite['imageRectOffset'] ) || !empty( $sprite['ImageRectOffset'] );
		if ( !empty( $sprite['Frames'] ) && !$hasRect ) {
			$framesSpec = $sprite['Frames'];
			if ( is_array( $framesSpec ) ) {
				$n = 0;
				foreach ( $framesSpec as $cell ) {
					if ( is_array( $cell ) && count( $cell ) >= 2 ) {
						$n++;
					}
				}
				if ( $n > 1 ) {
					return 'gif';
				}
				return 'png';
			}
		}
		return 'png';
	}

	public static function hashForSignatureAndExtension( string $sig, string $ext ): string {
		if ( $ext === 'gif' ) {
			return hash( 'sha256', $sig . '|gif_palette_v3', false );
		}
		return hash( 'sha256', $sig, false );
	}

	public static function parseAssetIdFromTextureString( ?string $t ): ?string {
		if ( !is_string( $t ) || $t === '' ) {
			return null;
		}
		if ( preg_match( '#rbxassetid://(\d+)#i', $t, $m ) ) {
			return $m[1];
		}
		return null;
	}

	/**
	 * @param array<string, mixed> $sprite
	 */
	public static function wikiUrlForSpriteLegacyHash( array $sprite ): ?string {
		$sig = self::spriteSignatureJson( $sprite );
		$primaryExt = self::spriteOutputExtension( $sprite );
		$tryExts = array_unique( [ $primaryExt, $primaryExt === 'gif' ? 'png' : 'gif' ] );
		foreach ( $tryExts as $ext ) {
			$h = self::hashForSignatureAndExtension( $sig, $ext );
			$fname = 'PQ_tex_' . $h . '.' . $ext;
			$url = PqRobloxWikiFileUrl::forFilename( $fname );
			if ( $url !== null ) {
				return $url;
			}
		}
		return null;
	}

	/**
	 * @param array<string, mixed> $sprite
	 */
	public static function wikiUrlForSprite( array $sprite ): ?string {
		return self::wikiUrlForSpriteLegacyHash( $sprite );
	}

	public static function wikiUrlForSemanticFilename( string $fname ): ?string {
		return PqRobloxWikiFileUrl::forFilename( $fname );
	}

	/**
	 * Items: item_{slug}_{id}.{ext}
	 *
	 * @param array<string, mixed> $sprite
	 */
	public static function wikiUrlForItemMainSprite( int $itemId, string $itemName, array $sprite ): ?string {
		$ext = self::spriteOutputExtension( $sprite );
		$base = PqRobloxTextureNames::itemSpriteBase( $itemId, $itemName );
		$url = self::wikiUrlForSemanticFilename( $base . '.' . $ext );
		if ( $url !== null ) {
			return $url;
		}
		return self::wikiUrlForSpriteLegacyHash( $sprite );
	}

	/**
	 * Tier strip cell: tier_star.png, tier_pixelween.png, …
	 *
	 * @param array<string, mixed> $tierIcon
	 */
	public static function wikiUrlForTierIconSprite( array $tierIcon ): ?string {
		$ext = self::spriteOutputExtension( $tierIcon );
		$base = PqRobloxTextureNames::tierIconBaseFromSprite( $tierIcon );
		$url = self::wikiUrlForSemanticFilename( $base . '.' . $ext );
		if ( $url !== null ) {
			return $url;
		}
		return self::wikiUrlForSpriteLegacyHash( $tierIcon );
	}

	/**
	 * Skin animation GIF (e.g. skin_*_*_e_idle.gif).
	 */
	public static function wikiUrlForSkinAnimation( int $skinId, string $skinName, string $animKey ): ?string {
		$base = PqRobloxTextureNames::skinAnimationBase( $skinId, $skinName, $animKey );
		$url = self::wikiUrlForSemanticFilename( $base . '.gif' );
		if ( $url !== null ) {
			return $url;
		}
		return null;
	}

	/**
	 * Rendered skin sheet preview (PQ Skin template).
	 *
	 * @param array<string, mixed> $sprite
	 */
	public static function wikiUrlForSkinSpritePreview( int $skinId, string $skinName, array $sprite ): ?string {
		$ext = self::spriteOutputExtension( $sprite );
		$base = PqRobloxTextureNames::skinSpritePreviewBase( $skinId, $skinName );
		$url = self::wikiUrlForSemanticFilename( $base . '.' . $ext );
		if ( $url !== null ) {
			return $url;
		}
		return self::wikiUrlForSpriteLegacyHash( $sprite );
	}

	/**
	 * @param array<string, mixed> $sprite
	 */
	public static function spriteLookupDiagnostics( array $sprite ): string {
		$sig = self::spriteSignatureJson( $sprite );
		$primaryExt = self::spriteOutputExtension( $sprite );
		$tryExts = array_unique( [ $primaryExt, $primaryExt === 'gif' ? 'png' : 'gif' ] );
		$files = [];
		foreach ( $tryExts as $ext ) {
			$h = self::hashForSignatureAndExtension( $sig, $ext );
			$files[] = 'PQ_tex_' . $h . '.' . $ext;
		}
		$keys = array_keys( $sprite );
		sort( $keys, SORT_STRING );
		return 'primary_ext=' . $primaryExt
			. ' tried=' . implode( '|', $files )
			. ' sig_len=' . strlen( $sig )
			. ' sprite_keys=' . implode( ',', $keys );
	}
}
