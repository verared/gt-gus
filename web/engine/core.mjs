// SPDX-License-Identifier: MIT OR Apache-2.0
// SPDX-FileCopyrightText: 2026 verared contributors
/**
 * Núcleo GUS (dominio GUS+CALENDAR): port exacto de src/gerarion/core/ —
 * calendario AY/DY, formato canónico 32/29, quick_verify e instantes.
 * (División modular v3.2.0: el puente TCJ/TAI−UTC vive en tcj-tai.mjs.)
 *
 * Aritmética entera exacta (acumulador solar en microdías). BigInt solo donde
 * el rango lo exige (instantes): el resto cabe en Number con garantía de
 * exactitud entera (días e índices < 2^53).
 *
 * LÍMITES DE PLATAFORMA (GUS 3.0.0, Apéndice Matemático §E de la spec):
 *
 *   - `instant` (segundos): SIEMPRE BigInt — exacto en todo el rango
 *     int64 ±2^63 ≈ ±2.92e11 años (y más allá, hasta lo que permita la
 *     memoria; el contrato normativo es el rango int64).
 *   - Calendario / `day_index` / JDN: aritmética en Number. Exacta solo
 *     mientras cada valor intermedio quepa en Number.MAX_SAFE_INTEGER
 *     (2^53-1 = 9_007_199_254_740_991). Eso garantiza |day_index| ≤
 *     2^53-1 días ≈ ±2.465e13 años. Más allá los resultados PIERDEN
 *     dígitos bajos (la conversión BigInteger requeriría doble aritmética
 *     en todo el módulo y no forma parte del contrato 3.0.0).
 *   - Referencia C11: gus.h blinda con GERO_ERANGE los límites int64
 *     (±2.92e11 años para instant, ±2.52e16 para el calendario); Python
 *     (int arbitrario) es exacto y es la referencia.
 *
 * Misma matriz de vectores normativos que la suite de Python.
 */

export const ORIGIN_JDN = 1719313;
export const SOLAR_DELTA_UD = 1242190;
export const SOLAR_THRESHOLD_UD = 7000000;
export const MONTH_BLOCK_DAYS = 360;
export const SECS_PER_DAY = 86400;

// tercer elemento: posicion en el ciclo de 7 dias (NO dia civil)
export const WEEKDAYS = [
  ["Soludyia", "S", "día 1 del ciclo"],
  ["Loondyia", "L", "día 2 del ciclo"],
  ["Mardyia", "M", "día 3 del ciclo"],
  ["Aisterdyia", "A", "día 4 del ciclo"],
  ["Trustdyia", "T", "día 5 del ciclo"],
  ["Viendyia", "V", "día 6 del ciclo"],
  ["Sabatyeh", "B", "día 7 del ciclo"],
];

export const MONTHS = {
  0: ["Tempalum", "Cierre del año"],
  1: ["Keuphero", "Aries · Equinoccio Norte"],
  2: ["Duphilus", "Tauro · Ascenso 2"],
  3: ["Tritom", "Géminis · Ascenso 3"],
  4: ["Andra", "Cáncer · Solsticio Norte"],
  5: ["Quintob", "Leo · Afelio"],
  6: ["Hexohan", "Virgo · Ecuatorial"],
  7: ["Barseti", "Libra · Equinoccio Sur"],
  8: ["Omary", "Escorpio · Meridión"],
  9: ["Novat", "Sagitario · Nuevo ciclo"],
  10: ["Deshimo", "Capricornio · Solsticio Sur"],
  11: ["Duitades", "Acuario · Perihelio"],
  12: ["Ichtys", "Piscis · Retorno Ecuatorial"],
};

const GT_CACHE = new Map();

/**
 * Acumulador solar simétrico (spec GUS 2.1 §3), O(1), todo entero year.
 *
 *   r_y = ((year % U) + U) % U   // módulo euclidiano (JS trunca hacia 0)
 *   r   = (r_y * S) % U
 *   es Gran Tempalum <=> r + S >= U
 *
 * Igual bit a bit a la recurrencia iterativa para year >= 0 y extendida
 * hacia el pasado: los años AY con GT empiezan en -1, -6, -12, -17, ...
 */
