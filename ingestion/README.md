# ingestion

Lleva los documentos del corpus a la base vectorial. Lee cada PDF, verifica que la extracción sea correcta, lo parte en fragmentos citables y los carga en Qdrant con sus vectores y metadatos.

## Cómo ejecutarlo

Desde esta carpeta, con el `venv` activado:

```powershell
# Validar cada PDF y llevar los datos a Qdrant. Requiere Qdrant arriba.
# La primera vez descarga el modelo de embeddings.
python -m app.main

# Lo mismo, y cambiar la colección activa a la nueva
python -m app.main --activate

# Crear la colección de tamaño fijo, solo para comparar en la evaluación
python -m app.main --baseline

# Propagar un cambio del registro de vigencia, sin recalcular vectores.
# Después hay que reiniciar mcp_server.
python -m app.main --sync-validity

# Medir el detector de inyección con variantes de ataque
python -m app.check_injection_variants

# Pruebas: no requieren Qdrant ni el modelo
python -m pytest
python -m pytest tests/test_extraction.py
python -m pytest tests/test_partition.py
```

`app.main` termina con código 1 si algún documento se rechaza. La configuración está en `app/config/Settings.py`, y se puede cambiar con un archivo `.env`, a partir de `.env.example`.

## Estructura

```
app/
├── config/         Settings
├── models/         ExtractedDocument, PageElement, VerificationIssue, Fragment
├── repositories/   PdfRepository, MarkdownRepository, RegistryRepository,
│                   EmbeddingRepository, QdrantRepository
├── services/       SectionParser, ExtractionVerifier, InjectionDetector,
│                   Partitioner, LexicalTokenizer
└── main.py         une todo el flujo
tests/              test_extraction, test_partition
```

Sigue las capas del Taller 1: los `repositories` hablan con el exterior (archivos, modelo, Qdrant), los `services` contienen las reglas y los `models` solo guardan datos.

## Cómo funciona

### 1. Lectura del PDF
`PdfRepository` lee las líneas de texto y las tablas con `pdfplumber`, en orden de lectura. Descarta el pie de página por su tamaño de fuente y evita duplicar el texto que ya pertenece a una tabla.

### 2. Estructura del documento
`SectionParser` convierte esos elementos en un documento:

- **Metadatos:** salen de la tabla del encabezado, que empieza con "Código". Se lee por celdas, para que un valor en dos líneas no se mezcle con otro campo.
- **Secciones:** se detectan por la fuente en negrita. Su identificador se deriva del título: `3` para "3. Criterios", `art-2` para "Artículo 2. X" y `anexo-notas-de-integracion` para los títulos sin número.
- **Bloques:** párrafos, elementos de lista y tablas. Cada bloque recuerda el numeral al que pertenece, como `3.1`.

Los tamaños de fuente y las distancias se midieron en estos PDF. Otra plantilla necesitaría otros valores.

### 3. Verificación
`ExtractionVerifier` compara el resultado con la copia en Markdown y con el registro de vigencia: metadatos, orden de los títulos, texto de cada sección y área responsable. **Un documento con diferencias no se indexa.** El Markdown solo se usa aquí; lo que se indexa sale del PDF.

No verifica dónde se corta cada párrafo, solo el texto completo de la sección.

### 4. Partición
`Partitioner` crea un fragmento por cada numeral, más uno con el contenido previo al primer numeral de la sección (ADR-02). Las tablas nunca se dividen.

Por ejemplo, en `PRO-MED-007` v2:

| Contenido | Fragmento |
|---|---|
| Tabla de tolerancias, antes del 3.1 | `PRO-MED-007@2#3` |
| Numeral 3.2 | `PRO-MED-007@2#3.2`, cuya sección padre es `3` |

Cada fragmento lleva los metadatos del contrato del corpus y copia su estado de vigencia del registro. El `fragment_id` es determinista: reingerir el mismo documento no cambia las citas.

### 5. Detección de inyección
`InjectionDetector` aplica reglas deterministas sobre el texto normalizado (ADR-06). Busca instrucciones dirigidas a sistemas automáticos, órdenes de ignorar instrucciones, ocultamiento al usuario y envío de datos a un correo. Solo marca el fragmento: **la retención se aplica al responder**, no aquí.

En el corpus marca únicamente el anexo de `COM-PRV-0134`. Una instrucción parafraseada no se detecta, como demuestra una de las pruebas; es el riesgo residual que declara el ADR-06.

### 6. Vectores
Cada fragmento recibe dos vectores:

- **Semántico (`EmbeddingRepository`):** usa `multilingual-e5-small` en CPU, en una revisión fija, con el prefijo `passage:` (ADR-04). La ingesta se detiene si un fragmento supera el límite de 512 tokens.
- **Léxico (`LexicalTokenizer`):** quita tildes y mayúsculas, y conserva códigos y números completos, además de sus partes (ADR-05). Calcula los pesos BM25; Qdrant aplica el factor IDF al consultar. **Debe ser idéntico al de `mcp_server`.**

El texto indexado lleva antes el código, el título del documento y el de la sección. El texto que se muestra al usuario no los incluye.

### 7. Carga en Qdrant
`QdrantRepository` crea la colección si no existe y carga los fragmentos. Su nombre incluye lo que determina sus vectores, por ejemplo:

```
corpus__multilingual-e5-small__614241f6__p1__t1__d1
```

Es decir: modelo, revisión y versiones de la partición, el tokenizador y las reglas de detección. Cambiar cualquiera crea una colección nueva sin tocar la activa.

El alias `corpus_active` indica cuál usa el servicio. La primera carga lo crea sola; después solo cambia con `--activate`. Una reingesta borra los fragmentos que ya no existen. Los pasos de reindexación están en el [README principal](../README.md#reindexar).

Solo se descarga el modelo: ningún documento sale del equipo.

## Qué hace cada clase

| Clase | Función principal | Qué hace |
|---|---|---|
| `PdfRepository` | `read` | Lee líneas y tablas del PDF |
| `MarkdownRepository` | `read` | Lee la copia en Markdown, solo para comparar |
| `RegistryRepository` | `load` | Lee el registro de vigencia |
| `EmbeddingRepository` | `embed_passages` | Calcula el vector semántico |
| | `token_count` | Cuenta los tokens de un texto |
| `QdrantRepository` | `ensure_collection` | Crea la colección si no existe |
| | `replace_points` | Carga los fragmentos y borra los que ya no existen |
| | `activate` | Apunta el alias a la colección |
| `SectionParser` | `parse` | Arma metadatos, secciones y bloques |
| `ExtractionVerifier` | `verify` | Devuelve las diferencias encontradas |
| `Partitioner` | `partition` | Convierte un documento en fragmentos |
| `InjectionDetector` | `detect` | Devuelve las reglas que coinciden con el texto |
| `LexicalTokenizer` | `tokenize` | Separa el texto en palabras normalizadas |
| | `document_vector` | Calcula el vector léxico de un fragmento |
| | `query_vector` | Calcula el vector léxico de una consulta |

`DocumentMetadata`, `Block`, `Section`, `ExtractedDocument`, `TextLine`, `TableElement`, `VerificationIssue` y `Fragment` guardan datos, sin reglas de negocio.

## Pruebas

- **`test_extraction.py`:** los 19 PDF coinciden con su Markdown y el registro, y el verificador detecta datos alterados. También cubre casos difíciles del corpus, como la tabla antes de un numeral y el anexo malicioso.
- **`test_partition.py`:** los fragmentos son únicos y deterministas, no se pierde contenido, las tablas quedan completas y el estado se copia del registro. También prueba el detector y el tokenizador.
