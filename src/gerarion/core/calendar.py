# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileCopyrightText: 2026 verared contributors
"""Núcleo del Calendario Gerarion — aritmética exacta de enteros.

Implementación de referencia de la Especificación Geroriana Universal (GUS) v2.1.0.
Sin dependencias externas. Sin aritmética de punto flotante en las rutas
normativas: el acumulador solar opera en microdías enteros, por lo que el
algoritmo es exacto y reproducible en cualquier plataforma y en cualquier
horizonte temporal.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# Constantes fundamentales (especificación GUS v2.1.0, sección 2)
# ---------------------------------------------------------------------------

#: Día Juliano (JDN) del origen: 1 Keuphero, año 0 DY = 21 de marzo de -5
#: (6 a.C., año astronómico -5). Ese día es Soludyia por definición.
ORIGIN_JDN = 1_719_313

#: Exceso solar anual por año común, en microdías exactos:
#: 365.24219 − 364 [días] → 1.24219 [días] → 1_242_190 [microdías].
SOLAR_DELTA_UD = 1_242_190

#: Umbral del acumulador solar que dispara un Gran Tempalum, en microdías.
SOLAR_THRESHOLD_UD = 7_000_000

#: Año común: 12 meses x 30 días + Tempalum de 4 días = 52 semanas exactas.
YEAR_COMMON_DAYS = 364

#: Año de Gran Tempalum: 12 meses x 30 días + Tempalum de 11 días
#: = 53 semanas exactas.
YEAR_GRAN_DAYS = 371

#: Días del bloque regular de meses (12 x 30). Todo año completo tiene
#: exactamente 360 días regulares; el Tempalum es el cierre del año.
MONTH_BLOCK_DAYS = 360

SECS_PER_DAY = 86_400

#: Precisión sub-segundo (GUS 3.0.0, precise sub-second): el instante sigue
#: siendo un entero de segundos (int64 conceptual); la fracción viaja en un
#: campo SEPARADO `nanos` (0..999_999_999) que NUNCA se fusiona con los
#: segundos en un único entero (preserva el horizonte ±292e9 años).
NANOS_MAX = 999_999_999


def validate_nanos(nanos: int) -> int:
    """Valida la fracción sub-segundo: entero en 0..999_999_999.

    Rechaza (no normaliza en silencio) negativos, >= 10^9, booleanos y
    no-enteros. Devuelve el valor validado.
    """
    if isinstance(nanos, bool) or not isinstance(nanos, int):
        raise GeroEinval(
            f"GERO_EINVAL: nanos debe ser un entero en 0..{NANOS_MAX}: {nanos!r}"
        )
    if not 0 <= nanos <= NANOS_MAX:
        raise GeroEinval(
            f"GERO_EINVAL: nanos fuera de rango 0..{NANOS_MAX}: {nanos}"
        )
    return nanos

#: Duración nominal del año tropical, en microdías. Constante declarativa de
#: la especificación (cálculo exacto no depende de ella, solo del acumulador).
TROPICAL_YEAR_UD = 365_242_190

# ---------------------------------------------------------------------------
# Nomenclatura (Nuvid). No normativa para el cómputo: el núcleo solo usa
# enteros. Los nombres habitan la capa de presentación.
# ---------------------------------------------------------------------------

MONTHS: Dict[int, Tuple[str, str]] = {
    0: ("Tempalum", "Mes de cierre y regulación"),
    1: ("Keuphero", "Aries · Equinoccio Norte"),
    2: ("Duphilus", "Tauro · Ascenso 2"),
    3: ("Tritom", "Géminis · Ascenso 3"),
    4: ("Andra", "Cáncer · Solsticio Norte"),
    5: ("Quintob", "Leo · Afelio"),
    6: ("Hexohan", "Virgo · Ecuatorial"),
    7: ("Barseti", "Libra · Equinoccio Sur"),
    8: ("Omary", "Escorpio · Meridión"),
    9: ("Novat", "Sagitario · Nuevo ciclo"),
    10: ("Deshimo", "Capricornio · Solsticio Sur"),
    11: ("Duitades", "Acuario · Perihelio"),
    12: ("Ichtys", "Piscis · Retorno Ecuatorial"),
}

WEEKDAYS: List[Tuple[str, str, str]] = [
    # (nuvid, abreviatura canónica, posición del ciclo de 7 días)
    ("Soludyia", "S", "día 1 del ciclo"),
    ("Loondyia", "L", "día 2 del ciclo"),
    ("Mardyia", "M", "día 3 del ciclo"),
    ("Aisterdyia", "A", "día 4 del ciclo"),
    ("Trustdyia", "T", "día 5 del ciclo"),
    ("Viendyia", "V", "día 6 del ciclo"),
    ("Sabatyeh", "B", "día 7 del ciclo"),
]

TEMPALUM_NORMAL_DAYS: Dict[int, str] = {
    1: "Unictis",
    2: "Kindom",
    3: "Iki",
    4: "Ikiyeh",
}

TEMPALUM_GRAN_DAYS: Dict[int, str] = {
    **TEMPALUM_NORMAL_DAYS,
    5: "Nuvivid I",
    6: "Nuvivid II",
    7: "Nuvivid III",
    8: "Nuvivid IV",
    9: "Nuvivid V",
    10: "Nuvivid VI",
    11: "Nuvivid VII",
}

DAY_SACRED: Dict[Tuple[int, int], str] = {
    (1, 12): "Cruxyphi",
    (1, 15): "Resinove",
    (1, 30): "Yeshuvid",
}


class GeroError(ValueError):
    """Error de dominio del sistema Gerarion."""


class GeroEinval(GeroError):
    """Fecha fuera de rango (mes o día inválido). Análogo a EINVAL."""


class GeroItemporal(GeroError):
    """Día Tempalum inválido para el tipo de año (ver spec GUS 2.1 §6)."""


# ---------------------------------------------------------------------------
# Acumulador solar — secuencia exacta de enteros
# ---------------------------------------------------------------------------

_gt_cache: Dict[int, bool] = {}


def is_gran_tempalum(year: int) -> bool:
    """True si el año Gerarion dado tiene Gran Tempalum (11 días de Tempalum).

    Regla simétrica y cerrada (spec GUS 2.1 §3), válida para todo entero
    `year` (era DY, era AY y año 0):

        r_y = ((year % U) + U) % U          # residuo euclidiano del año en [0, U)
        r   = (r_y * S) % U                 # acumulador solar en [0, U)
        es Gran Tempalum  <=>  r + S >= U

    con S = SOLAR_DELTA_UD y U = SOLAR_THRESHOLD_UD. Equivale bit a bit a la
    recurrencia iterativa `r(n) = (r(n-1) + S) mod U` para `year >= 0`
    (verificado contra el vector set `gus-normative-002`) y la extiende
    hacia el pasado con módulo euclidiano: la secuencia es infinita en
    ambas direcciones. Determinista, sin punto flotante, O(1).

    Ejemplos: los años DY con GT empiezan en 5, 11, 16, 22, ...; los AY
    en -1, -6, -12, -17, -23, -29, ... (0001AY es Gran Tempalum de 371
    días; su año comienza en day_index -371).
    """
    if year in _gt_cache:
        return _gt_cache[year]
    r_y = year % SOLAR_THRESHOLD_UD  # % de Python ya es euclidiano
    r = (r_y * SOLAR_DELTA_UD) % SOLAR_THRESHOLD_UD
    result = (r + SOLAR_DELTA_UD) >= SOLAR_THRESHOLD_UD
    _gt_cache[year] = result
    return result


def year_length(year: int) -> int:
    """Días del año Gerarion dado: 371 si Gran Tempalum, 364 si común.

    Simétrico: la regla vale para toda la recta entera (era DY y era AY).
    """
    return YEAR_GRAN_DAYS if is_gran_tempalum(year) else YEAR_COMMON_DAYS


def tempalum_days(year: int) -> int:
    return 11 if year_length(year) == YEAR_GRAN_DAYS else 4


# ---------------------------------------------------------------------------
# Conversión día índice <-> gregoriano (vía JDN, entera)
# ---------------------------------------------------------------------------

def jdn(year: int, month: int, day: int) -> int:
    """Día Juliano de una fecha del calendario gregoriano proleptico.

    Acepta años astronómicos negativos (6 a.C. = -5). División entera.
    """
    a = (14 - month) // 12
    y = year + 4800 - a
    m = month + 12 * a - 3
    return day + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32_045


def jdn_to_gregorian(j: int) -> Tuple[int, int, int]:
    """Inversa exacta de :func:`jdn` (algoritmo Richards)."""
    a = j + 68_569
    b = 4 * a // 146_097
    c = a - (146_097 * b + 3) // 4
    d = 4000 * (c + 1) // 1_461_001
    e = c - 1461 * d // 4 + 31
    f = 80 * e // 2447
    day = e - 2447 * f // 80
    g = f // 11
    month = f + 2 - 12 * g
    year = 100 * (b - 49) + d + g
    return year, month, day


def day_index_from_gregorian(year: int, month: int, day: int) -> int:
    """Índice del día: 0 = 1 Keuphero, año 0 DY. Negativo = era AY."""
    return jdn(year, month, day) - ORIGIN_JDN


def gregorian_from_day_index(day_index: int) -> Tuple[int, int, int]:
    return jdn_to_gregorian(ORIGIN_JDN + day_index)


# ---------------------------------------------------------------------------
# Aritmética de años Gerarions
# ---------------------------------------------------------------------------

def year_start_day_index(year: int) -> int:
    """Índice del día 1 Keuphero del año dado, O(1) y simétrico (spec §3).

    Con división piso (`q, r = divmod(year, U)`, `0 <= r < U`,
    euclidiana también para `year < 0`):

        gt_count = q * S + (r * S) // U        # años Gran Tempalum acumulados
        year_start_day_index = year * 364 + 7 * gt_count

    Para `year=0` da `0`; para `year=-1` da `-371` (0001AY es Gran
    Tempalum); para todo `year >= 0` coincide bit a bit con la suma
    iterativa de longitudes (`ver gus-normative-002`).
    """
    q, r = divmod(year, SOLAR_THRESHOLD_UD)
    gt_count = q * SOLAR_DELTA_UD + (r * SOLAR_DELTA_UD) // SOLAR_THRESHOLD_UD
    return year * YEAR_COMMON_DAYS + 7 * gt_count


def _locate(day_index: int) -> Tuple[int, int]:
    """(año, día_del_año) para un índice de día, 0-based dentro del año.

    Inversa simétrica (spec §3): estima el año con la longitud media
    exacta de año (`364 + 7*S/U` días, racional `D/U`) y corrige con
    `year_start_day_index`, que es monótona. La estimación usa división
    piso, idéntica en ambas eras; el error de la estimación es < 1 año,
    así que la corrección es O(1).
    """
    if day_index == 0:
        return 0, 0
    est = (day_index * SOLAR_THRESHOLD_UD) // (
        YEAR_COMMON_DAYS * SOLAR_THRESHOLD_UD + 7 * SOLAR_DELTA_UD
    )
    while year_start_day_index(est) > day_index:
        est -= 1
    while year_start_day_index(est + 1) <= day_index:
        est += 1
    return est, day_index - year_start_day_index(est)


# ---------------------------------------------------------------------------
# Fecha Geroriana
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GerarionDate:
    """Fecha Geroriana completa."""

    year: int        # año DY si >= 0, AY (valor absoluto en formato) si < 0
    month: int       # 0 = Tempalum, 1..12 = meses regulares
    day: int         # 1..30 (meses) o 1..4 / 1..11 (Tempalum)
    day_index: int   # días desde el origen; negativo en era AY

    @property
    def weekday_index(self) -> int:
        """0 = Soludyia ... 6 = Sabatyeh. Invariante global: idx = day_index %% 7."""
        return self.day_index % 7

    @property
    def weekday(self) -> Tuple[str, str]:
        nuvid, abbrev, _latin = WEEKDAYS[self.weekday_index]
        return nuvid, abbrev

    @property
    def is_gran_tempalum_year(self) -> bool:
        return year_length(self.year) == YEAR_GRAN_DAYS

    @property
    def in_tempalum(self) -> bool:
        return self.month == 0

    @property
    def sacred_day(self) -> str | None:
        return DAY_SACRED.get((self.month, self.day))

    @property
    def tempalum_name(self) -> str | None:
        if not self.in_tempalum:
            return None
        table = TEMPALUM_GRAN_DAYS if self.is_gran_tempalum_year else TEMPALUM_NORMAL_DAYS
        return table.get(self.day)

    def canonical(self) -> str:
        """Formato canónico de fecha: AAAAYY-MM-DD-X (especificación 4)."""
        era = "DY" if self.year >= 0 else "AY"
        yy = abs(self.year)
        _, abbrev = self.weekday
        return f"{yy:04d}{era}-{self.month:02d}-{self.day:02d}-{abbrev}"


def to_gerarion(day_index: int) -> GerarionDate:
    """Fecha Geroriana para un índice de día."""
    year, rest = _locate(day_index)
    if rest < MONTH_BLOCK_DAYS:
        month = rest // 30 + 1
        day = rest % 30 + 1
    else:
        month = 0
        day = rest - MONTH_BLOCK_DAYS + 1
    return GerarionDate(year=year, month=month, day=day, day_index=day_index)


def from_gerarion(year: int, month: int, day: int) -> GerarionDate:
    """Índice de día para una fecha Geroriana, con validación de rango.

    El argumento `year` se expresa en años DY/AY: valores >= 0 son DY,
    valores <= 0 son AY (el año 0 DY es el origen compartido de ambas eras).
    """
    year = int(year)
    if month == 0:
        max_day = tempalum_days(year)
        if day < 1 or day > max_day:
            kind = "es" if max_day == 11 else "no es"
            raise GeroItemporal(
                f"Tempalum día {day} inválido: el año {year} {kind} Gran Tempalum"
            )
    elif 1 <= month <= 12:
        if day < 1 or day > 30:
            raise GeroEinval(f"Día {day} fuera de rango 1..30 para el mes {month}")
    else:
        raise GeroEinval(f"Mes {month} fuera de rango 0..12")
    offset = (MONTH_BLOCK_DAYS if month == 0 else (month - 1) * 30) + (day - 1)
    return to_gerarion(year_start_day_index(year) + offset)


# ---------------------------------------------------------------------------
# Instante y ciclo temporal (SC / LC)
# ---------------------------------------------------------------------------


def cycle_of(hour: int) -> str:
    """Ciclo luminoso de una hora: SC (06:00-17:59) o LC (18:00-05:59)."""
    if not 0 <= hour <= 23:
        raise GeroEinval(f"Hora {hour} fuera de rango 0..23")
    return "SC" if 6 <= hour < 18 else "LC"


def instant_from_parts(
    day_index: int, hour: int = 0, minute: int = 0, second: int = 0,
    offset_seconds: int = 0,
) -> int:
    """Instante continuo TCJ (GUS 3.0.0, Cap 13.1): segundos desde el origen.

    instant = day_index * 86400 + h*3600 + m*60 + s - offset_seconds

    La hora HH:MM:SS es la hora civil del OBSERVADOR; ``offset_seconds``
    (TCJ±O en segundos, signo del campo) sitúa al observador respecto del
    marco TCJ (= TAI + 8 400 s). Con offset 0 la marca es TCJ+0 y la
    hora es la del meridiano de referencia. Rango del offset: ±24 h en
    múltiplos de 60 s. La escala no tiene segundos intercalares internos.
    """
    if not (0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
        raise GeroEinval("GERO_EINVAL: hora/minuto/segundo fuera de rango (00-23:59:59)")
    if not isinstance(offset_seconds, int) or offset_seconds % 60 or not (-86400 <= offset_seconds <= 86400):
        raise GeroEinval("GERO_EINVAL: TCJ±O fuera de rango o con segundos (mul. de 60, ±24 h)")
    return (
        day_index * SECS_PER_DAY + hour * 3600 + minute * 60 + second
        - offset_seconds
    )


def parts_from_instant(instant: int, offset_seconds: int = 0) -> Tuple[GerarionDate, int, int, int]:
    """Descompone un instante como lo vería el observador de TCJ±O.

    Suma ``offset_seconds`` (la hora civil del observador es su propia
    referencia) y descompone en (fecha, hora, minuto, segundo) de SU día;
    cada observador conserva su hora civil y su ciclo SC/LC.
    """
    if not isinstance(offset_seconds, int) or offset_seconds % 60 or not (-86400 <= offset_seconds <= 86400):
        raise GeroEinval("GERO_EINVAL: TCJ±O fuera de rango o con segundos (mul. de 60, ±24 h)")
    return instant_parts(instant + offset_seconds)


def instant_parts(instant: int) -> Tuple[GerarionDate, int, int, int]:
    """Descompone un instante en (fecha Geroriana, hora, minuto, segundo)."""
    day_index, rem = divmod(instant, SECS_PER_DAY)
    hour, rem = divmod(rem, 3600)
    minute, second = divmod(rem, 60)
    return to_gerarion(day_index), hour, minute, second


# ---------------------------------------------------------------------------
# Precisión sub-segundo (campo separado; la aritmética de segundos no cambia)
# ---------------------------------------------------------------------------

NANOS_PER_SECOND = 1_000_000_000


def instant_from_parts_nanos(
    day_index: int, hour: int = 0, minute: int = 0, second: int = 0,
    nanos: int = 0, offset_seconds: int = 0,
) -> Tuple[int, int]:
    """Constructor de instante con fracción: devuelve ``(instant, nanos)``.

    El par (segundos int64, nanos uint32) es la representación canónica de
    precisión sub-segundo; los segundos conservan la aritmética entera O(1)
    intacta y los nanos viajan SIEMPRE por separado, con validación
    estricta 0..999_999_999 (sin normalización silenciosa).
    """
    validate_nanos(nanos)
    instant = instant_from_parts(day_index, hour, minute, second, offset_seconds)
    return instant, nanos
