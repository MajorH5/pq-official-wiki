from __future__ import annotations

import hashlib
import io
import json
from typing import Any, Optional

from PIL import Image

from pq_wiki.roblox_assets import fetch_asset_bytes, parse_asset_id


def _g(obj: dict, *keys: str, default=None):
    for k in keys:
        if k in obj and obj[k] is not None:
            return obj[k]
    return default


def normalize_xy(obj: Optional[dict]) -> tuple[int, int]:
    if not obj:
        return 0, 0
    return int(_g(obj, "X", "x", default=0)), int(_g(obj, "Y", "y", default=0))


def get_texture_url(sprite: Optional[dict]) -> Optional[str]:
    if not sprite:
        return None
    return _g(sprite, "texture", "Texture")


def sprite_signature_for_hash(sprite: Any) -> str:
    """Stable JSON for hashing (sprite sheets + animation)."""
    return json.dumps(sprite, sort_keys=True, separators=(",", ":"))


def content_hash(signature: str) -> str:
    return hashlib.sha256(signature.encode("utf-8")).hexdigest()


def _crop_sheet(im: Image.Image, left: int, top: int, w: int, h: int) -> Image.Image:
    return im.crop((left, top, left + w, top + h))


# Chroma-key for GIF: fully transparent pixels become this RGB before palette quantization.
# Must be unlikely in game art (reserved for transparency index in GIF palette).
_GIF_TRANS_KEY = (255, 0, 255)


def _rgba_frames_to_transparent_gif(
    rgba_frames: list[Image.Image],
    duration_ms: int,
) -> bytes:
    """
    Encode animated GIF with binary transparency. Plain RGBA→GIF in Pillow often
    yields black backgrounds; we matte onto a key color then quantize with a shared
    palette so the key maps to one transparent index.
    """
    if not rgba_frames:
        raise ValueError("No frames")

    # Build one shared palette from all frames so colors stay stable.
    rgba_frames = [fr.convert("RGBA") for fr in rgba_frames]
    total_w = sum(fr.size[0] for fr in rgba_frames)
    max_h = max(fr.size[1] for fr in rgba_frames)
    combined = Image.new("RGBA", (total_w, max_h), (0, 0, 0, 0))
    x_off = 0
    for fr in rgba_frames:
        combined.paste(fr, (x_off, 0), fr)
        x_off += fr.size[0]

    combined_p = combined.convert("RGB").quantize(
        method=Image.Quantize.MEDIANCUT,
        dither=Image.Dither.NONE,
        colors=255,  # reserve 1 palette index for transparency
    )
    trans_idx = 255

    p_frames: list[Image.Image] = []
    for fr in rgba_frames:
        p = fr.convert("RGB").quantize(palette=combined_p, dither=Image.Dither.NONE)
        p_pixels = p.load()
        a_pixels = fr.split()[3].load()
        w, h = fr.size
        for yy in range(h):
            for xx in range(w):
                if a_pixels[xx, yy] < 128:
                    p_pixels[xx, yy] = trans_idx
        p.info["transparency"] = trans_idx
        p_frames.append(p)

    out = io.BytesIO()
    p_frames[0].save(
        out,
        format="GIF",
        save_all=True,
        append_images=p_frames[1:],
        duration=duration_ms,
        loop=0,
        disposal=2,
        transparency=trans_idx,
        optimize=False,
    )
    return out.getvalue()


def render_animation_to_gif_bytes(
    animation: dict,
    sheet: Image.Image,
    fps_scale: float = 1.0,
) -> bytes:
    size = animation.get("Size") or {}
    base = animation.get("Base") or {}
    fw = int(_g(size, "X", "x", default=1))
    fh = int(_g(size, "Y", "y", default=1))
    bx, by = normalize_xy(base)
    frames_spec = animation.get("Frames") or []
    fps = float(animation.get("Fps") or 10) * fps_scale
    duration_ms = max(20, int(1000 / fps)) if fps > 0 else 100

    frames: list[Image.Image] = []
    for cell in frames_spec:
        if not isinstance(cell, (list, tuple)) or len(cell) < 2:
            continue
        col, row = int(cell[0]), int(cell[1])
        left = bx + col * fw
        top = by + row * fh
        frames.append(_crop_sheet(sheet, left, top, fw, fh).convert("RGBA"))

    if not frames:
        raise ValueError("No frames in animation")

    return _rgba_frames_to_transparent_gif(frames, duration_ms)


