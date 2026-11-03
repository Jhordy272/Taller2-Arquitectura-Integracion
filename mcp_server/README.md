# mcp_server

Servidor MCP que responde consultas con pasajes literales y citados, solo de documentos vigentes, o rechaza la consulta si no hay soporte. Combina búsqueda semántica y léxica, y expone dos herramientas: `search_documents` y `get_fragment`.

## Cómo ejecutarlo

Desde esta carpeta, con el `venv` activado, Qdrant arriba y el corpus cargado:

```powershell
# Abrir el servidor MCP en MCP Inspector
npx @modelcontextprotocol/inspector python -m app.main

# Arrancar solo el servidor: espera mensajes por stdin, sin mostrar nada
python -m app.main

# Responder una consulta sin pasar por MCP
python -m app.ask "¿Cuál es la tolerancia de conciliación?"

# Obtener un fragmento por documento, versión y sección
python -m app.ask --fragment PRO-MED-007 2 3.3

# Comparar los rankings híbrido, semántico y léxico
python -m app.compare "K 061+800"

# Medir los umbrales de rechazo y guardar la evidencia en data/evidence/
python -m app.calibrate_threshold

# Todas las pruebas
python -m pytest

# Solo las que no requieren Qdrant
python -m pytest tests/test_contracts.py tests/test_answer_rules.py tests/test_mcp_tools.py
```

La configuración está en `app/config/Settings.py`, y se puede cambiar con un archivo `.env`, a partir de `.env.example`.

## Estructura

```
app/
├── config/         Settings
├── models/         RetrievedFragment, SearchOutcome, Answer y sus partes
├── repositories/   QdrantSearchRepository, QueryEmbeddingRepository, RegistryRepository
├── services/       ResponseComposer, HybridSearchService, QueryAnalyzer,
│                   ValidityRegistry, LexicalTokenizer
├── tools/          DocumentTools: contratos de las herramientas MCP
├── composition.py  conecta los componentes
├── main.py         arranca el servidor MCP
├── ask.py          responde una consulta y la imprime en JSON
├── compare.py      imprime los rankings de una consulta
└── calibrate_threshold.py   mide los umbrales de rechazo
tests/              test_contracts, test_answer_rules, test_mcp_tools, test_search, test_answers
```

`ask.py`, `compare.py` y `calibrate_threshold.py` son herramientas de apoyo: no pasan por el protocolo MCP.

## Herramientas MCP

| Herramienta | Parámetros | Qué hace |
|---|---|---|
| `search_documents` | `query` | Busca y devuelve pasajes citados, o un rechazo |
| `get_fragment` | `code`, `version`, `section_id` | Devuelve un fragmento por su cita |

Ambas son de solo lectura y devuelven la misma estructura, `Answer`. **No hay parámetros para saltarse la vigencia ni la retención.** Un rechazo no es un error: es un resultado normal en `status`. Un error solo significa que no se pudo procesar la llamada:

| Error | Cuándo ocurre |
|---|---|
| `validation error` | Faltan parámetros o no cumplen su esquema; el mensaje lo genera el SDK |
| `search_unavailable` | Qdrant no responde; el detalle queda en el log del servidor |

El servidor usa `stdio`, así que `stdout` queda reservado para el protocolo y los logs van a `stderr`. Usa la clase `MCPServer` de `mcp` 2.x, que reemplazó a `FastMCP`. Al arrancar carga el modelo, por lo que tarda unos segundos, y falla si la colección es incompatible.

## Cómo funciona

### 1. Comprobación al iniciar
`ensure_compatible` compara el modelo, su revisión, sus dimensiones y la versión del tokenizador con los que se usaron para construir la colección (ADR-04). Si no coinciden, lanza un error en lugar de devolver resultados sin sentido.

### 2. Documentos excluidos
Lo primero es revisar si la consulta nombra un documento excluido, en el registro de vigencia (ADR-07). Se reconoce por su código (`RES-CREG-0112-2021`), su versión (`PRO-MED-007 v1`) o su número de resolución ("Resolución 0112 de 2021"). En ese caso, responde con su estado y su sucesor, sin buscar ni mostrar su contenido.

Un código con alguna versión vigente, como `PRO-MED-007`, no se considera excluido si la consulta no menciona una versión anterior.

### 3. Búsqueda filtrada
Calcula dos vectores de la consulta:

- **Semántico:** `QueryEmbeddingRepository` usa el mismo modelo de la ingesta, con el prefijo `query:`. Solo lee archivos locales, así que consultar no hace llamadas a internet.
- **Léxico:** `LexicalTokenizer` genera el vector. Es una copia del de `ingestion`; una prueba falla si dejan de ser idénticos. La consulta conserva los códigos completos, para que `VA-AY-003` no traiga todo lo que contenga "003".

`QdrantSearchRepository.search` envía tres búsquedas en un lote:

| Búsqueda | Puntaje | Para qué sirve |
|---|---|---|
| **Híbrida** | RRF, combina las posiciones de ambas ramas | Es el orden de la respuesta |
| **Semántica** | Similitud coseno | Decidir el soporte de una pregunta |
| **Léxica** | BM25 | Encontrar códigos exactos |

Los empates de puntaje se resuelven por `fragment_id`, antes de cortar los resultados, para que el orden sea reproducible.

