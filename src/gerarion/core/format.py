# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileCopyrightText: 2026 verared contributors
"""Formato canónico de marca temporal Geroriana y normalización de entradas.

Implementa la especificación de formatos (spec GUS 3.0.0, §6 / Cap 13.1):

    Extendido:  AAAAYY-MM-DD-X-HH:MM:SS-CC-TCJ±O   (ej. TCJ+0, TCJ-2:20)
    Compacto:   AAAAYY-MM-DD-X-HHMMSS-CC-TCJ±O     (ej. TCJ0, TCJ+2, TCJ-220)

    Obligatorios:   AAAAYY-MM-DD-X          (fecha + letra de día Nuvid)
    Opcionales:     -HH:MM:SS-CC-TCJ±O      (hora, ciclo, offset temporal)

    Offset: el signo es OBLIGATORIO salvo el cero sin firmar (`TCJ+0` o
    `TCJ0`). Con minutos (TODO-004 cerrado, v3.0.0): `TCJ+H:MM` (ext.) /
    `TCJ±HMM` (comp., hora de 1 dígito + MM de 2, p. ej. `TCJ+540` = +05:40;
    hora ≥ 10 usa HHMM: `TCJ+1030` = +10:30).

Errores canónicos:
    GERO_EINVAL     campo fuera de rango o sintaxis inválida
    GERO_ETEMPALUM  día Tempalum inexistente para ese tipo de año
    GERO_EWEEK      letra de día Nuvid inconsistente con la calculada
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List

from . import calendar as cal
from .calendar import GeroEinval, GeroError, GeroItemporal

_DATE_PART = r"^(?P<year>\d{1,6})(?:(?P<era>DY|AY))?[-.](?P<month>\d{1,2})[-.](?P<day>\d{1,2})[-.](?P<weekday>[SLMATVBslmatvb])"

TIMESTAMP_RE = re.compile(
    _DATE_PART
    + r"(?:[-](?P<hour>\d{1,2}):(?P<minute>\d{1,2}):(?P<second>\d{1,2})"
    r"[-](?P<cycle>SC|LC|sc|lc)"
    r"[-]TCJ(?:(?P<offzero>0(?!\d))|(?P<offsign>[+\-])(?P<offh>\d{1,2})(?::(?P<offm>\d{2}))?))?$"
)

TIMESTAMP_COMPACT_RE = re.compile(
    _DATE_PART
    + r"(?:[-](?P<hour>\d{2})(?P<minute>\d{2})(?P<second>\d{2})"
    r"[-](?P<cycle>SC|LC|sc|lc)"
    r"[-]TCJ(?:0|(?P<coffsign>[+\-])(?P<coffdigits>\d{1,4})))?$"
)

WEEKDAY_LETTERS = {abbrev: idx for idx, (_, abbrev, _latin) in enumerate(cal.WEEKDAYS)}

CANONICAL_CTX = "GUS2-TS"


@dataclass
class ParsedTimestamp:
    """Marca temporal parseada y normalizada."""

    year: int            # años desde el origen (>= 0: DY; < 0: AY)
    month: int
    day: int
    weekday_index: int
    hour: int = 0
    minute: int = 0
    second: int = 0
    nanos: int = 0           # fracción sub-segundo 0..999_999_999 (campo separado)
    autocycle: bool = True   # ciclo inferido de la hora
    cycle: str | None = None  # si el emisor declaró SC/LC explícito
    offset: int = 0           # TCJ±O en horas (compatibilidad 2.x)
    offset_seconds: int = 0   # TCJ±O exacto en segundos (GUS 3.0.0)
    has_time: bool = False    # la marca trae hora completa
    compact: bool = False     # la entrada vino en formato compacto (29+ chars)
    flags: List[str] = field(default_factory=list)


def normalize(raw: str) -> str:
    """Normaliza una entrada a formato canónico sin validar el calendario."""
    s = raw.strip().upper().replace(" ", "-")
    s = s.replace(".", "-")
    return s


def parse(raw: str, *, strict_weekday: bool = False) -> ParsedTimestamp:
    """Parsea una marca temporal Geroriana aplicando las reglas 1-7.

    Las violaciones recuperables se reportan en `flags`; la letra de día
    calculada siempre prevalece sobre la declarada (REGLA 4). Con
    `strict_weekday=True` el conflicto eleva GERO_EWEEK en lugar de corregir.
    """
    # Fracción sub-segundo OPCIONAL (`.f{1,9}` entre el segundo y el ciclo):
    # se extrae del texto CRUDO (el normalizador convierte '.' en '-' y la
    # destruiría), se escala exacta a nanosegundos y se valida estricta.
    # La forma canónica NUNCA la emite (queda como dato de precisión).
    nanos = 0
    work = raw
    m_frac = re.search(r"\.(\d{1,9})(?=-[Ss][Cc]-|-[Ll][Cc]-|-[Tt][Cc][Jj])", raw)
    if m_frac:
        nanos = int(m_frac.group(1)) * 10 ** (9 - len(m_frac.group(1)))
        work = raw[: m_frac.start()] + raw[m_frac.end():]
    cleaned = normalize(work)
    m = TIMESTAMP_RE.match(cleaned)
    compact = False
    if not m:
        m = TIMESTAMP_COMPACT_RE.match(cleaned)
        compact = True
    if not m:
        raise GeroEinval(f"Sintaxis inválida: {raw!r}")
    flags: List[str] = []

    year = int(m.group("year"))
    era = m.group("era")
    if era is None:
        flags.append("era_assumed_DY")          # REGLA 3
        era = "DY"
    if era == "AY":
        year = -year
    elif year == 0 and "era_assumed_DY" in flags:
        pass

    month = int(m.group("month"))
    day = int(m.group("day"))
    declared = m.group("weekday").upper()

    # REGLA 5: Tempalum solo en años Gran Tempalum — la valida to_gerarion.
    try:
        gdate = cal.from_gerarion(year, month, day)
    except GeroItemporal:
        raise
    except GeroEinval:
        raise

    actual_idx = gdate.weekday_index
    if WEEKDAY_LETTERS[declared] != actual_idx:
        if strict_weekday:
            raise GeroError(
                f"GERO_EWEEK: letra declarada {declared} != calculada "
                f"{cal.WEEKDAYS[actual_idx][1]}"
            )
        flags.append("weekday_corrected")       # REGLA 4

    hour = minute = second = 0
    cycle: str | None = None
    offset = 0
    offset_seconds = 0
    if m.group("hour") is not None:
        hour, minute, second = (
            int(m.group("hour")),
            int(m.group("minute")),
            int(m.group("second")),
        )
        if hour > 23 or minute > 59 or second > 59:
            raise GeroEinval("Hora fuera de rango")
        cal.validate_nanos(nanos)  # defensa en profundidad: 0..999_999_999
        cycle = m.group("cycle").upper() if m.group("cycle") else None
        offset_seconds = _offset_seconds_from_match(m, compact)
        offset = offset_seconds // 3600 if offset_seconds % 3600 == 0 else 0
        if cycle is not None:
            expected = cal.cycle_of(hour)
            if cycle != expected:
                flags.append("cycle_corrected")  # REGLA 4 aplicada al ciclo
                cycle = expected
        else:
            cycle = cal.cycle_of(hour)

    return ParsedTimestamp(
        year=year,
        month=month,
        day=day,
        weekday_index=actual_idx,
        hour=hour,
        minute=minute,
        second=second,
        nanos=nanos,
        cycle=cycle,
        offset=offset,
        offset_seconds=offset_seconds,
        has_time=m.group("hour") is not None,
        compact=compact,
        flags=flags,
    )


def _offset_seconds_from_match(m: "re.Match", compact: bool) -> int:
    """Extrae el offset TCJ±O en segundos del match (extendido o compacto).

    Extendido: `TCJ0`, `TCJ+2`, `TCJ-2:20`, `TCJ+05:45`. Compacto: `TCJ0`,
    `TCJ+2`, `TCJ-220` (=−02:20), `TCJ+1030` (=+10:30). Rango ±23:59.
    """
    if compact:
        sign = m.group("coffsign")
        if sign is None:
            return 0  # TCJ0 exacto
        d = m.group("coffdigits")
        if len(d) <= 2:
            h, mi = int(d), 0
        elif len(d) == 3:
            h, mi = int(d[0]), int(d[1:])
        else:
            h, mi = int(d[:2]), int(d[2:])
    else:
        if m.group("offzero") is not None:
            return 0  # TCJ0 literal
        if m.group("offsign") is None or m.group("offh") is None:
            return 0
        sign = m.group("offsign")
        h, mi = int(m.group("offh")), int(m.group("offm") or 0)
    if h > 23 or mi > 59:
        raise GeroEinval(f"GERO_EINVAL: offset TCJ fuera de rango (±23:59): {h:02d}:{mi:02d}")
    val = h * 3600 + mi * 60
    return -val if sign == "-" else val


def quick_verify(raw: str) -> bool:
    """Verificación rápida de consistencia interna, O(1) y sin red.

    Comprueba sintaxis, rangos, letra Nuvid en modo estricto y ciclo exacto,
    y rechaza además cualquier corrección silenciosa (era asumida, ciclo
    declarado equivocado): la entrada debe ser válida tal cual, sin
    normalización que la rescate. Filtro barato para logs e IoT; no
    sustituye a `parse` + verificación de firma.
    """
    try:
        parsed = parse(raw, strict_weekday=True)
    except Exception:  # noqa: BLE001 - cualquier fallo = marca no verificada
        return False
    return not parsed.flags


def _format_offset(offset_seconds: int, compact: bool) -> str:
    """TCJ±O textual: `TCJ0`/`TCJ+2`/`TCJ-2:20` (ext.) o `TCJ±HMM` (comp.)."""
    if offset_seconds == 0:
        return "TCJ0" if compact else "TCJ+0"
    sign = "-" if offset_seconds < 0 else "+"
    total = abs(offset_seconds)
    h, rem = divmod(total, 3600)
    if rem:
        m = rem // 60
        if compact:
            if h < 10:
                return f"TCJ{sign}{h}{m:02d}"
            return f"TCJ{sign}{h:02d}{m:02d}"
        return f"TCJ{sign}{h}:{m:02d}"
    if compact:
        return f"TCJ{sign}{h}"
    return f"TCJ{sign}{h}" if h >= 10 else f"TCJ{sign}{h}"


def to_canonical(parsed: ParsedTimestamp) -> str:
    """Serializa a formato canónico extendido (GUS 3.0.0, Cap 13.1)."""
    era = "DY" if parsed.year >= 0 else "AY"
    yy = abs(parsed.year)
    date = cal.from_gerarion(parsed.year, parsed.month, parsed.day)
    _, abbrev = date.weekday
    base = f"{yy:04d}{era}-{parsed.month:02d}-{parsed.day:02d}-{abbrev}"
    if not parsed.has_time:
        return base
    cycle = parsed.cycle or cal.cycle_of(parsed.hour)
    return (
        f"{base}-{parsed.hour:02d}:{parsed.minute:02d}:{parsed.second:02d}"
        f"-{cycle}-{_format_offset(parsed.offset_seconds, compact=False)}"
    )


def to_compact(parsed: ParsedTimestamp) -> str:
    """Serializa a formato canónico compacto (29+ chars, Cap 13.1: HHMMSS)."""
    era = "DY" if parsed.year >= 0 else "AY"
    yy = abs(parsed.year)
    date = cal.from_gerarion(parsed.year, parsed.month, parsed.day)
    _, abbrev = date.weekday
    base = f"{yy:04d}{era}-{parsed.month:02d}-{parsed.day:02d}-{abbrev}"
    if not parsed.has_time:
        return base
    cycle = parsed.cycle or cal.cycle_of(parsed.hour)
    return (
        f"{base}-{parsed.hour:02d}{parsed.minute:02d}{parsed.second:02d}"
        f"-{cycle}-{_format_offset(parsed.offset_seconds, compact=True)}"
    )


def canonical_bytes(canon: str, instant: int, context: str = CANONICAL_CTX) -> bytes:
    """Bytes canónicos firmables: contexto || marca || instante.

    El contexto evita colisiones de dominio con otros usos del mismo hash.
    """
    return f"{context}\n{canon}\n{instant}\n".encode("utf-8")
