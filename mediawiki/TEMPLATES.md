# PQ wiki layout templates

Generated item, enemy, and location pages **transclude** these templates so you can change layout/CSS/wrappers in **one place**. After editing a template, use **purge** (or wait for cache) to see changes on all member pages.

**Developers:** Keep `mediawiki/wiki_templates/*.wikitext` in sync with the bot whenever you change `template_invocation()` or layout in `bot/pq_wiki/renderers/*_renderer.py`. See `mediawiki/wiki_templates/README.md` for the mapping, then paste updated wikitext into the wiki.

## What is “preload”?

**Preload** is a MediaWiki URL feature: when you open the editor with `?preload=Some/Page`, the **empty edit box is pre-filled** with that page’s wikitext. We use small pages like `Template:PQ Item/preload` so editors get a ready-made `{{PQ Item|...}}` skeleton instead of starting from scratch. It does **not** auto-apply on every new page; you use a link or bookmark that includes `preload=`.

## Auto-import templates from this repo

From the project root (with wiki up and bot credentials in `.env`):

```bash
docker compose run --rm pqwikibot python -m pq_wiki import-templates
```

Or locally, from `bot/` with `PYWIKIBOT_DIR` set:

```bash
cd bot && python -m pq_wiki import-templates
```

This reads `mediawiki/wiki_templates/*.wikitext` and creates/updates `Template:PQ Item`, `Template:PQ Entity`, `Template:PQ Location`, and the optional `/preload` subpages. The `pqwikibot` service mounts `./mediawiki/wiki_templates` and sets `WIKI_LAYOUT_TEMPLATES_DIR` (see `docker-compose.yml`).

## One-time setup (after clone or new wiki)

1. **Install ParserFunctions** (required for optional sections): rebuild the MediaWiki Docker image so `extensions/ParserFunctions` is present, then run:

   ```bash
   docker compose exec mediawiki php maintenance/update.php --quick
   ```

   `LocalSettings.php` already includes `wfLoadExtension( 'ParserFunctions' );`.

2. **Install layout templates** — either run **`python -m pq_wiki import-templates`** (see above) or manually copy from `mediawiki/wiki_templates/`:

   | Wiki page            | Source file                 |
   |----------------------|-----------------------------|
   | `Template:PQ Item`   | `PQ_Item.wikitext`          |
   | `Template:PQ Entity`| `PQ_Entity.wikitext`        |
   | `Template:PQ Location` | `PQ_Location.wikitext` |

3. **Re-run the bot import** (or let the next import run) so pages contain `{{PQ Item|...}}` / `{{PQ Entity|...}}` / `{{PQ Location|...}}`.

## How editors create a new page from a template

### Items

1. Create the article (e.g. `My Custom Item`).
2. Open the editor with **preload** (adjust host/path):

   `http://localhost:8080/wiki/My_Custom_Item?action=edit&preload=Template:PQ_Item/preload`

   If the preload page is named differently, use that title after `preload=`.

3. Source for the preload page: copy from `mediawiki/wiki_templates/PQ_Item_preload.wikitext`, save as **`Template:PQ Item/preload`** (subpage of the template).

4. Fill in parameters (`head`, `icon`, `information`, …). **Pipe characters** in values must be written as `{{!}}` (e.g. in wikitext tables or `[[File:...|40px]]`).

### Enemies / locations

Use the same idea: create `Template:PQ Entity/preload` and `Template:PQ Location/preload` with a minimal `{{PQ Entity|...}}` / `{{PQ Location|...}}` call, then link `?preload=Template:PQ_Entity/preload` (encode spaces as `_`).

## How updates propagate

- **Transclusion**: Each article stores only `{{PQ Item|...}}` with **parameters**. The **visual frame** (sections, headings, `#if` blocks) lives in `Template:PQ Item`. Editing that template updates **every** page that still uses it.
- **Data** (stats, images, tables) is still passed in parameters from the bot (or hand-filled). Changing a template does **not** change parameter *values*; it changes how they are shown.

## Troubleshooting

### Article shows raw `{{PQ Item|...}}` or “Template:PQ Item” instead of layout

MediaWiki only expands templates that **exist**. If `Template:PQ Item` was never created (or the title does not match exactly), the saved wikitext is shown **literally** or as a red link to the missing template.

**Check:**

1. Open **`Special:Version`** — **ParserFunctions** must be listed (required for `#if` in the templates). If missing, rebuild the MediaWiki image and run `maintenance/update.php`.
2. Open **`/wiki/Template:PQ_Item`** (or `Template:PQ Item`). The page must exist and contain the wikitext from `mediawiki/wiki_templates/PQ_Item.wikitext` (not the *article* body — that belongs on `Fire Claymore`, etc.).
3. Repeat for **`Template:PQ Entity`** and **`Template:PQ Location`**.
4. After creating templates, **purge** an item page (`?action=purge`) or wait for cache.

The import bot logs a **WARNING** if any of these three templates are missing.

**Do not** paste the bot’s `{{PQ Item|...}}` call into `Template:PQ Item`. The template page should only contain the **layout** (parameters like `{{{information|}}}`), while each **item article** stores the `{{PQ Item|information=...}}` invocation from the bot.

### Other

- **Blank page / raw `{{PQ Item`**: Same as above — create `Template:PQ Item` exactly (space in name: `PQ Item`).
- **`#if` not working**: ParserFunctions not installed or not loaded — run `update.php` and confirm `Special:Version` lists ParserFunctions.
- **Tables break inside a parameter**: The bot passes `|` as `{{!}}` in parameter values automatically.
