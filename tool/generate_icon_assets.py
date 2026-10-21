#!/usr/bin/env python3
"""Genera los assets de icono/splash de Seguimiento Glucosa.

Produce, a partir de formas vectoriales descritas en código (sin depender
de ningún archivo binario externo), tres PNG en ``assets/icon/``:

- ``icon.png``: icono completo (gota de sangre roja sobre círculo azul,
  el símbolo universal de concienciación sobre la diabetes) para
  plataformas que no soportan icono adaptativo (iOS, web, Windows, macOS)
  y como *fallback* en Android.
- ``icon_background.png``: solo el fondo (gradiente azul), usado como
  capa de fondo del icono adaptativo de Android (API 26+).
- ``icon_foreground.png``: solo la gota roja sobre fondo transparente,
  centrada dentro de la "safe zone" (66 % central) que exige el icono
  adaptativo de Android, y reutilizada también como imagen del splash
  screen nativo (``flutter_native_splash``).

Uso:
    python tool/generate_icon_assets.py

Requiere Pillow y NumPy (ya presentes en el entorno de desarrollo).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

# Carpeta de salida: assets/icon/ en la raíz del proyecto Flutter.
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "assets" / "icon"

# Resolución de trabajo. Se renderiza a 4x y se reduce al final
# (supersampling) para obtener bordes suaves sin depender de ninguna
# librería de anti-aliasing adicional.
FINAL_SIZE = 1024
SUPERSAMPLE = 4
WORK_SIZE = FINAL_SIZE * SUPERSAMPLE

# Paleta: azul "concienciación de diabetes" + rojo "gota de sangre".
BLUE_LIGHT = (66, 165, 245)  # Colors.blue 400 aprox.
BLUE_DARK = (13, 71, 161)  # Colors.blue 900 aprox.
RED_LIGHT = (239, 83, 80)  # Colors.red 400 aprox.
RED_DARK = (183, 28, 28)  # Colors.red 900 aprox.
WHITE = (255, 255, 255)


def _cubic_bezier(
    p0: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
    steps: int,
) -> list[tuple[float, float]]:
    """Muestrea una curva de Bézier cúbica en ``steps`` puntos (incluye
    el punto final, excluye el inicial para poder encadenar segmentos
    sin duplicar vértices)."""
    points = []
    for i in range(1, steps + 1):
        t = i / steps
        mt = 1 - t
        x = (
            mt**3 * p0[0]
            + 3 * mt**2 * t * p1[0]
            + 3 * mt * t**2 * p2[0]
            + t**3 * p3[0]
        )
        y = (
            mt**3 * p0[1]
            + 3 * mt**2 * t * p1[1]
            + 3 * mt * t**2 * p2[1]
            + t**3 * p3[1]
        )
        points.append((x, y))
    return points


def _drop_polygon(center: tuple[float, float], height: float) -> list[tuple[float, float]]:
    """Devuelve el polígono (muy muestreado) de una gota de agua/sangre.

    Se basa en el path del icono Material Design "water_drop"
    (viewBox 24x24): M12,2 C12,2 6,9.5 6,14.5 C6,18 8.69,21 12,21
    C15.31,21 18,18 18,14.5 C18,9.5 12,2 12,2 Z, escalado y centrado en
    ``center`` para que ocupe ``height`` píxeles de alto.
    """
    # Puntos de control originales en el espacio 24x24 del icono fuente,
    # con origen arriba-izquierda (y crece hacia abajo).
    p_top = (12.0, 2.0)
    p_left = (6.0, 14.5)
    p_bottom = (12.0, 21.0)
    p_right = (18.0, 14.5)

    segments = [
        (p_top, (12.0, 2.0), (6.0, 9.5), p_left),
        (p_left, (6.0, 18.0), (8.69, 21.0), p_bottom),
        (p_bottom, (15.31, 21.0), (18.0, 18.0), p_right),
        (p_right, (18.0, 9.5), (12.0, 2.0), p_top),
    ]

    raw_points = [p_top]
    for p0, c1, c2, p3 in segments:
        raw_points.extend(_cubic_bezier(p0, c1, c2, p3, steps=80))

    # Escala: el path original mide 24 unidades de ancho y 19 de alto
    # (y entre 2 y 21). Se normaliza por altura para que el resultado
    # mida exactamente ``height`` píxeles, y se centra en ``center``.
    source_height = 21.0 - 2.0
    scale = height / source_height
    cx, cy = center
    # Centro geométrico del path fuente (en su propio espacio 24x24).
    source_cx, source_cy = 12.0, 2.0 + source_height / 2

    return [
        (cx + (x - source_cx) * scale, cy + (y - source_cy) * scale)
        for x, y in raw_points
    ]


def _vertical_gradient(
    size: int, top_color: tuple[int, int, int], bottom_color: tuple[int, int, int]
) -> Image.Image:
    """Crea un degradado vertical suave entre dos colores RGB."""
    # `t` varía por fila (eje Y); se le da forma (size, 1, 1) para que
    # broadcastee correctamente contra los colores (1, 1, 3) y produzca
    # una sola columna de alto `size` con los 3 canales ya interpolados,
    # antes de repetirla `size` veces a lo ancho.
    t = np.linspace(0.0, 1.0, size, dtype=np.float32).reshape(size, 1, 1)
    top = np.array(top_color, dtype=np.float32).reshape(1, 1, 3)
    bottom = np.array(bottom_color, dtype=np.float32).reshape(1, 1, 3)
    column = top + (bottom - top) * t  # shape (size, 1, 3)
    gradient = np.tile(column, (1, size, 1)).astype(np.uint8)  # (size, size, 3)
    return Image.fromarray(gradient, mode="RGB")


def _radial_vignette(size: int, strength: float = 0.35) -> np.ndarray:
    """Factor multiplicativo 0..1 que oscurece levemente las esquinas,
    para dar profundidad al fondo azul sin texturas adicionales."""
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    center = (size - 1) / 2
    dist = np.sqrt((xx - center) ** 2 + (yy - center) ** 2) / (center * 1.42)
    return 1.0 - strength * np.clip(dist, 0, 1) ** 2


def build_background(size: int) -> Image.Image:
    """Fondo circular con degradado azul y viñeta sutil (pensado para
    rellenar todo el lienzo cuadrado, incluida la capa de fondo del
    icono adaptativo de Android)."""
    gradient = _vertical_gradient(size, BLUE_LIGHT, BLUE_DARK)
    array = np.asarray(gradient, dtype=np.float32)
    vignette = _radial_vignette(size)[:, :, None]
    array = np.clip(array * vignette, 0, 255).astype(np.uint8)
    return Image.fromarray(array, mode="RGB")


def build_drop_layer(size: int, drop_height_ratio: float) -> Image.Image:
    """Capa RGBA con solo la gota roja (degradado + brillo), centrada
    y transparente alrededor, lista para componer sobre cualquier
    fondo o para usarse como icono adaptativo / imagen de splash."""
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))

    # Máscara de la silueta de la gota (para recortar el degradado).
    mask = Image.new("L", (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    polygon = _drop_polygon((size / 2, size / 2), size * drop_height_ratio)
    mask_draw.polygon(polygon, fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(radius=size * 0.0015))

    gradient = _vertical_gradient(size, RED_LIGHT, RED_DARK).convert("RGBA")
    layer = Image.composite(gradient, layer, mask)

    # Brillo especular (glossy highlight) arriba a la izquierda de la
    # gota, para que no se vea plana.
    highlight = Image.new("L", (size, size), 0)
    h_draw = ImageDraw.Draw(highlight)
    hw, hh = size * 0.11, size * 0.16
    hx = size / 2 - size * drop_height_ratio * 0.17
    hy = size / 2 - size * drop_height_ratio * 0.08
    h_draw.ellipse([hx - hw, hy - hh, hx + hw, hy + hh], fill=140)
    highlight = highlight.filter(ImageFilter.GaussianBlur(radius=size * 0.02))
    # El brillo solo debe verse dentro de la gota.
    highlight = Image.composite(highlight, Image.new("L", (size, size), 0), mask)

    white_layer = Image.new("RGBA", (size, size), (*WHITE, 0))
    white_layer.putalpha(highlight)
    layer = Image.alpha_composite(layer, white_layer)

    return layer


def render(size: int, drop_height_ratio: float, with_background: bool) -> Image.Image:
    drop = build_drop_layer(size, drop_height_ratio)
    if not with_background:
        return drop
    background = build_background(size).convert("RGBA")
    return Image.alpha_composite(background, drop)


def _save_downscaled(image: Image.Image, path: Path) -> None:
    final = image.resize((FINAL_SIZE, FINAL_SIZE), Image.LANCZOS)
    path.parent.mkdir(parents=True, exist_ok=True)
    final.save(path)
    print(f"Generado {path} ({final.size[0]}x{final.size[1]})")


def main() -> None:
    # Icono completo (gota + fondo azul), para iOS/web/Windows/macOS y
    # como fallback de Android.
    full_icon = render(WORK_SIZE, drop_height_ratio=0.60, with_background=True)
    _save_downscaled(full_icon, OUTPUT_DIR / "icon.png")

    # Fondo del icono adaptativo de Android (sin la gota).
    background_only = build_background(WORK_SIZE).convert("RGBA")
    _save_downscaled(background_only, OUTPUT_DIR / "icon_background.png")

    # Gota sobre transparente, dentro de la "safe zone" (66 %) del
    # icono adaptativo de Android; se reutiliza como imagen de splash.
    foreground = build_drop_layer(WORK_SIZE, drop_height_ratio=0.40)
    _save_downscaled(foreground, OUTPUT_DIR / "icon_foreground.png")


if __name__ == "__main__":
    main()
