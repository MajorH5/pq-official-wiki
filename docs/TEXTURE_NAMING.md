# Pixel Quest wiki texture filenames

Bot uploads and the MediaWiki `PixelQuestRoblox` extension resolve **the same semantic filenames** so editors can search the file namespace (e.g. `item_`, `skin_`, `tier_star`) instead of opaque `PQ_tex_<sha256>` hashes.

## Rules

- Lowercase, ASCII: letters, digits, `_`, `-`, `.` before extension.
- One canonical file per logical asset; re-import overwrites the same title.
- Legacy `PQ_tex_*` files may still exist on older wikis; the PHP extension tries **semantic names first**, then hash-based URLs where still implemented.

## Patterns

| Kind | Pattern | Example |
|------|---------|---------|
| Item main sprite | `item_{slug(name)}_{id}.{png\|gif}` | `item_forbidden-dagger_353.png` |
| Item tier corner (TierIcon strip) | `{tier_theme}.{png\|gif}` | `tier_star.png` — theme from **first animation frame row** in `Frames[0][1]`: `0→tier_star`, `2→tier_pixelween`, `8→tier_pixelmas`, `9→tier_gamemode`, `10→tier_corrupted`, else `tier_row_{n}` |
| Projectile | `projectile_px_{hash16}.{png\|gif}` | `projectile_px_a1b2c3d4e5f67890.png` — **`hash16`** = first 16 hex chars of SHA-256 of the **uploaded file bytes** (after GIF normalization). Same pixels ⇒ one file even if asset id / datadump JSON changes. Local cache still keys off a JSON signature (`projectile_tex_*` / `projectile_{hash12}`) to skip re-render. |
| Skin sheet preview | `skin_{slug}_{id}_sprite.{png\|gif}` | `skin_crusader_1_sprite.png` |
| Skin animation GIF | `skin_{slug}_{id}_{anim_key}.gif` | `skin_crusader_1_e_idle.gif` |
| Skin drop table idle PNG | `skin_{slug}_{id}_idle_preview.png` | `skin_crusader_1_idle_preview.png` |
| Loot UI (chest/bag cell) | `drop_chest_{tier}.png`, `drop_bag_{tier}.png` | `drop_chest_3.png` |
| Skin rarity | `skin_rarity_{0..4}.{png\|gif}` | `skin_rarity_2.gif` (Rare+ animated) |
| Valor icon | `valor_icon.png` | |
| Stat icon | `stat_{stat}.png` | `stat_attack.png` |
| Difficulty skull | `skull_difficulty.png` | |
| Status effect | `status_effect_{slug}.png` | `status_effect_bleeding.png` |
| Portal preview | `portal_{location_slug}.gif` | `portal_pirate-cove.gif` |
| Location minimap | `location_{location_slug}_minimap.{ext}` | |
| Location screenshot | `location_{location_slug}_screenshot_{i}.{ext}` | |
| Entity sprite | `entity_{slug}_{id}.{png\|gif}` | `entity_goblin_42.png` |

## Implementation

- Python: `bot/pq_wiki/texture_names.py`, uploads via `bot/pq_wiki/wiki_assets.py` (`ensure_file_uploaded`) and `bot/pq_wiki/texture_service.py`.
- PHP: `mediawiki/extensions/PixelQuestRoblox/includes/PqRobloxTextureNames.php`, URL resolution in `PqRobloxWikiTexture.php` and `Service/PqRobloxLookupIndex.php`.

## Migration

After deploying, run a full bot import so new filenames are uploaded. Old `PQ_tex_*` pages can be deleted or redirected over time.
