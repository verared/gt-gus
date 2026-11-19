# Especificación GUS — Gerarion Universal Standard (formato canónico)

- **Estado:** Estable (normativo, matemática congelada) · **Versión:** 1.0.0 · **Línea base:** GUS v3.1.1
- **Edición consolidada:** [`../spec/gus-3.0.0.md`](../spec/gus-3.0.0.md) (§1–§2, §6, §11, Apéndices)
- **Licencia:** CC-BY-4.0 · Mantenida por: verared contributors

## 1. Alcance

GUS define la **sintaxis canónica** de la marca temporal de 32 y 29
caracteres, la representación del instante continuo (`int64` segundos +
`nanos` separado), la verificación rápida de formato (`quick_verify`) y
las reglas de normalización y versionado del estándar. No cubre el
calendario (dominio CALENDAR), la definición física de TCJ (dominio TCJ)
ni el sellado criptográfico (dominio GST).

## 2. Reglas normativas

1. **Dos formatos canónicos:**
   - *Extendido* (32 chars, salida): `AAAAYY-MM-DD-X-HH:MM:SS-CC-TCJ±O`,
     p. ej. `2031DY-03-08-T-09:30:00-SC-TCJ+0`.
   - *Compacto* (29 chars, entrada/almacenamiento): `AAAAYY-MM-DD-X-HHMMSS-CC-TCJ±0`,
     p. ej. `2031DY-03-08-T-093000-SC-TCJ0`.
2. **Eras:** `DY` (después del origen) y `AY` (antes). Letras de día
   Nuvid: `S L M A T V B` (Soludyia…Sabatyeh). Reglas de normalización
   REGLAS 1-7 (módulo `gerarion.format`: `weekday_corrected`,
   `GERO_ETEMPALUM`, `GERO_EINVAL`).
3. **Ciclos del observador:** `SC` = 06:00–17:59 y `LC` = 18:00–05:59,
   evaluados SIEMPRE sobre la hora civil `HH` declarada del observador,
   nunca sobre `TCJ+0`. Es etiqueta semántica, no transformación.
4. **Offsets `TCJ±O`:** horas enteras o con minutos
   (`TCJ-2:20` / compacto `TCJ-220`); el offset entra en el cálculo del
   instante; rango |TCJ±O| ≤ 24 h en múltiplos de 60 s. El offset cero
   se emite siempre `TCJ+0` / `TCJ0`. Dos vistas con distinto offset
   describen el MISMO instante.
5. **Instante:** `instant = day_index × 86.400 + h·3600 + m·60 + s −
   offset_seconds`, entero con signo de 64 bits en **segundos**, con
   campo separado `nanos` (`0 ≤ nanos ≤ 999.999.999`, validación
   estricta: sin normalización silenciosa de fracciones inválidas).
6. **`quick_verify`:** verificación rápida de formato sin construir el
   calendario (longitud, alfabeto, dígito/letra, rango de campos,
   coherencia ciclo/hora).
7. **Versionado de la especificación:** semver sobre la especificación;
   cualquier cambio exige vectores nuevos, entrada de errata/changelog y
   periodo de comentario público de un release.

## 3. Fuentes de verdad

| Plataforma | Implementación |
|---|---|
| Python | `src/gerarion/format.py`, `src/gerarion/core/` |
| C11 | `impl-c/core/gus_core.c` (formato + instante) |
| JavaScript | `web/engine/core.mjs` |

## 4. Vectores aplicables

- `vectors/gus-normative-003.json` — **normativo y congelado**.
- `vectors/gus-quickverify-001.json` — aceptación/rechazo rápido.
- `vectors/gus-3339-002.json` — puente de entrada RFC 3339 (ver INTEROP).

## 5. Madurez y límites

- **Congelada** la aritmética y el formato desde v3.0.0 (con la precisión
  sub-segundo `nanos` añadida sin alterar la aritmética).
- `day_index` > 2⁵³−1 es válido en C11/Python y rechazado en JS `Number`
  (contrato de plataforma; ver apéndice de la edición consolidada).
- Los niveles de nombre (N0–N4) son solo presentación y no afectan a la
  conformancia.

## 6. Referencias

- `docs/CONFORMANCE.md`, `docs/GLOSSARY.md`
- Compatibilidad de nombres: `docs/profiles/gus-for-notation.md`
- Apéndice A (formalización matemática) de la edición consolidada.
