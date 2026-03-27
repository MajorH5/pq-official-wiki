<?php

namespace PixelQuestRoblox\Service;

use PixelQuestRoblox\PqRobloxConfig;
use PixelQuestRoblox\PqRobloxTextureNames;
use PixelQuestRoblox\PqRobloxWikiFileUrl;
use PixelQuestRoblox\PqRobloxWikiTexture;

/**
 * Loads pq-datadump.json once per request (static cache) and builds id → wiki page title + texture URLs.
 * Title algorithm mirrors bot/pq_wiki/renderers/pathing.py (claim_unique_title).
 */
final class PqRobloxLookupIndex {

	/** Same strip order as bot/pq_wiki/stat_icons.py (STAT_ICONS_16X16_RENDERED_1X). */
	private const STAT_ICON_INDEX = [
		'health' => 0,
		'mana' => 1,
		'defense' => 2,
		'vitality' => 3,
		'speed' => 4,
		'wisdom' => 5,
		'attack' => 6,
		'dexterity' => 7,
	];

	/** @var self|null */
	private static $instance;

	/** @var array<int, array<string, mixed>> */
	private $itemsById = [];

	/** @var array<int, array<string, mixed>> */
	private $skinsById = [];

	/** @var array<int, array<string, mixed>> */
	private $entitiesById = [];

	/** @var array<int, array<string, mixed>> */
	private $accountStatsById = [];

	/** @var array<int, string> */
	private $itemTitleById = [];

	/** @var array<int, string> */
	private $skinTitleById = [];

	/** @var array<int, string> */
	private $entityTitleById = [];

	/** @var array<int, string> */
	private $accountStatTitleById = [];

	/** @var array<int, string> ordered skin ids for grid */
	private $allSkinIdsOrdered = [];

	/** @var array<int, true> Dedupe wfDebugLog lines per item id per request */
	private $loggedMissingItemTexture = [];

	/** Raw Texture string from datadump (e.g. rbxassetid://…) for stat icon filename hashing. */
	private ?string $statTextureRaw = null;

	/** Asset id for LOOT_CONTAINERS_8X8_RENDERED (loot_tier_icons.py). */
	private ?string $lootTextureAssetId = null;

	/** @var array<int, array<string, mixed>> */
	private $badgesById = [];

	/** @var array<int, array<string, mixed>> */
	private $achievementsById = [];

	/** @var array<int, string> */
	private $badgeTitleById = [];

	/** @var array<int, string> */
	private $achievementTitleById = [];

	/** @var array<int, string> ordered badge ids for grid */
	private $allBadgeIdsOrdered = [];

	/** Denominator for honor → %: (honor / this) * 100 — see MaxAttainableHonorPoints / MaxPossibleHonor in datadump. */
	private float $maxAttainableHonorPoints = 0.0;

	/** @var array<string, string> HonorToName */
	private $honorToName = [];

	/**
	 * @var array<int, array{min: float, max: float}>
	 */
	private $honorRangesByRank = [];

	/** @var int[] */
	private $honorRankOrder = [];