export function isGranTempalum(year) {
  if (GT_CACHE.has(year)) return GT_CACHE.get(year);
  const rY = ((year % SOLAR_THRESHOLD_UD) + SOLAR_THRESHOLD_UD) % SOLAR_THRESHOLD_UD;
  const r = (rY * SOLAR_DELTA_UD) % SOLAR_THRESHOLD_UD;
  const isGt = r + SOLAR_DELTA_UD >= SOLAR_THRESHOLD_UD;
  GT_CACHE.set(year, isGt);
  return isGt;
}

export function yearLength(year) {
  return isGranTempalum(year) ? 371 : 364;
}

export function tempalumDays(year) {
  return yearLength(year) === 371 ? 11 : 4;
}

export function jdn(year, month, day) {
  const a = Math.floor((14 - month) / 12);
  const y = year + 4800 - a;
  const m = month + 12 * a - 3;
  return day + Math.floor((153 * m + 2) / 5) + 365 * y + Math.floor(y / 4) - Math.floor(y / 100) + Math.floor(y / 400) - 32045;
}

export function jdnToGregorian(j) {
  const a = j + 68569;
  const b = Math.floor((4 * a) / 146097);
  const c = a - Math.floor((146097 * b + 3) / 4);
  const d = Math.floor((4000 * (c + 1)) / 1461001);
  const e = c - Math.floor((1461 * d) / 4) + 31;
  const f = Math.floor((80 * e) / 2447);
  const day = e - Math.floor((2447 * f) / 80);
  const g = Math.floor(f / 11);
  const month = f + 2 - 12 * g;
  const year = 100 * (b - 49) + d + g;
  return [year, month, day];
}

export function dayIndexFromGregorian(year, month, day) {
  return jdn(year, month, day) - ORIGIN_JDN;
}

export function gregorianFromDayIndex(dayIndex) {
  // Mismo domínio exacto que toGerarion (jdnToGregorian multiplica por 4).
  if (!Number.isSafeInteger(dayIndex)) {
    throw new GeroError(`GERO_EINVAL: day_index ${dayIndex} fuera del rango exacto de Number (±2^53-1)`);
  }
  return jdnToGregorian(ORIGIN_JDN + dayIndex);
}

/**
 * Inicio del año Gerarion, O(1) y simétrico (spec GUS 2.1 §3):
 * con q = floor(year / U), r = year mod U (euclidiano):
 *   gt_count = q*S + floor(r*S / U)
 *   year_start_day_index = year*364 + 7*gt_count
 * ysi(0) = 0; ysi(-1) = -371 (0001AY es Gran Tempalum).
 */
export function yearStartDayIndex(year) {
  const q = Math.floor(year / SOLAR_THRESHOLD_UD);
  const r = year - q * SOLAR_THRESHOLD_UD;
  const gtCount = q * SOLAR_DELTA_UD + Math.floor((r * SOLAR_DELTA_UD) / SOLAR_THRESHOLD_UD);
  return year * 364 + 7 * gtCount;
}

export function toGerarion(dayIndex) {
  // Inversa simétrica (spec GUS 2.1 §3): estimación con la longitud media
  // exacta de año (364 + 7*S/U días) y corrección monotónica con
  // yearStartDayIndex O(1); usa la duración real de cada año (364 o 371)
  // en ambas eras.
  //
  // Domínio exacto (GUS 3.0.0, Apéndice Matemático §E): la aritmética es
  // Number; con |dayIndex| >= 2^53 la imprecisión rompe la convergencia
  // de los bucles de corrección (bucle indefinido / dígitos bajos
  // perdidos). Se rechaza con GERO_EINVAL — nunca se trata de "aproximar".
  if (!Number.isSafeInteger(dayIndex)) {
    throw new GeroError(`GERO_EINVAL: day_index ${dayIndex} fuera del rango exacto de Number (±2^53-1)`);
  }
  let year, rest;
  if (dayIndex === 0) {
    year = 0; rest = 0;
  } else {
    year = Math.floor((dayIndex * SOLAR_THRESHOLD_UD) / (364 * SOLAR_THRESHOLD_UD + 7 * SOLAR_DELTA_UD));
    while (yearStartDayIndex(year) > dayIndex) year--;
    while (yearStartDayIndex(year + 1) <= dayIndex) year++;
    rest = dayIndex - yearStartDayIndex(year);
  }
  let month, day;
  if (rest < MONTH_BLOCK_DAYS) {
    month = Math.floor(rest / 30) + 1;
    day = (rest % 30) + 1;
  } else {
    month = 0;
    day = rest - MONTH_BLOCK_DAYS + 1;
  }
  const weekdayIndex = ((dayIndex % 7) + 7) % 7;
  const wd = WEEKDAYS[weekdayIndex];
  return { year, month, day, dayIndex, weekdayIndex, weekday: wd[0], abbr: wd[1] };
}

