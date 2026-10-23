#!/usr/bin/env python3
"""Corrige la relación de aspecto de las capturas de pantalla de
``Capturas/`` para que cumplan el límite de Google Play Console.

Play Console rechaza capturas de teléfono cuyo lado largo supere el
doble del lado corto (relación de aspecto máxima 2:1). Las 7 capturas
tomadas en el dispositivo real son 1200x2664 px (≈2.22:1), por lo que
podrían ser rechazadas al subirlas (ver sección 6 de
``GOOGLE_PLAY_LISTING.md``).

En vez de recortar contenido (cada pantalla tiene botones/texto en
posiciones Y distintas, así que recortar arriba/abajo con un único
margen fijo cortaría contenido real en algunas capturas), este script
amplía el **ancho** del lienzo añadiendo relleno lateral: los bordes
izquierdo y derecho de estas capturas son fondo sólido sin contenido
(confirmado comparando columna 0 vs. columna 20 de cada fila), así que
se replica el píxel de borde de cada fila hacia afuera. El resultado
es una imagen más ancha, con el mismo contenido original intacto y
centrado, sin recortes ni distorsión.

Uso:
    python tool/fix_screenshot_aspect_ratio.py

Lee ``Capturas/screen_*.png`` (1200x2664) y escribe las versiones
corregidas (1332x2664, relación exacta 2:1) en ``Capturas/play_store/``
para no sobrescribir los originales ni las capturas que no son parte
de la ficha de Play Store (``Screenshot_1.png``, capturas de WhatsApp).

Requiere Pillow y NumPy (ya presentes en el entorno de desarrollo).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

ROOT_DIR = Path(__file__).resolve().parent.parent
SOURCE_DIR = ROOT_DIR / "Capturas"
OUTPUT_DIR = SOURCE_DIR / "play_store"

MAX_ASPECT_RATIO = 2.0  # Límite de Play Console (lado largo / lado corto).


def fix_aspect_ratio(path: Path) -> Path:
    """Ensancha ``path`` con relleno lateral hasta cumplir 2:1 y lo
    guarda en ``OUTPUT_DIR``. Devuelve la ruta del archivo generado."""
    image = Image.open(path).convert("RGB")
    array = np.asarray(image)
    height, width, _ = array.shape

    target_width = int(np.ceil(height / MAX_ASPECT_RATIO))
    if target_width <= width:
        # Ya cumple la relación de aspecto; se copia sin cambios.
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = OUTPUT_DIR / path.name
        image.save(out_path, optimize=True)
        return out_path

    pad_total = target_width - width
    pad_left = pad_total // 2
    pad_right = pad_total - pad_left

    # Relleno por replicación de borde: cada fila usa su propio color
    # de borde (el fondo tiene degradado vertical, no horizontal), así
    # que no se introduce ninguna costura visible.
    left_fill = np.repeat(array[:, :1, :], pad_left, axis=1)
    right_fill = np.repeat(array[:, -1:, :], pad_right, axis=1)
    padded = np.concatenate([left_fill, array, right_fill], axis=1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / path.name
    Image.fromarray(padded, mode="RGB").save(out_path, optimize=True)
    return out_path


def main() -> None:
    sources = sorted(SOURCE_DIR.glob("screen_*.png"))
    if not sources:
        raise SystemExit(f"No se encontraron capturas en {SOURCE_DIR}")

    for source in sources:
        out_path = fix_aspect_ratio(source)
        with Image.open(out_path) as result:
            w, h = result.size
        ratio = h / w
        print(f"{source.name} -> {out_path.relative_to(ROOT_DIR)} "
              f"({w}x{h}, relación {ratio:.3f}:1)")


if __name__ == "__main__":
    main()