	private function __construct() {
		$path = PqRobloxConfig::getDataDumpPath();
		if ( !is_readable( $path ) ) {
			return;
		}
		$raw = file_get_contents( $path );
		if ( $raw === false ) {
			return;
		}
		$data = json_decode( $raw, true );
		if ( !is_array( $data ) ) {
			return;
		}

		$items = $data['Items'] ?? [];
		if ( is_array( $items ) ) {
			foreach ( $items as $row ) {
				if ( !is_array( $row ) ) {
					continue;
				}
				$id = (int)( $row['Id'] ?? 0 );
				if ( $id >= 0 ) {
					$this->itemsById[$id] = $row;
				}
			}
			$this->itemTitleById = self::buildTitles( $this->itemsById, 'Item' );
		}

		$skins = $data['CharacterSkins'] ?? [];
		if ( is_array( $skins ) ) {
			foreach ( $skins as $row ) {
				if ( !is_array( $row ) ) {
					continue;
				}
				$id = (int)( $row['Id'] ?? 0 );
				if ( $id >= 0 ) {
					$this->skinsById[$id] = $row;
				}
			}
			$this->skinTitleById = self::buildTitles( $this->skinsById, 'Skin' );
			$this->allSkinIdsOrdered = array_keys( $this->skinsById );
			sort( $this->allSkinIdsOrdered, SORT_NUMERIC );
		}

		$gos = $data['GameObjects'] ?? [];
		if ( is_array( $gos ) ) {
			foreach ( $gos as $row ) {
				if ( !is_array( $row ) || empty( $row['IsEntity'] ) ) {
					continue;
				}
				$id = (int)( $row['Id'] ?? 0 );
				if ( $id >= 0 ) {
					$this->entitiesById[$id] = $row;
				}
			}
			$this->entityTitleById = self::buildTitles( $this->entitiesById, 'Entity' );
		}

		$accountStats = $data['AccountStats'] ?? [];
		if ( is_array( $accountStats ) ) {
			foreach ( $accountStats as $row ) {
				if ( !is_array( $row ) ) {
					continue;
				}
				$id = (int)( $row['Id'] ?? 0 );
				if ( $id >= 0 ) {
					$this->accountStatsById[$id] = $row;
				}
			}
			$this->accountStatTitleById = self::buildTitles( $this->accountStatsById, 'Account Stat' );
		}

		$badges = $data['Badges'] ?? [];
		if ( is_array( $badges ) ) {
			foreach ( $badges as $row ) {
				if ( !is_array( $row ) ) {
					continue;
				}
				$id = (int)( $row['Id'] ?? 0 );
				if ( $id >= 0 ) {
					$this->badgesById[$id] = $row;
				}
			}
			$this->badgeTitleById = self::buildTitles( $this->badgesById, 'Badge' );
			$this->allBadgeIdsOrdered = array_keys( $this->badgesById );
			sort( $this->allBadgeIdsOrdered, SORT_NUMERIC );
		}

		$achievements = $data['Achievements'] ?? [];
		if ( is_array( $achievements ) ) {
			foreach ( $achievements as $row ) {
				if ( !is_array( $row ) ) {
					continue;
				}
				$id = (int)( $row['Id'] ?? 0 );
				if ( $id >= 0 ) {
					$this->achievementsById[$id] = $row;
				}
			}
			$this->achievementTitleById = self::buildTitles( $this->achievementsById, 'Achievement' );
		}

		$maxHonorRaw = $data['MaxAttainableHonorPoints'] ?? $data['maxAttainableHonorPoints'] ?? null;
		if ( $maxHonorRaw === null && is_array( $data['Achievement'] ?? null ) ) {
			$ach = $data['Achievement'];
			$maxHonorRaw = $ach['MaxAttainableHonorPoints'] ?? $ach['maxAttainableHonorPoints'] ?? null;
		}
		if ( $maxHonorRaw === null ) {
			$maxHonorRaw = $data['MaxPossibleHonor'] ?? $data['maxPossibleHonor'] ?? 0;
		}
		$this->maxAttainableHonorPoints = (float)$maxHonorRaw;

		$htn = $data['HonorToName'] ?? [];
		if ( is_array( $htn ) ) {
			foreach ( $htn as $k => $v ) {
				if ( is_string( $v ) ) {
					$this->honorToName[(string)$k] = $v;
				}
			}
		}

		$hr = $data['HonorRanges'] ?? [];
		if ( is_array( $hr ) ) {
			foreach ( $hr as $k => $spec ) {
				if ( !is_array( $spec ) ) {
					continue;
				}
				if ( !is_numeric( $k ) ) {
					continue;
				}
				$rid = (int)$k;
				$this->honorRangesByRank[$rid] = [
					'min' => (float)( $spec['min'] ?? $spec['Min'] ?? 0 ),
					'max' => (float)( $spec['max'] ?? $spec['Max'] ?? 100 ),
				];
			}
			$this->honorRankOrder = array_keys( $this->honorRangesByRank );
			$ranges = $this->honorRangesByRank;
			usort(
				$this->honorRankOrder,
				static function ( int $a, int $b ) use ( $ranges ) {
					$ha = $ranges[$a] ?? [ 'min' => 0.0 ];
					$hb = $ranges[$b] ?? [ 'min' => 0.0 ];
					return $ha['min'] <=> $hb['min'];
				}
			);
		}

		$textures = $data['Textures'] ?? null;
		if ( is_array( $textures ) ) {
			$st = $textures['STAT_ICONS_16X16_RENDERED_1X'] ?? null;
			if ( is_array( $st ) ) {
				$t = $st['Texture'] ?? $st['texture'] ?? null;
				$this->statTextureRaw = is_string( $t ) ? $t : null;
			}
			$lc = $textures['LOOT_CONTAINERS_8X8_RENDERED'] ?? null;
			if ( is_array( $lc ) ) {
				$tx = $lc['Texture'] ?? $lc['texture'] ?? null;
				$this->lootTextureAssetId = PqRobloxWikiTexture::parseAssetIdFromTextureString(
					is_string( $tx ) ? $tx : null
				);
			}
		}
	}