export function fromGerarion(year, month, day) {
  // Domínio exacto: |year*371 + 7| debe caber en Number.MAX_SAFE_INTEGER;
  // con años mayores la estimación pierde dígitos bajos. Límite
  // conservador: floor((2^53-1)/380) años (yb la longitud máxima 371 más
  // margen para el Tempalum y las sumas intermedias).
  if (!Number.isSafeInteger(year) || Math.abs(year) > Math.floor((Number.MAX_SAFE_INTEGER - 7) / 380)) {
    throw new GeroError(`GERO_EINVAL: año ${year} fuera del rango exacto de Number (±2.37e13)`);
  }
  if (month === 0) {
    const max = tempalumDays(year);
    if (day < 1 || day > max) {
      const kind = max === 11 ? "es" : "no es";
      throw new GeroError(`GERO_ETEMPALUM: Tempalum día ${day} inválido: el año ${year} ${kind} Gran Tempalum`);
    }
  } else if (month >= 1 && month <= 12) {
    if (day < 1 || day > 30) throw new GeroError(`GERO_EINVAL: día ${day} fuera de rango 1..30`);
  } else {
    throw new GeroError(`GERO_EINVAL: mes ${month} fuera de rango 0..12`);
  }
  const offset = (month === 0 ? MONTH_BLOCK_DAYS : (month - 1) * 30) + (day - 1);
  return toGerarion(yearStartDayIndex(year) + offset);
}

export class GeroError extends Error {}

/*(mm) Formato canónico: AAAAYY-MM-DD-X[-HH:MM:SS-CC-TCJ±O] */
const TS_RE =
  /^(\d{1,6})(DY|AY)?[-.](\d{1,2})[-.](\d{1,2})[-.]([SLMATVB])(?:[-](\d{1,2}):(\d{1,2}):(\d{1,2})[-](SC|LC)[-]TCJ(?:0(?![0-9])|([+-])(\d{1,2})(?::(\d{2}))?))?$/;

/*(mm) Formato COMPACTO (Cap 13.1): AAAAYY-MM-DD-X-HHMMSS-CC-TCJ±O */
const TS_COMPACT_RE =
  /^(\d{1,6})(DY|AY)?[-.](\d{1,2})[-.](\d{1,2})[-.]([SLMATVB])(?:[-](\d{2})(\d{2})(\d{2})[-](SC|LC)[-]TCJ(?:0(?![0-9])|([+-])(\d{1,4})))?$/;

/** Normaliza: mayúsculas, separadores homogéneos (reglas 1, 6).
 * Reemplazo POR CARÁCTER (igual que la referencia Python): los espacios
 * múltiples producen '--' y quedan como sintaxis inválida (GERO_EINVAL);
 * colapsarlos cambiaría el veredicto sobre marcas doblemente malformadas. */
export function normalize(raw) {
  return raw.trim().toUpperCase().replace(/\s/g, "-").replace(/\./g, "-");
}

// ---------------------------------------------------------------------------
// Precisión sub-segundo (GUS 3.0.0): campo `nanos` SEPARADO del instante.
// El instante sigue siendo BigInt de segundos; la fracción viaja aparte
// (0..999_999_999) y NUNCA se fusiona con los segundos en un único entero
// (preserva el horizonte ±292e9 años). Validación estricta: los valores
// inválidos se rechazan, jamás se normalizan en silencio.
// ---------------------------------------------------------------------------

