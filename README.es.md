# Sintaxis canónica de marca Gerarion

Parte de la suite de referencia **Gerarion** (verared/gerarion `v3.2.0`,
Gerarion Universal Standard). Este directorio es un **paquete de
exportación** listo para publicarse (o consumirse) como repositorio
satélite `verared/gt-gus`; conserva las rutas relativas del repositorio
base para componer módulos.

## El problema único que resuelve

El formato canónico de 32 y 29 caracteres, sus reglas de normalización (REGLAS 1-7), la verificación rápida (quick_verify) y la representación del instante (int64 segundos + nanos separado).

## Estado normativo

- **Estable** — línea base `v3.2.0` (aritmética y vectores
  congelados: GUS v3.0.0).
- Especificación(es) incluida(s): `docs/specs/GUS.es.md`, `docs/specs/GUS.en.md`

## Dependencias

- **Ninguna externa: 100 % standalone.** Puede adoptarse aisladamente, sin el resto de la suite.

## Contenido

- `LICENSE`
- `NOTICE`
- `docs/specs/GUS.en.md`
- `docs/specs/GUS.es.md`
- `impl-c/core/gus_core.c`
- `impl-c/core/gus_core.h`
- `src/gerarion/core/__init__.py`
- `src/gerarion/core/calendar.py`
- `src/gerarion/core/format.py`
- `vectors/gus-normative-003.json`
- `vectors/gus-quickverify-001.json`
- `web/engine/core.mjs`

## Uso offline

No requiere red, cuentas, registro de paquetes ni frameworks:

```bash
python3 -c 'import sys; sys.path.insert(0, "src"); import gerarion'
```

## Verificación

Con Python ≥ 3.9 y `reuse` instalado:

```bash
reuse lint                                    # licencias al 100 %
# (las pruebas viven en la suite de verared/gerarion)
```

## Contrato de sincronización con `verared/gerarion`

Este paquete es **generado, no editado a mano**: se regenera byte a
byte desde `verared/gerarion v3.2.0` con
`python3 tools/export_module.py --module gt-gus --out <dir>`. La fuente
de verdad normativa (especificaciones, vectores CC0, núcleos de
referencia de las tres plataformas y la batería completa) permanece en
`verared/gerarion`; los satélites `verared/gt-gus` la consumen y no forkean la
aritmética. Las actualizaciones fluyen regenerando la exportación desde
un tag del repositorio base; nunca editando los archivos exportados.
