"""Patrón de identificadores de usuario de Firebase (se interpolan en rutas de la API)."""

import re

UID_PATTERN = re.compile(r"[A-Za-z0-9]{1,128}")


def is_valid_uid(value: object) -> bool:
    return isinstance(value, str) and UID_PATTERN.fullmatch(value) is not None