/** Límite superior de la fracción: 999_999_999 ns (menos de un segundo). */
export const NANOS_MAX = 999999999;

/** Valida la fracción sub-segundo; lanza GeroError si está fuera de rango. */
export function validateNanos(nanos) {
  if (!Number.isInteger(nanos) || nanos < 0 || nanos > NANOS_MAX) {
    throw new GeroError(
      `GERO_EINVAL: nanos fuera de rango 0..${NANOS_MAX}: ${nanos}`,
    );
  }
  return nanos;
}

/** Fracción decimal de entrada (1-9 dígitos) → nanosegundos exactos. */
export function nanosFromFraction(digits) {
  const s = String(digits);
  if (!/^\d{1,9}$/.test(s)) {
    throw new GeroError(
      `GERO_EINVAL: fracción sub-segundo inválida (1-9 dígitos): ${digits}`,
    );
  }
  return validateNanos(Number(s) * 10 ** (9 - s.length));
}

/** Constructor de instante con fracción: devuelve { instant, nanos }. */
export function instantFromPartsNanos(
  dayIndex,
  hour = 0,
  minute = 0,
  second = 0,
  nanos = 0,
  offsetSeconds = 0,
) {
  validateNanos(nanos);
  return {
    instant: instantFromParts(dayIndex, hour, minute, second, offsetSeconds),
    nanos,
  };
}

export function parse(raw, { strictWeekday = false } = {}) {
  // Fracción sub-segundo OPCIONAL (`.f{1,9}` entre el segundo y el ciclo):
  // se extrae del texto CRUDO (el normalizador convierte '.' en '-' y la
  // destruiría), se escala exacta a nanosegundos y se valida estricta.
  // La forma canónica NUNCA la emite (queda como dato de precisión).
  let nanos = 0;
  let work = String(raw);
  const mFraction = /\d\.(\d{1,9})(?=-SC-|-LC-|-TCJ)/i.exec(work);
  if (mFraction) {
    nanos = nanosFromFraction(mFraction[1]);
    work = work.slice(0, mFraction.index + 1) + work.slice(mFraction.index + mFraction[0].length);
  }
  const clean = normalize(work);
  let m = TS_RE.exec(clean);
  let compact = false;
  if (!m) { m = TS_COMPACT_RE.exec(clean); compact = true; }
  if (!m) throw new GeroError(`GERO_EINVAL: sintaxis inválida: ${raw}`);
  const flags = [];
  let year = parseInt(m[1], 10);
  let era = m[2];
  if (!era) {
    flags.push("era_assumed_DY");
    era = "DY";
  }
  if (era === "AY") year = -year;
  const month = parseInt(m[3], 10);
  const day = parseInt(m[4], 10);
  const declared = m[5];
  const gdate = fromGerarion(year, month, day);
  if (WEEKDAYS[gdate.weekdayIndex][1] !== declared) {
    if (strictWeekday) throw new GeroError(`GERO_EWEEK: letra declarada ${declared} != calculada ${WEEKDAYS[gdate.weekdayIndex][1]}`);
    flags.push("weekday_corrected");
  }
  let hour = 0, minute = 0, second = 0, cycle = null, offset = 0, offsetSeconds = 0;
  const gi = (i) => (m[i] !== undefined ? parseInt(m[i], 10) : null);
  if (m[6] !== undefined) {
    hour = parseInt(m[6], 10);
    minute = compact ? parseInt(m[7], 10) : gi(7);
    second = compact ? parseInt(m[8], 10) : gi(8);
    if (hour > 23 || minute > 59 || second > 59) throw new GeroError("GERO_EINVAL: hora fuera de rango");
    // offset TCJ±O con minutos (TODO-004, GUS 3.0.0): TCJ0 | ±H(H)[:MM] | ±HMM/±HHMM
    if (compact) {
      const sgn = m[10];
      if (sgn === undefined) offsetSeconds = 0;              // TCJ0
      else {
        const d = m[11];
        const [h, mi] = d.length <= 2 ? [parseInt(d, 10), 0]
          : d.length === 3 ? [parseInt(d[0], 10), parseInt(d.slice(1), 10)]
          : [parseInt(d.slice(0, 2), 10), parseInt(d.slice(2), 10)];
        if (h > 23 || mi > 59) throw new GeroError(`GERO_EINVAL: offset TCJ fuera de rango: TCJ${sgn}${d}`);
        offsetSeconds = (sgn === "-" ? -1 : 1) * (h * 3600 + mi * 60);
      }
    } else {
      if (m[10] === undefined || m[10] === "0") offsetSeconds = 0;   // sin offset / TCJ0 / TCJ+0
      else {
        const h = gi(11), mi = m[12] !== undefined ? parseInt(m[12], 10) : 0;
        if (h > 23 || mi > 59) throw new GeroError(`GERO_EINVAL: offset TCJ fuera de rango: TCJ${m[10]}${h}:${String(mi).padStart(2, "0")}`);
        offsetSeconds = (m[10] === "-" ? -1 : 1) * (h * 3600 + mi * 60);
      }
    }
    offset = offsetSeconds % 3600 === 0 && offsetSeconds !== 0 ? offsetSeconds / 3600 : 0;
    const expected = cycleOf(hour);
    const declaredCycle = compact ? m[9] : m[9];
    if (declaredCycle) {
      cycle = expected;
      if (declaredCycle !== expected) flags.push("cycle_corrected");
    } else {
      cycle = expected;
    }
  }
  return { ...gdate, hour, minute, second, nanos, cycle, offset, offsetSeconds, hasTime: m[6] !== undefined, compact, flags };
}

