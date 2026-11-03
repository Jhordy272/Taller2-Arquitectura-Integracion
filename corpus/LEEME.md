# Corpus documental del caso — Taller 2, ARTI 4212

Este corpus reúne 19 documentos sintéticos de PetroAndes S.A. y de su filial de transporte
AndesTransporte S.A.S. Todos son ficticios y carecen de validez operativa o regulatoria; existen
únicamente como material de trabajo del curso.

## Qué contiene

| Carpeta | Contenido |
| --- | --- |
| `01_manuales` | Manuales de operación y de mantenimiento |
| `02_procedimientos` | Procedimientos operativos y de HSE |
| `03_normativa` | Resoluciones regulatorias (entidades ficticias) |
| `04_actas` | Actas del Comité Técnico Operativo |
| `05_comunicaciones` | Comunicaciones y boletines de proveedores |
| `06_fichas` | Fichas técnicas de activos |

Cada documento está en dos formatos. `pdf/` es la forma en que el material existe realmente en la
organización y es la que debe procesar la ingesta. `md/` contiene el mismo contenido en texto plano,
con metadatos en el encabezado; se entrega para que la depuración no dependa de la extracción de PDF,
no para sustituirla.

## Advertencia sobre los metadatos

El encabezado de cada documento declara código, versión, fecha, área emisora y, cuando aplica, a qué
documento reemplaza. **Ninguno declara si está vigente.** Esa ausencia es deliberada y reproduce la
situación real: la vigencia no es un atributo del documento, es una decisión de gobierno que alguien
debe certificar.

El corpus contiene documentos vigentes y documentos que ya no lo están. Determinar cuáles, y declarar
con qué regla y con qué fuente de autoridad lo determinaron, es parte del trabajo del taller. No
todos los casos se resuelven con la misma regla, y hay al menos uno que no se resuelve leyendo el
corpus.

## Advertencia de seguridad

Uno de los documentos contiene contenido diseñado para alterar el comportamiento de un sistema
automático de procesamiento. Está ahí a propósito. No lo retire del corpus: la prueba de
envenenamiento del enunciado consiste en recuperarlo y demostrar qué capa de su diseño lo detiene.
