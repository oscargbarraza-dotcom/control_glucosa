"""Normalización básica de nombres de alimentos, solo para AGRUPAR.

Los alimentos son texto libre (sin catálogo ni identificador). La normalización es deliberadamente
mínima y predecible:

* minúsculas (``casefold``);
* sin tildes ni diéresis (``Plátano`` → ``platano``, ``Güisqui`` → ``guisqui``);
* espacios, tabulaciones y saltos colapsados en un único espacio y sin espacios en los extremos.

La **ñ se conserva** (es otra letra: ``piña`` ≠ ``pina``). No se unen sinónimos, plurales ni
signos de puntuación (``huevo`` ≠ ``huevos``, ``pan`` ≠ ``pan.``). El texto original nunca se
modifica: este valor se usa únicamente como clave de agrupación.
"""

import re
import unicodedata

_ENIE_MARK = "\u0001"  # marca temporal para que la ñ sobreviva a la descomposición
_WHITESPACE = re.compile(r"\s+")


def normalize_food_name(name: str) -> str:
    text = unicodedata.normalize("NFC", name).casefold().replace("ñ", _ENIE_MARK)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    return _WHITESPACE.sub(" ", text.replace(_ENIE_MARK, "ñ")).strip()