	public static function instance(): self {
		if ( self::$instance === null ) {
			self::$instance = new self();
		}
		return self::$instance;
	}

	/**
	 * @param array<int, array<string, mixed>> $byId
	 * @return array<int, string>
	 */
	private static function buildTitles( array $byId, string $fallbackPrefix ): array {
		$used = [];
		$out = [];
		foreach ( $byId as $pk => $row ) {
			$fb = $fallbackPrefix . ' ' . $pk;
			$name = $row['Name'] ?? '';
			$out[$pk] = self::claimUniqueTitle( is_string( $name ) ? $name : '', $fb, $pk, $used );
		}
		return $out;
	}

	private static function cleanTitle( ?string $name, string $fallback ): string {
		$raw = trim( (string)$name );
		if ( $raw === '' ) {
			return $fallback;
		}
		$t = preg_replace( '/[#<>\[\]|{}]/', '', $raw );
		$t = preg_replace( '/\s+/', ' ', (string)$t );
		$t = trim( (string)$t );
		if ( $t === '' || preg_match( '/^[\?\s\-_\.]+$/', $t ) ) {
			return $fallback;
		}
		return $t;
	}

	/**
	 * @param array<string, true> $used
	 */
	private static function claimUniqueTitle( string $name, string $fallbackTitle, int $pk, array &$used ): string {
		$base = self::cleanTitle( $name, $fallbackTitle );
		if ( !isset( $used[$base] ) ) {
			$used[$base] = true;
			return $base;
		}
		$candidate = "$base ($pk)";
		if ( !isset( $used[$candidate] ) ) {
			$used[$candidate] = true;
			return $candidate;
		}
		$n = 2;
		while ( true ) {
			$c = "$base ($pk-$n)";
			if ( !isset( $used[$c] ) ) {
				$used[$c] = true;
				return $c;
			}
			$n++;
		}
	}

	public function getItemPageTitle( int $id ): string {
		return $this->itemTitleById[$id] ?? ( 'Item ' . $id );
	}

	public function getSkinPageTitle( int $id ): string {
		return $this->skinTitleById[$id] ?? ( 'Skin ' . $id );
	}

	public function getBadgePageTitle( int $id ): string {
		return $this->badgeTitleById[$id] ?? ( 'Badge ' . $id );
	}

	public function getAchievementPageTitle( int $id ): string {
		return $this->achievementTitleById[$id] ?? ( 'Achievement ' . $id );
	}

	public function getEntityPageTitle( int $id ): string {
		return $this->entityTitleById[$id] ?? ( 'Entity ' . $id );
	}

	public function getAccountStatPageTitle( int $id ): string {
		return $this->accountStatTitleById[$id] ?? ( 'Account Stat ' . $id );
	}

	public function getItemRow( int $id ): ?array {
		return $this->itemsById[$id] ?? null;
	}

	public function getSkinRow( int $id ): ?array {
		return $this->skinsById[$id] ?? null;
	}

	/**
	 * @return array<string, mixed>|null
	 */
	public function getBadgeRow( int $id ): ?array {
		return $this->badgesById[$id] ?? null;
	}

	/**
	 * @return array<string, mixed>|null
	 */
	public function getAchievementRow( int $id ): ?array {
		return $this->achievementsById[$id] ?? null;
	}