/** Verificación rápida de consistencia interna, O(1) y sin red (Cap 13.8 v1.2).
 *  true solo si la marca es válida tal cual, sin correcciones silenciosas
 *  (era asumida, letra Nuvid o ciclo declarados equivocados). Filtro barato
 *  para logs e IoT; no sustituye a parse + verificación de firma. */
export function quickVerify(raw) {
  try {
    const p = parse(raw, { strictWeekday: true });
    return p.flags.length === 0;
  } catch {
    return false;
  }
}

export function cycleOf(hour) {
  if (hour < 0 || hour > 23) throw new GeroError("GERO_EINVAL: hora fuera de rango 0..23");
  return hour >= 6 && hour < 18 ? "SC" : "LC";
}

/* TCJ±O textual — canónico SIEMPRE extendido (GUS 3.0.0): TCJ+0 / TCJ+2 / TCJ-2:20 */
export function formatOffset(offsetSeconds) {
  if (offsetSeconds === 0 || offsetSeconds === undefined) return "TCJ+0";
  const sign = offsetSeconds < 0 ? "-" : "+";
  const a = offsetSeconds < 0 ? -offsetSeconds : offsetSeconds;
  const h = Math.trunc(a / 3600), m = Math.trunc((a % 3600) / 60);
  return m ? `TCJ${sign}${h}:${String(m).padStart(2, "0")}` : `TCJ${sign}${h}`;
}

export function canonicalOf(d) {
  const era = d.year >= 0 ? "DY" : "AY";
  const yy = Math.abs(d.year);
  let base = `${String(yy).padStart(4, "0")}${era}-${String(d.month).padStart(2, "0")}-${String(d.day).padStart(2, "0")}-${d.abbr}`;
  const offSec = d.offsetSeconds !== undefined ? d.offsetSeconds
    : (d.offset !== undefined && d.offset !== 0 ? d.offset * 3600 : 0);
  if (d.cycle) {
    base += `-${String(d.hour).padStart(2, "0")}:${String(d.minute).padStart(2, "0")}:${String(d.second).padStart(2, "0")}-${d.cycle}-${formatOffset(offSec)}`;
  } else if (d.hasTime || (d.hour !== undefined && (d.hour || d.minute || d.second))) {
    const cyc = d.cycle || cycleOf(d.hour);
    base += `-${String(d.hour).padStart(2, "0")}:${String(d.minute).padStart(2, "0")}:${String(d.second).padStart(2, "0")}-${cyc}-${formatOffset(offSec)}`;
  }
  return base;
}