El filtro `validity_status = valid` está fijo en `_VALID_ONLY` y se declara en cada rama, de modo que se aplica durante la búsqueda y nunca después (ADR-05). **No es un parámetro:** ningún cliente puede pedir documentos derogados.

### 4. Regla de rechazo
Las pruebas mostraron que ningún umbral de similitud separa todos los casos: la respuesta correcta de `K 061+800` puntúa 0,803 y una pregunta fuera del corpus, 0,805. Por eso hay dos reglas, según la consulta:

| Consulta | Regla | Ejemplo |
|---|---|---|
| **Con un identificador** | Debe aparecer completo en el fragmento; se ignora el coseno | `CMP-999` se rechaza y `K 061+800` se responde |
| **En lenguaje natural** | El coseno del fragmento debe superar el umbral | Se rechaza la pregunta por el crudo Brent |

El umbral de 0,84 sale de `app/calibrate_threshold.py`: un conjunto aumentado de 44 preguntas lo elige y un conjunto de validación de 32 preguntas nuevas lo mide. En validación obtiene 19/20 respuestas correctas, 1/20 con fragmento erróneo y 2/12 respuestas falsas, con 90,6 % de exactitud. La evidencia queda en `data/evidence/`. El conjunto de validación no debe usarse para seguir ajustando el umbral.

### 5. Composición
`ResponseComposer` arma la respuesta sin generar texto sobre el contenido (ADR-03):

- **Pasajes literales:** el texto se devuelve tal como está en el corpus, marcado como `untrusted_data`.
- **Cita:** documento, versión, sección, título, tipo y área. `document_class` indica si es una norma o un registro.
- **Sección padre:** un numeral incluye el contenido de su sección en `parent_context`, con su propia cita. Así, el numeral 3.2 de `PRO-MED-007` llega con la tabla que define la tolerancia (ADR-02). No se repite si esa sección ya es un pasaje.
- **Retención:** un fragmento con `injection_risk` devuelve su cita y una alerta, sin su texto (ADR-06). Se aplica en la búsqueda, en la obtención directa y en la sección padre.

### 6. Estados de la respuesta

| `status` | Cuándo ocurre |
|---|---|
| `answered` | Hay pasajes con soporte |
| `rejected` | No hay soporte en el corpus vigente |
| `excluded_document` | Se nombró un documento excluido |
| `not_found` | El fragmento solicitado no existe |

## Qué hace cada clase y función

**`ResponseComposer`**

| Función | Qué hace |
|---|---|
| `answer` | Responde una consulta aplicando todas las reglas |
| `get_fragment` | Devuelve un fragmento por documento, versión y sección |
| `_select_by_identifier` | Conserva los fragmentos que contienen el identificador |
| `_select_by_similarity` | Conserva los fragmentos que superan el umbral |
| `_parent_context` | Agrega la sección padre de un numeral |
| `_content` | Arma la cita y aplica la retención |

**`QdrantSearchRepository`**

| Elemento | Qué hace |
|---|---|
| `_VALID_ONLY` | Filtro fijo: solo documentos vigentes |
| `collection_metadata` | Lee con qué modelo y tokenizador se construyó la colección |
| `search` | Lanza las búsquedas híbrida, semántica y léxica |
| `get_fragment` | Busca un fragmento vigente por su identificador |
| `_dense_branch`, `_lexical_branch` | Preparan las ramas de la búsqueda híbrida |
| `_to_fragments`, `_to_fragment` | Convierten la respuesta de Qdrant en `RetrievedFragment` |

**Resto del componente**

| Elemento | Qué hace |
|---|---|
| `QueryEmbeddingRepository.embed` | Convierte la consulta en un vector semántico |
| `RegistryRepository.load` | Lee el registro de vigencia |
| `LexicalTokenizer.tokenize` | Normaliza y separa el texto, conservando los códigos |
| `LexicalTokenizer.query_vector` | Calcula el vector léxico de la consulta |
| `HybridSearchService.search` | Calcula ambos vectores y llama al repositorio |
| `ensure_compatible` | Lanza un error si la colección no coincide con la configuración |
| `extract_identifiers` | Encuentra códigos y ubicaciones en una consulta |
| `contains_identifier` | Comprueba que un identificador aparezca completo |
| `ValidityRegistry.excluded_mentions` | Encuentra los documentos excluidos que nombra una consulta |
| `build_search_service`, `build_composer` | Conectan los componentes y comprueban la colección |

## Pruebas

- **`test_contracts.py`:** no requiere Qdrant. Comprueba que el tokenizador sea idéntico al de `ingestion` y que una colección incompatible se rechace.
- **`test_answer_rules.py`:** no requiere Qdrant, porque reemplaza la búsqueda con objetos simulados. Cubre las reglas de rechazo, las citas, la sección padre, la retención y los documentos excluidos.
- **`test_mcp_tools.py`:** no requiere Qdrant. Comprueba las dos herramientas, sus contratos, que sean de solo lectura, los parámetros inválidos y el error genérico si falla Qdrant.
- **`test_search.py`:** requiere Qdrant y el corpus cargado. Comprueba que lo derogado no aparezca en ninguna rama y que se encuentren códigos exactos.
- **`test_answers.py`:** requiere Qdrant y el corpus cargado. Comprueba las reglas sobre el corpus real, incluidos el anexo malicioso y la resolución derogada.