	public function getMaxPossibleHonor(): float {
		return $this->maxAttainableHonorPoints;
	}

	/** Same as game: Achievement.MaxAttainableHonorPoints (falls back to root MaxPossibleHonor). */
	public function getMaxAttainableHonorPoints(): float {
		return $this->maxAttainableHonorPoints;
	}

	/**
	 * Match game honor tier: normalized = (honor / MaxAttainableHonorPoints) * 100, then find HonorRanges
	 * rank where Min <= normalized <= Max (inclusive). Iteration order is ascending Min so shared
	 * boundaries (e.g. 5 in [0,5] and [5,10]) resolve to the lower rank first. Default: bronze (0).
	 *
	 * @param float $normalizedPercent Same as Lua `normalized` (0–100 scale).
	 */
	public function rankIdFromHonorPercent( float $normalizedPercent ): int {
		if ( $this->honorRangesByRank === [] ) {
			return 0;
		}
		foreach ( $this->honorRankOrder as $rid ) {
			$r = $this->honorRangesByRank[$rid] ?? null;
			if ( !is_array( $r ) ) {
				continue;
			}
			$min = (float)( $r['min'] ?? 0 );
			$max = (float)( $r['max'] ?? 100 );
			if ( $normalizedPercent >= $min && $normalizedPercent <= $max ) {
				return $rid;
			}
		}
		return 0;
	}

	public function getHonorDisplayNameForRankId( int $rankId ): string {
		$k = (string)$rankId;
		return $this->honorToName[$k] ?? ( 'Honor ' . $rankId );
	}

	/** @return int[] */
	public function getAllBadgeIdsOrdered(): array {
		return $this->allBadgeIdsOrdered;
	}

	/**
	 * Wiki file for uploaded badge sprite (bot: badge_{slug}_{id}.png).
	 */
	public function getBadgeWikiIconUrl( int $id ): ?string {
		if ( $id <= 0 ) {
			return null;
		}
		$row = $this->badgesById[$id] ?? null;
		if ( !$row ) {
			return null;
		}
		$n = is_string( $row['Name'] ?? null ) ? $row['Name'] : ( 'Badge ' . $id );
		$base = PqRobloxTextureNames::badgeSpriteBase( $id, $n );
		return PqRobloxWikiFileUrl::forFilename( $base . '.png' );
	}

	public function getAccountStatRow( int $id ): ?array {
		return $this->accountStatsById[$id] ?? null;
	}

	/**
	 * @return array<int, array<string, mixed>>
	 */
	public function getAllAccountStatsOrdered(): array {
		if ( $this->accountStatsById === [] ) {
			return [];
		}
		$rows = $this->accountStatsById;
		ksort( $rows, SORT_NUMERIC );
		return $rows;
	}

	/**
	 * Generic "Skin" item (metadata holds appearance via rid) — bot/shared.py DropType Item Value "Skin".
	 */
	public function isSkinItem( int $itemId ): bool {
		if ( $itemId <= 0 ) {
			return false;
		}
		$row = $this->itemsById[$itemId] ?? null;
		if ( !$row ) {
			return false;
		}
		$hier = $row['TypeHierarchy'] ?? null;
		if ( is_array( $hier ) ) {
			foreach ( $hier as $h ) {
				if ( strcasecmp( (string)$h, 'Skin' ) === 0 ) {
					return true;
				}
			}
		}
		$name = $row['Name'] ?? '';
		return is_string( $name ) && strcasecmp( trim( $name ), 'Skin' ) === 0;
	}

	public function getItemDropTierType( int $itemId ): int {
		$row = $this->itemsById[$itemId] ?? null;
		if ( !$row ) {
			return 0;
		}
		return (int)( $row['DropTierType'] ?? 0 );
	}

	/**
	 * When false, UI should not show stack quantity (datadump Items).
	 */
	public function isItemStackable( int $itemId ): bool {
		if ( $itemId <= 0 ) {
			return false;
		}
		$row = $this->itemsById[$itemId] ?? null;
		if ( !$row ) {
			return true;
		}
		if ( array_key_exists( 'IsStackable', $row ) ) {
			return (bool)$row['IsStackable'];
		}
		if ( array_key_exists( 'isStackable', $row ) ) {
			return (bool)$row['isStackable'];
		}
		return true;
	}

