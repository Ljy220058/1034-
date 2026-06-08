from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from PIL import Image, ImageDraw, ImageFilter, ImageFont

router = APIRouter(prefix='/api/v1/activities', tags=['activities'])

_PNG_HEADER = b'\x89PNG\r\n\x1a\n'


def _resolve_photo_path(activity_id: int, member_id: int) -> Path | None:
    candidates = [
        Path(f'uploads/photos/activity_{activity_id}.jpg'),
        Path(f'uploads/photos/activity_{activity_id}.jpeg'),
        Path(f'uploads/photos/activity_{activity_id}.png'),
        Path(f'uploads/photos/activity_{activity_id}_{member_id}.jpg'),
        Path(f'uploads/photos/activity_{activity_id}_{member_id}.png'),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _load_logo_image() -> Image.Image:
    logo_path = Path('frontend/assets/logo.png')
    if logo_path.exists():
        return Image.open(logo_path).convert('RGBA')
    image = Image.new('RGBA', (120, 120), (255, 255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.ellipse((10, 10, 110, 110), fill=(67, 90, 120, 255))
    draw.text((38, 45), '1034', fill=(255, 255, 255, 255), font=ImageFont.load_default())
    return image


def _load_background_image(activity_id: int, member_id: int) -> Image.Image:
    photo_path = _resolve_photo_path(activity_id, member_id)
    if photo_path is not None:
        return Image.open(photo_path).convert('RGBA')
    image = Image.new('RGBA', (1200, 1600), (35, 43, 60, 255))
    draw = ImageDraw.Draw(image)
    for offset in range(0, 1600, 120):
        color = (45 + offset // 20, 58 + offset // 18, 82 + offset // 25, 255)
        draw.rectangle((0, offset, 1200, min(1600, offset + 120)), fill=color)
    return image


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf',
    ]
    for font_path in candidates:
        if Path(font_path).exists():
            return ImageFont.truetype(font_path, size=size)
    return ImageFont.load_default()


def _wrap_text(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    lines: list[str] = []
    current = ''
    for char in text:
        if len(current) >= max_chars and char != '\n':
            lines.append(current)
            current = ''
        if char == '\n':
            if current:
                lines.append(current)
                current = ''
            continue
        current += char
    if current:
        lines.append(current)
    return lines


def _format_date(value: str | None) -> str:
    if not value:
        return '日期待确认'
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return value
    return parsed.strftime('%Y年%m月%d日')


def _draw_card(activity: dict[str, Any], member: dict[str, Any]) -> bytes:
    canvas = Image.new('RGBA', (1200, 1600), (14, 18, 28, 255))
    background = _load_background_image(activity['id'], member['id']).resize((1200, 1600))
    background = background.filter(ImageFilter.GaussianBlur(radius=1.2))
    canvas.alpha_composite(background)

    overlay = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rounded_rectangle((60, 70, 1140, 1530), radius=46, fill=(8, 14, 24, 178))
    canvas.alpha_composite(overlay)

    draw = ImageDraw.Draw(canvas)
    title_font = _load_font(64)
    subtitle_font = _load_font(34)
    body_font = _load_font(30)
    small_font = _load_font(24)

    logo = _load_logo_image().resize((120, 120))
    canvas.alpha_composite(logo, (90, 100))

    draw.text((240, 110), '1034 跑团', fill=(255, 255, 255, 255), font=subtitle_font)
    draw.text((90, 250), activity['name'], fill=(255, 255, 255, 255), font=title_font)
    draw.text((90, 350), _format_date(activity.get('date')), fill=(220, 227, 241, 255), font=subtitle_font)

    metrics = [
        f"成员：{member['name']}",
        f"里程：{member.get('distance_km', 0):.1f} km",
        f"配速：{member.get('pace_min_per_km', 'N/A')} 分/公里",
    ]
    y_offset = 460
    for metric in metrics:
        draw.text((90, y_offset), metric, fill=(245, 248, 255, 255), font=body_font)
        y_offset += 58

    draw.rounded_rectangle((90, 680, 1110, 980), radius=34, fill=(255, 255, 255, 25))
    draw.text((130, 720), '活动分享卡片', fill=(255, 255, 255, 255), font=body_font)
    activity_lines = _wrap_text(activity.get('description', '一起跑起来。'), 18)
    current_y = 780
    for line in activity_lines[:5]:
        draw.text((130, current_y), line, fill=(220, 227, 241, 255), font=body_font)
        current_y += 48

    draw.rounded_rectangle((90, 1040, 1110, 1380), radius=34, fill=(0, 0, 0, 70))
    draw.text((130, 1085), '俱乐部徽标与活动照片叠层区域', fill=(255, 255, 255, 255), font=body_font)
    draw.text((130, 1145), '透明贴纸风格 · 服务端生成 PNG', fill=(210, 218, 232, 255), font=small_font)

    buffer = BytesIO()
    canvas.save(buffer, format='PNG')
    return buffer.getvalue()


@router.get('/{activity_id}/share-card')
def share_card(activity_id: int, member_id: int = Query(..., ge=1)) -> Response:
    activity = {
        'id': activity_id,
        'name': f'活动 {activity_id}',
        'date': '2026-06-09',
        'description': '活动分享卡片由服务端生成，适合社交传播与活动回顾。',
    }
    member = {
        'id': member_id,
        'name': f'成员 {member_id}',
        'distance_km': 12.5,
        'pace_min_per_km': 5.4,
    }
    png_bytes = _draw_card(activity, member)
    if not png_bytes.startswith(_PNG_HEADER):
        raise HTTPException(status_code=500, detail='分享卡片生成失败')
    return Response(content=png_bytes, media_type='image/png')