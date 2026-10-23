#!/usr/bin/env python3
"""Genera los assets gráficos de la ficha de Google Play que
``flutter_launcher_icons`` no cubre: el ícono de alta resolución
(512x512) y el gráfico destacado / *feature graphic* (1024x500).

Son recursos obligatorios en Play Console (Ficha principal de Play
Store → Gráficos) distintos del ícono de la app instalada en el
dispositivo (ese lo genera ``flutter_launcher_icons`` a partir de
``assets/icon/icon.png``, ver ``generate_icon_assets.py``).

Reutiliza el mismo estilo de marca (gota roja sobre fondo azul
degradado, definido en ``generate_icon_assets.py``) para que la ficha
de la tienda sea visualmente consistente con el ícono real de la app.

Salida: ``store_assets/`` en la raíz del proyecto.

Uso:
    python tool/generate_play_store_assets.py

Requiere Pillow y NumPy (ya presentes en el entorno de desarrollo,
igual que ``generate_icon_assets.py``).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_icon_assets import (  # noqa: E402  (import tras sys.path)
    BLUE_DARK,
    BLUE_LIGHT,
    WHITE,
    _vertical_gradient,
    build_drop_layer,
)

ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT_DIR / "store_assets"
SOURCE_ICON = ROOT_DIR / "assets" / "icon" / "icon.png"

# --- Ícono de alta resolución para la ficha ---
# Requisito de Play Console: PNG de 32 bits (con canal alfa), 512x512,
# máximo 1024 KB. ``icon.png`` ya es RGBA 1024x1024 totalmente opaco
# (mismo origen que usa `flutter_launcher_icons` para todas las
# plataformas), así que basta con reescalarlo.
PLAY_ICON_SIZE = 512
PLAY_ICON_MAX_BYTES = 1024 * 1024

# --- Gráfico destacado / feature graphic ---
# Requisito de Play Console: JPEG o PNG de 24 bits (sin canal alfa),
# exactamente 1024x500.
FEATURE_WIDTH = 1024
FEATURE_HEIGHT = 500
FEATURE_SUPERSAMPLE = 2  # Se renderiza a 2x y se reduce (antialiasing).

FONT_BOLD = Path(r"C:\Windows\Fonts\arialbd.ttf")
FONT_REGULAR = Path(r"C:\Windows\Fonts\arial.ttf")

APP_NAME = "Seguimiento Glucosa"
TAGLINE = "Glucosa, comidas, medicamentos y biometría en un solo lugar"


def generate_play_store_icon() -> None:
    """Reescala el ícono fuente de la app a 512x512 para la ficha."""
    source = Image.open(SOURCE_ICON).convert("RGBA")
    icon = source.resize((PLAY_ICON_SIZE, PLAY_ICON_SIZE), Image.LANCZOS)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / "play_store_icon_512.png"
    icon.save(path, optimize=True)
    size_kb = path.stat().st_size / 1024
    print(f"Generado {path} ({icon.size[0]}x{icon.size[1]}, {size_kb:.1f} KB)")
    if path.stat().st_size > PLAY_ICON_MAX_BYTES:
        raise SystemExit(
            f"ERROR: {path.name} supera el límite de 1024 KB de Play Console."
        )


def _build_rect_background(width: int, height: int) -> Image.Image:
    """Fondo rectangular con el mismo degradado azul vertical y la
    misma viñeta que ``build_background`` usa para el ícono circular,
    adaptado a un lienzo no cuadrado."""
    gradient = _vertical_gradient(height, BLUE_LIGHT, BLUE_DARK)
    # `_vertical_gradient` genera un cuadrado `height x height`;
    # se recorta/expande el ancho tomando solo la primera columna y
    # repitiéndola, ya que el degradado no varía horizontalmente.
    column = np.asarray(gradient, dtype=np.float32)[:, :1, :]
    array = np.tile(column, (1, width, 1))

    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    cx, cy = (width - 1) / 2, (height - 1) / 2
    norm = max(cx, cy) * 1.42
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / norm
    vignette = (1.0 - 0.35 * np.clip(dist, 0, 1) ** 2)[:, :, None]

    array = np.clip(array * vignette, 0, 255).astype(np.uint8)
    return Image.fromarray(array, mode="RGB")


def generate_feature_graphic() -> None:
    """Genera el banner 1024x500 (fondo de marca + gota + texto)."""
    work_w = FEATURE_WIDTH * FEATURE_SUPERSAMPLE
    work_h = FEATURE_HEIGHT * FEATURE_SUPERSAMPLE

    background = _build_rect_background(work_w, work_h).convert("RGBA")

    # Gota de marca a la izquierda, centrada verticalmente.
    drop_size = int(work_h * 0.90)
    drop = build_drop_layer(drop_size, drop_height_ratio=0.62)
    drop_x = int(work_w * 0.06)
    drop_y = (work_h - drop_size) // 2
    canvas = background.copy()
    canvas.alpha_composite(drop, dest=(drop_x, drop_y))

    draw = ImageDraw.Draw(canvas)
    text_x = drop_x + drop_size + int(work_w * 0.03)
    max_text_width = work_w - text_x - int(work_w * 0.04)

    # Reduce el tamaño del título hasta que quepa en el ancho
    # disponible: con el nombre completo de la app ("Seguimiento
    # Glucosa") un tamaño fijo grande se corta fuera del lienzo.
    title_size = int(work_h * 0.16)
    title_font = ImageFont.truetype(str(FONT_BOLD), title_size)
    title_bbox = draw.textbbox((0, 0), APP_NAME, font=title_font)
    while title_bbox[2] - title_bbox[0] > max_text_width and title_size > 10:
        title_size -= 2
        title_font = ImageFont.truetype(str(FONT_BOLD), title_size)
        title_bbox = draw.textbbox((0, 0), APP_NAME, font=title_font)
    title_h = title_bbox[3] - title_bbox[1]

    tagline_font = ImageFont.truetype(str(FONT_REGULAR), int(work_h * 0.075))

    # Envuelve el tagline en dos líneas si no cabe en el ancho
    # disponible, para no salirse del lienzo.
    words = TAGLINE.split(" ")
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), candidate, font=tagline_font)
        if bbox[2] - bbox[0] > max_text_width and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)

    tagline_line_h = draw.textbbox((0, 0), "Ag", font=tagline_font)[3]
    line_spacing = int(work_h * 0.02)
    block_h = title_h + line_spacing + len(lines) * (tagline_line_h + line_spacing)
    start_y = (work_h - block_h) // 2

    draw.text(
        (text_x, start_y),
        APP_NAME,
        font=title_font,
        fill=(*WHITE, 255),
    )
    y = start_y + title_h + line_spacing * 2
    for line in lines:
        draw.text((text_x, y), line, font=tagline_font, fill=(230, 238, 250, 255))
        y += tagline_line_h + line_spacing

    final = canvas.convert("RGB").resize(
        (FEATURE_WIDTH, FEATURE_HEIGHT), Image.LANCZOS
    )
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / "feature_graphic_1024x500.png"
    final.save(path, optimize=True)
    print(f"Generado {path} ({final.size[0]}x{final.size[1]})")


def main() -> None:
    generate_play_store_icon()
    generate_feature_graphic()


if __name__ == "__main__":
    main()