	/**
	 * Wiki URL for bag/chest tier crop (drop_chest_{tier}.png / drop_bag_{tier}.png).
	 *
	 * @param 'chest'|'bag' $kind
	 */
	public function getLootTierIconUrl( int $tier, string $kind = 'chest' ): ?string {
		if ( $this->lootTextureAssetId === null || $tier < 0 ) {
			return null;
		}
		$base = PqRobloxTextureNames::lootDropBase( $kind, $tier );
		return PqRobloxWikiFileUrl::forFilename( $base . '.png' );
	}

	/** skin_rarity_{0..4}.{png|gif} */
	public function getSkinRarityIconUrl( int $rarity ): ?string {
		$r = max( 0, min( 4, $rarity ) );
		$ext = ( $r <= 1 ) ? 'png' : 'gif';
		$base = PqRobloxTextureNames::skinRarityBase( $r );
		return PqRobloxWikiFileUrl::forFilename( $base . '.' . $ext );
	}

	/** @return int[] */
	public function getAllSkinIdsOrdered(): array {
		return $this->allSkinIdsOrdered;
	}

	/**
	 * @return array<string, mixed>|null
	 */
	public function getSpriteForItem( int $id ): ?array {
		$row = $this->itemsById[$id] ?? null;
		if ( !$row ) {
			return null;
		}
		$s = $row['Sprite'] ?? $row['sprite'] ?? null;
		return is_array( $s ) ? $s : null;
	}

	/**
	 * Main item icon URL (Items[].Sprite). Logs once per item id per request when tier/icon works but main file is missing.
	 */
	public function getItemTextureWikiUrl( int $itemId ): ?string {
		if ( $itemId <= 0 ) {
			return null;
		}
		$row = $this->itemsById[$itemId] ?? null;
		if ( !$row ) {
			return null;
		}
		$sprite = $this->getSpriteForItem( $itemId );
		if ( $sprite === null ) {
			if ( !isset( $this->loggedMissingItemTexture[$itemId] ) ) {
				$this->loggedMissingItemTexture[$itemId] = true;
				$name = $row['Name'] ?? '';
				$keys = array_keys( $row );
				sort( $keys, SORT_STRING );
				wfDebugLog(
					'pqroblox',
					'[Sprite] item_id=' . $itemId
					. ' name=' . ( is_string( $name ) ? $name : '' )
					. ' reason=no_Sprite_dict row_keys=' . implode( ',', $keys )
				);
			}
			return null;
		}
		$iname = is_string( $row['Name'] ?? null ) ? $row['Name'] : ( 'Item ' . $itemId );
		$url = PqRobloxWikiTexture::wikiUrlForItemMainSprite( $itemId, $iname, $sprite );
		if ( $url !== null ) {
			return $url;
		}
		if ( !isset( $this->loggedMissingItemTexture[$itemId] ) ) {
			$this->loggedMissingItemTexture[$itemId] = true;
			$name = $row['Name'] ?? '';
			$tierOk = false;
			$ti = $row['TierIcon'] ?? null;
			if ( is_array( $ti ) ) {
				$tierOk = self::textureUrlFromSprite( $ti ) !== null;
			}
			wfDebugLog(
				'pqroblox',
				'[Sprite] item_id=' . $itemId
				. ' name=' . ( is_string( $name ) ? $name : '' )
				. ' reason=wiki_file_missing_for_computed_hash'
				. ' tier_icon_file_ok=' . ( $tierOk ? '1' : '0' )
				. ' ' . PqRobloxWikiTexture::spriteLookupDiagnostics( $sprite )
			);
		}
		return null;
	}

	/**
	 * Optional tier corner sprite from item row (bot-imported `TierIcon`), same wiki URL rules as textures.
	 */
	public function getItemTierIconWikiUrl( int $itemId ): ?string {
		$row = $this->itemsById[$itemId] ?? null;
		if ( !$row ) {
			return null;
		}
		$ti = $row['TierIcon'] ?? null;
		return is_array( $ti ) ? PqRobloxWikiTexture::wikiUrlForTierIconSprite( $ti ) : null;
	}