/** Formato COMPACTO (Cap 13.1): HHMMSS + TCJ0/TCJ±H/TCJ±HMM */
export function compactOf(d) {
  const era = d.year >= 0 ? "DY" : "AY";
  const yy = Math.abs(d.year);
  let base = `${String(yy).padStart(4, "0")}${era}-${String(d.month).padStart(2, "0")}-${String(d.day).padStart(2, "0")}-${d.abbr}`;
  const offSec = d.offsetSeconds !== undefined ? d.offsetSeconds
    : (d.offset !== undefined && d.offset !== 0 ? d.offset * 3600 : 0);
  const cyc = d.cycle || (d.hour !== undefined ? cycleOf(d.hour) : null);
  if (!cyc) return base;
  let tcj;
  if (offSec === 0) tcj = "TCJ0";
  else {
    const sign = offSec < 0 ? "-" : "+";
    const a = offSec < 0 ? -offSec : offSec;
    const h = Math.trunc(a / 3600), m = Math.trunc((a % 3600) / 60);
    tcj = m ? (h < 10 ? `TCJ${sign}${h}${String(m).padStart(2, "0")}` : `TCJ${sign}${h}${m}`) : `TCJ${sign}${h}`;
  }
  return `${base}-${String(d.hour).padStart(2, "0")}${String(d.minute).padStart(2, "0")}${String(d.second).padStart(2, "0")}-${cyc}-${tcj}`;
}

/**
 * Instante continuo TCJ (GUS 3.0.0, Cap 13.1, BigInt): sin segundos
 * intercalares internos.
 * instant = dayIndex*86400 + h*3600 + m*60 + s - offsetSeconds
 * (la hora HH:MM:SS es hora civil del OBSERVADOR; offsetSeconds = TCJ±O).
 */
export function instantFromParts(dayIndex, hour = 0, minute = 0, second = 0, offsetSeconds = 0) {
  if (!Number.isInteger(hour) || !Number.isInteger(minute) || !Number.isInteger(second) ||
      hour < 0 || hour > 23 || minute < 0 || minute > 59 || second < 0 || second > 59) {
    throw new GeroError("GERO_EINVAL: hora/minuto/segundo fuera de rango");
  }
  if (!Number.isInteger(offsetSeconds) || offsetSeconds % 60 !== 0 ||
      offsetSeconds < -86400 || offsetSeconds > 86400) {
    throw new GeroError("GERO_EINVAL: TCJ±O fuera de rango o con segundos (mul. de 60, ±24 h)");
  }
  return BigInt(dayIndex) * BigInt(SECS_PER_DAY) + BigInt(hour * 3600 + minute * 60 + second - offsetSeconds);
}

/** Vista TCJ+0 de un instante: fecha Gerarion + hora civil (espejo de calendar.instant_parts). */
export function instantParts(instant) {
  const t = BigInt(instant);
  const day = t < 0n ? -((-t) / BigInt(SECS_PER_DAY)) : t / BigInt(SECS_PER_DAY);
  let rem = t % BigInt(SECS_PER_DAY);
  if (rem < 0n) rem += BigInt(SECS_PER_DAY);
  const hour = Number(rem / 3600n);
  const minute = Number((rem % 3600n) / 60n);
  const second = Number(rem % 60n);
  const date = toGerarion(Number(day));
  return { ...date, hour, minute, second, cycle: cycleOf(hour), offset: 0, offsetSeconds: 0 };
}

/** Vista del observador TCJ±O de un instante (suma offset y descompone). */
export function partsFromInstant(instant, offsetSeconds = 0) {
  const p = instantParts(BigInt(instant) + BigInt(offsetSeconds));
  p.offsetSeconds = offsetSeconds;
  return p;
}

// ---------------------------------------------------------------------------

export function tempalumName(date) {
  if (date.month !== 0) return null;
  const names = tempalumDays(date.year) === 11
    ? ["Unictis", "Kindom", "Iki", "Ikiyeh", "Nuvivid I", "Nuvivid II", "Nuvivid III", "Nuvivid IV", "Nuvivid V", "Nuvivid VI", "Nuvivid VII"]
    : ["Unictis", "Kindom", "Iki", "Ikiyeh"];
  return names[date.day - 1];
}
