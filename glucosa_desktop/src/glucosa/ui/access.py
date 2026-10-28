"""Puerta de acceso local a la interfaz.

El servidor solo escucha en 127.0.0.1, pero cualquier proceso o usuario del mismo equipo podría
abrir ese puerto. Por eso cada ejecución del lanzador (``python -m glucosa``) genera un token
aleatorio que solo conocen el servidor (por variable de entorno, no por línea de comandos) y la
URL que abre el lanzador. Sin ese token la interfaz **no lee datos, no muestra nada y no importa
archivos**: ``require_access`` detiene la ejecución antes de tocar Firebase o la base local.

Falla cerrado: si el servidor se inicia sin token (p. ej. ``streamlit run`` directo) tampoco abre.
La misma idea sirve para el futuro contenedor de escritorio: basta con que cargue la URL con token.
"""

import hmac
import os
from collections.abc import Mapping
from enum import StrEnum

import streamlit as st

from glucosa.access_config import ENV_ACCESS_TOKEN, URL_TOKEN_PARAM

_GRANTED_KEY = "glucosa_acceso_concedido"


class AccessDecision(StrEnum):
    GRANTED = "granted"
    DENIED = "denied"
    NOT_CONFIGURED = "not_configured"


def decide_access(expected: str | None, provided: str | None) -> AccessDecision:
    """Compara en tiempo constante; sin token esperado nunca se concede."""
    if not expected:
        return AccessDecision.NOT_CONFIGURED
    if not provided:
        return AccessDecision.DENIED
    matches = hmac.compare_digest(expected.encode("utf-8"), provided.encode("utf-8"))
    return AccessDecision.GRANTED if matches else AccessDecision.DENIED


def _provided_token(params: Mapping[str, str]) -> str | None:
    value = params.get(URL_TOKEN_PARAM)
    return value if isinstance(value, str) else None


def require_access() -> None:
    """Detiene la página (``st.stop``) salvo que esta sesión del navegador presente el token."""
    if st.session_state.get(_GRANTED_KEY) is True:
        return
    decision = decide_access(os.environ.get(ENV_ACCESS_TOKEN), _provided_token(st.query_params))
    if decision is AccessDecision.GRANTED:
        st.session_state[_GRANTED_KEY] = True
        return
    if decision is AccessDecision.NOT_CONFIGURED:
        st.error(
            "Acceso bloqueado: la interfaz debe iniciarse con `python -m glucosa`, que protege "
            "el acceso local con un token."
        )
    else:
        st.error(
            "Acceso no autorizado a _glucosa. Abre la aplicación con `python -m glucosa` "
            "(usa un enlace propio de cada ejecución)."
        )
    st.stop()
