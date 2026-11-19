# GUS Specification — Gerarion Universal Standard (canonical format)

- **Status:** Stable (normative, frozen math) · **Version:** 1.0.0 · **Baseline:** GUS v3.1.1
- **Consolidated edition:** [`../en/gus-3.0.0.md`](../en/gus-3.0.0.md) (§1–§2, §6, §11, appendices)
- **License:** CC-BY-4.0 · Maintained by: verared contributors

## 1. Scope

GUS defines the **canonical syntax** of the 32- and 29-character
timestamp, the representation of the continuous instant (`int64` seconds
+ separate `nanos`), the fast format check (`quick_verify`), and the
normalisation and versioning rules of the standard. It does not cover the
calendar (CALENDAR domain), the physical definition of TCJ (TCJ domain),
or cryptographic sealing (GST domain).

## 2. Normative rules

1. **Two canonical formats:**
   - *Extended* (32 chars, output): `AAAAYY-MM-DD-X-HH:MM:SS-CC-TCJ±O`,
     e.g. `2031DY-03-08-T-09:30:00-SC-TCJ+0`.
   - *Compact* (29 chars, input/storage): `AAAAYY-MM-DD-X-HHMMSS-CC-TCJ±0`,
     e.g. `2031DY-03-08-T-093000-SC-TCJ0`.
2. **Eras:** `DY` (after the origin) and `AY` (before). Nuvid day
   letters: `S L M A T V B` (Soludyia…Sabatyeh). Normalisation rules
   RULES 1-7 (module `gerarion.format`: `weekday_corrected`,
   `GERO_ETEMPALUM`, `GERO_EINVAL`).
3. **Observer cycles:** `SC` = 06:00–17:59 and `LC` = 18:00–05:59,
   always evaluated on the observer's declared civil hour `HH`, never on
   `TCJ+0`. It is a semantic label, not a transformation.
4. **Offsets `TCJ±O`:** whole hours or with minutes (`TCJ-2:20` /
   compact `TCJ-220`); the offset enters the instant computation; range
   |TCJ±O| ≤ 24 h in multiples of 60 s. Zero offset is always emitted
   `TCJ+0` / `TCJ0`. Two views with different offsets describe the SAME
   instant.
5. **Instant:** `instant = day_index × 86,400 + h·3600 + m·60 + s −
   offset_seconds`, a signed 64-bit integer in **seconds**, with a
   separate `nanos` field (`0 ≤ nanos ≤ 999,999,999`, strict validation:
   no silent normalisation of invalid fractions).
6. **`quick_verify`:** fast format check without building the calendar
   (length, alphabet, digit/letter, field ranges, cycle/hour coherence).
7. **Spec versioning:** semver over the specification; any change
   requires new vectors, an errata/changelog entry, and a one-release
   public comment period.

## 3. Sources of truth

| Platform | Implementation |
|---|---|
| Python | `src/gerarion/format.py`, `src/gerarion/core/` |
| C11 | `impl-c/core/gus_core.c` (format + instant) |
| JavaScript | `web/engine/core.mjs` |

## 4. Applicable vectors

- `vectors/gus-normative-003.json` — **normative and frozen**.
- `vectors/gus-quickverify-001.json` — fast accept/reject.
- `vectors/gus-3339-002.json` — RFC 3339 input bridge (see INTEROP).

## 5. Maturity and limits

- Arithmetic and format **frozen** since v3.0.0 (sub-second `nanos`
  precision added without altering the arithmetic).
- `day_index` > 2⁵³−1 is valid in C11/Python and rejected by JS `Number`
  (platform contract; see appendix of the consolidated edition).
- Name levels (N0–N4) are presentation only and never affect conformity.

## 6. References

- `docs/CONFORMANCE.md`, `docs/GLOSSARY.md`
- Naming compatibility: `docs/en/profiles/gus-for-notation.md`
- Appendix A (mathematical formalisation) of the consolidated edition.