def render_tier_icon_strip(sprite: dict, sheet: Image.Image) -> bytes:
    """TierIcon-style: Frames + ImageRectSize, optional Base."""
    size = sprite.get("ImageRectSize") or sprite.get("imageRectSize") or {}
    fw = int(_g(size, "X", "x", default=1))
    fh = int(_g(size, "Y", "y", default=1))
    base = sprite.get("Base") or {"X": 0, "Y": 0}
    bx, by = normalize_xy(base)
    frames_spec = sprite.get("Frames") or []
    imgs: list[Image.Image] = []
    for cell in frames_spec:
        if not isinstance(cell, (list, tuple)) or len(cell) < 2:
            continue
        col, row = int(cell[0]), int(cell[1])
        left = bx + col * fw
        top = by + row * fh
        imgs.append(_crop_sheet(sheet, left, top, fw, fh).convert("RGBA"))
    if not imgs:
        raise ValueError("TierIcon: no frames")
    if len(imgs) == 1:
        buf = io.BytesIO()
        imgs[0].save(buf, format="PNG")
        return buf.getvalue()
    return _rgba_frames_to_transparent_gif(imgs, 100)


def render_static_sprite(sprite: dict, sheet: Image.Image) -> bytes:
    off = sprite.get("imageRectOffset") or sprite.get("ImageRectOffset") or {}
    sz = sprite.get("imageRectSize") or sprite.get("ImageRectSize") or {}
    ox, oy = normalize_xy(off)
    w = int(_g(sz, "X", "x", default=1))
    h = int(_g(sz, "Y", "y", default=1))
    im = _crop_sheet(sheet, ox, oy, w, h).convert("RGBA")
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def render_projectile_sprite(proj_sprite: dict, sheet: Image.Image) -> bytes:
    anim = proj_sprite.get("Animation")
    if anim:
        return render_animation_to_gif_bytes(anim, sheet)
    return render_static_sprite(proj_sprite, sheet)


def projectile_sprite_to_bytes(proj_sprite: dict) -> tuple[bytes, str]:
    """ProjectileDescriptor.Sprite → PNG or GIF bytes."""
    tex = get_texture_url(proj_sprite)
    aid = parse_asset_id(tex or "")
    if not aid:
        raise ValueError("Projectile sprite missing texture")
    raw = fetch_asset_bytes(aid)
    sheet = Image.open(io.BytesIO(raw)).convert("RGBA")
    if proj_sprite.get("Animation"):
        # Requested: projectile GIFs should play at 50% speed.
        b = render_animation_to_gif_bytes(proj_sprite["Animation"], sheet, fps_scale=0.5)
        return b, "gif"
    b = render_static_sprite(proj_sprite, sheet)
    return b, "png"


def render_portal_animation_first_frame(portal_sprite: dict, which: str = "IdleAnimation") -> Optional[bytes]:
    """PortalSprite: use first frame of IdleAnimation (or Open) as PNG."""
    block = portal_sprite.get(which) or portal_sprite.get("OpenAnimation")
    if not block:
        return None
    tex = get_texture_url(portal_sprite)
    aid = parse_asset_id(tex or "")
    if not aid:
        return None
    sheet = Image.open(io.BytesIO(fetch_asset_bytes(aid))).convert("RGBA")
    size = block.get("Size") or {}
    base = block.get("Base") or {}
    fw = int(_g(size, "X", "x", default=1))
    fh = int(_g(size, "Y", "y", default=1))
    bx, by = normalize_xy(base)
    frames = block.get("Frames") or [[0, 0]]
    col, row = int(frames[0][0]), int(frames[0][1])
    left = bx + col * fw
    top = by + row * fh
    im = _crop_sheet(sheet, left, top, fw, fh).convert("RGBA")
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def render_sprite_object(sprite: dict) -> tuple[bytes, str]:
    """
    Returns (file_bytes, extension_without_dot).
    Handles static rects, Animation blocks, TierIcon-style Frames.
    """
    tex = get_texture_url(sprite)
    aid = parse_asset_id(tex or "")
    if not aid:
        raise ValueError("No texture URL in sprite")

    raw = fetch_asset_bytes(aid)
    sheet = Image.open(io.BytesIO(raw)).convert("RGBA")

    if sprite.get("Animation"):
        b = render_animation_to_gif_bytes(sprite["Animation"], sheet)
        return b, "gif"

    has_rect = sprite.get("imageRectOffset") or sprite.get("ImageRectOffset")
    if sprite.get("Frames") and not has_rect:
        b = render_tier_icon_strip(sprite, sheet)
        if b[:4] == b"\x89PNG":
            return b, "png"
        return b, "gif"

    b = render_static_sprite(sprite, sheet)
    return b, "png"


def portal_sprite_preview_bytes(portal: dict) -> Optional[tuple[bytes, str]]:
    """Returns PNG bytes for portal idle first frame."""
    tex = get_texture_url(portal)
    if not parse_asset_id(tex or ""):
        return None
    for key in ("IdleAnimation", "OpenAnimation"):
        b = render_portal_animation_first_frame(portal, key)
        if b:
            return b, "png"
    return None