	/**
	 * @return array<string, mixed>|null
	 */
	public function getSpriteForSkin( int $id ): ?array {
		$row = $this->skinsById[$id] ?? null;
		if ( !$row ) {
			return null;
		}
		$s = $row['Sprite'] ?? null;
		return is_array( $s ) ? $s : null;
	}

	/**
	 * Profile skin grid: prefer wiki e_idle animation GIF (see skin_renderer.py), else rendered Sprite texture.
	 */
	public function getSkinGridIconUrl( int $id ): ?string {
		$row = $this->skinsById[$id] ?? null;
		$name = is_array( $row ) ? (string)( $row['Name'] ?? ( 'Skin ' . $id ) ) : ( 'Skin ' . $id );
		$url = PqRobloxWikiTexture::wikiUrlForSkinAnimation( $id, $name, 'e_idle' );
		if ( $url !== null ) {
			return $url;
		}

		// Debug why skins show "—" in profile UI.
		$eIdleFile = PqRobloxTextureNames::skinAnimationBase( $id, $name, 'e_idle' ) . '.gif';
		$eIdleExists = PqRobloxWikiFileUrl::forFilename( $eIdleFile ) !== null;

		$sprite = $this->getSpriteForSkin( $id );
		if ( $sprite === null ) {
			wfDebugLog(
				'pqroblox',
				'[SkinGrid] skin_id=' . $id
				. ' name=' . $name
				. ' e_idle_file=' . $eIdleFile
				. ' e_idle_exists=' . ( $eIdleExists ? '1' : '0' )
				. ' sprite=null'
			);
			return null;
		}

		$url2 = PqRobloxWikiTexture::wikiUrlForSkinSpritePreview( $id, $name, $sprite );
		if ( $url2 === null ) {
			$ext = PqRobloxWikiTexture::spriteOutputExtension( $sprite );
			$prevFile = PqRobloxTextureNames::skinSpritePreviewBase( $id, $name ) . '.' . $ext;
			$prevExists = PqRobloxWikiFileUrl::forFilename( $prevFile ) !== null;
			wfDebugLog(
				'pqroblox',
				'[SkinGrid] skin_id=' . $id
				. ' name=' . $name
				. ' e_idle_file=' . $eIdleFile
				. ' e_idle_exists=' . ( $eIdleExists ? '1' : '0' )
				. ' preview_file=' . $prevFile
				. ' preview_exists=' . ( $prevExists ? '1' : '0' )
				. ' ' . PqRobloxWikiTexture::spriteLookupDiagnostics( $sprite )
			);
		}
		return $url2;
	}

	/**
	 * URL for an uploaded wiki file (semantic or legacy PQ_tex hash).
	 *
	 * @param array<string, mixed>|null $sprite
	 */
	public static function textureUrlFromSprite( ?array $sprite ): ?string {
		if ( !$sprite ) {
			return null;
		}
		return PqRobloxWikiTexture::wikiUrlForSprite( $sprite );
	}

	/**
	 * Stat icon image (stat_{stat}.png).
	 */
	public function statIconHtmlForKey( string $statKey ): string {
		$norm = strtolower( trim( $statKey ) );
		if ( !isset( self::STAT_ICON_INDEX[$norm] ) ) {
			return '';
		}
		$label = ucfirst( $norm );
		$fname = PqRobloxTextureNames::statIconBase( $norm ) . '.png';
		$url = PqRobloxWikiFileUrl::forFilename( $fname );
		if ( $url === null ) {
			return '';
		}
		$urlEsc = htmlspecialchars( $url, ENT_QUOTES );
		$px = 18;
		return '<span class="pq-roblox-stat-ico"><img src="' . $urlEsc . '" alt="" title="'
			. htmlspecialchars( $label, ENT_QUOTES ) . '" width="' . $px
			. '" height="' . $px . '" class="pq-roblox-stat-ico-img" loading="lazy" /></span>';
	}
}
