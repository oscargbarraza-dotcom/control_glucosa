"""Formato de la exportación de LibreView (idioma español), verificado con un archivo real.

Estructura: opcionalmente una fila de metadatos (título, fecha de generación en UTC y
nombre del paciente), el encabezado de 21 columnas y una fila por registro. Las marcas
de hora de los datos son hora local del dispositivo (``dd-mm-aaaa hh:mm``, sin segundos).
"""

from glucosa.limits import GLUCOSE_RANGE

HEADER: tuple[str, ...] = (
    "Dispositivo",
    "Número de serie",
    "Marca de hora del dispositivo",
    "Tipo de registro",
    "Historial de glucosa mg/dL",
    "Escanear glucosa mg/dL",
    "Insulina de acción rápida no numérica",
    "Insulina de acción rápida (unidades)",
    "Alimento no numérico",
    "Carbohidratos (gramos)",
    "Carbohidratos (porciones)",
    "Insulina de acción prolongada no numérica",
    "Insulina de acción prolongada (unidades)",
    "Notas",
    "Banda de glucosa mg/dL",
    "Cetona mmol/L",
    "Insulina para la hora de la comida (unidades)",
    "Insulina de corrección (unidades)",
    "Insulina de cambio de usuario (unidades)",
    "Cetona histórica mmol/L",
    "Escanear cetona mmol/L",
)

COL_MODEL = 0
COL_SERIAL = 1
COL_TIMESTAMP = 2
COL_TYPE = 3
COL_HISTORIC = 4
COL_SCAN = 5

TYPE_HISTORIC = 0
TYPE_SCAN = 1
TYPE_FOOD = 5
TYPE_NOTE = 6

DATE_FORMAT = "%d-%m-%Y %H:%M"
PLAUSIBLE_YEARS = (2010, 2100)  # un typo de año no debe extender el período en silencio
MAX_FILE_BYTES = 25 * 1024 * 1024
MAX_DATA_ROWS = 1_000_000
MAX_STORED_INVALID_ROWS = 1000  # el resto solo se cuenta, por motivo
HEADER_SEARCH_ROWS = 3
MIN_HEADER_OVERLAP = 10  # coincidencias para considerar que es un encabezado «con diferencias»

PLAUSIBLE_GLUCOSE = GLUCOSE_RANGE  # (20, 600) mg/dL, el mismo rango que valida la app Android

REASON_LABELS: dict[str, str] = {
    "hi": "Valor «HI» (por encima del límite del sensor): no numérico, excluido",
    "lo": "Valor «LO» (por debajo del límite del sensor): no numérico, excluido",
    "valor_ausente": "Registro de glucosa sin valor",
    "valor_no_numerico": "Valor no numérico",
    "valor_no_entero": "Valor con decimales (se esperaban mg/dL enteros)",
    "fuera_de_rango_plausible": "Valor fuera del rango plausible (20–600 mg/dL)",
    "fecha_invalida": "Fecha u hora no interpretable (se esperaba dd-mm-aaaa hh:mm)",
    "tipo_invalido": "Tipo de registro no numérico",
    "columnas_inesperadas": "Número de columnas distinto del encabezado",
    "dispositivo_ausente": "Registro sin dispositivo o número de serie",
}
OTHER_EVENT_LABELS: dict[int, str] = {TYPE_FOOD: "alimento", TYPE_NOTE: "nota"}
