# Wiki layout templates (repo mirror)

These files are the **source of truth** for what should exist on the wiki as `Template:PQ Item`, `Template:PQ Entity`, and `Template:PQ Location`. The import bot **transcludes** them; article bodies are mostly `{{PQ Item|...}}` style calls with data parameters.

## When to update this folder

| You change… | Update… |
|-------------|---------|
| Parameter names or order in `template_invocation()` in `bot/pq_wiki/renderers/item_renderer.py` | `PQ_Item.wikitext` (and preloads) |
| Same for entities | `PQ_Entity.wikitext` |
| Same for locations | `PQ_Location.wikitext` |
| Section headings, `#if` blocks, Notes placement | The matching `.wikitext` file here |

After editing these files, **copy the contents into the wiki** (same page titles) so production matches the repo. Purge a sample page if changes do not show.

## Files

| File | Wiki page |
|------|-----------|
| `PQ_Item.wikitext` | `Template:PQ Item` |
| `PQ_Entity.wikitext` | `Template:PQ Entity` |
| `PQ_Location.wikitext` | `Template:PQ Location` |
| `PQ_Item_preload.wikitext` | `Template:PQ Item/preload` (optional) |
| `PQ_Entity_preload.wikitext` | `Template:PQ Entity/preload` (optional) |
| `PQ_Location_preload.wikitext` | `Template:PQ Location/preload` (optional) |

See also `../TEMPLATES.md` for install steps and editor-facing help.

**Sync to wiki:** `docker compose run --rm pqwikibot python -m pq_wiki import-templates`
