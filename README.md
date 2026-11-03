# Taller 2: consulta documental gobernada de PetroAndes

Servicio que responde preguntas de operación citando documento, versión y sección, sin citar material derogado. Es el Escenario A del Taller 2 de Arquitectura de Integración (ARTI 4212). El Escenario B se entrega solo como diseño.

Los documentos del corpus son sintéticos.

## Componentes

| Carpeta | Rol |
|---|---|
| [ingestion/](ingestion/README.md) | Lleva los PDF a la base vectorial |
| [mcp_server/](mcp_server/README.md) | Responde con pasajes citados y expone las herramientas MCP |
| [evaluation/](evaluation/README.md) | Mide el servicio con los casos de referencia |
| `corpus/` | Los 19 documentos: `pdf/` se procesa y `md/` solo se usa para verificar |
| `data/validity_registry.yaml` | Registro de vigencia de cada documento |
| `docs/` | Documentos de los Escenarios A y B, análisis crítico y presentación, en LaTeX |
| `docker-compose.yml` | Levanta Qdrant |

```
Ingesta:   PDF → texto → secciones → verificación → fragmentos → vectores → Qdrant
Consulta:  pregunta → vectores → búsqueda filtrada → rankings
```

## Levantar todo

Requiere Python 3.11, Docker Desktop abierto y, para MCP Inspector, Node 22.19 o superior. Ejecuta los pasos en PowerShell, desde la raíz del proyecto.

```powershell
# 1. Crear y activar el entorno
python -m venv venv
.\venv\Scripts\Activate.ps1

# 2. Instalar dependencias
python -m pip install -r requirements.txt

# 3. Levantar Qdrant
docker compose up -d

# 4. Validar los PDF y cargarlos en Qdrant
# La primera vez descarga el modelo de embeddings, de unos 470 MB.
cd ingestion
python -m app.main
cd ..

# 5. Hacer una consulta
cd mcp_server
python -m app.ask "¿Cuál es la tolerancia de conciliación?"

# 6. Abrir el servidor MCP en MCP Inspector
npx @modelcontextprotocol/inspector python -m app.main
cd ..
```

Si `torch` falla con `WinError 126`, instala o repara el [Visual C++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe) y abre una terminal nueva.

Si MCP Inspector falla con `Cannot find native binding` tras actualizar Node, borra su caché y reintenta: `Remove-Item -Recurse -Force "$env:LOCALAPPDATA\npm-cache\_npx"`. Al abrirse en el navegador, presiona **Connect** y luego **List Tools**.

Para apagar Qdrant conservando los datos, usa `docker compose down`. Para borrarlos también, usa `docker compose down -v`.

## Cómo ver que todo funciona

| Qué | Cómo | Qué deberías ver |
|---|---|---|
| Qdrant | `curl.exe http://localhost:6333` | La versión `1.20.0` |
| Panel de Qdrant | http://localhost:6333/dashboard | La colección `corpus__...` con sus fragmentos |
| Ingesta | Última línea de `python -m app.main` | `19 documents, 0 rejected` |
| Colección activa | `curl.exe http://localhost:6333/collections/corpus_active` | `points_count` igual al número de fragmentos |
| Consulta citada | `python -m app.ask "K 061+800"` desde `mcp_server/` | `status: answered`, con la cita de `MAN-MTO-002`, sección 2 |
| Consulta rechazada | `python -m app.ask "¿Cuál es el precio del crudo Brent?"` desde `mcp_server/` | `status: rejected` |
| Documento derogado | `python -m app.ask "RES-CREG-0112-2021"` desde `mcp_server/` | `status: excluded_document`, con su sucesor y sin contenido |
| Rankings de búsqueda | `python -m app.compare "K 061+800"` desde `mcp_server/` | Las listas híbrida, semántica y léxica |

Logs de Qdrant en vivo:

```powershell
docker compose logs -f qdrant
```

## Probar el código

```powershell
# Ingesta: no requiere Qdrant ni el modelo
cd ingestion
python -m pytest
cd ..

# Búsqueda: requiere Qdrant arriba y el corpus cargado
cd mcp_server
python -m pytest
cd ..

# Arnés: no requiere Qdrant, el servidor ni laya
cd evaluation
python -m pytest
cd ..
```

## Evaluar

Con Qdrant arriba y el corpus cargado:

```powershell
cd evaluation
python -m app.main
cd ..
```

La evidencia queda en `data/evidence/`, y [evaluation/](evaluation/README.md) explica las métricas.

Cada componente detalla sus pruebas en su README.

## Compilar los documentos

Desde `docs/escenario_a`, `docs/escenario_b`, `docs/analisis_critico` o `docs/presentacion`:

```powershell
latexmk -pdf main.tex
```

## Reindexar

Aplica al cambiar el modelo de embeddings o su revisión, la partición, el tokenizador o las reglas de detección (ADR-04). Un cambio de vigencia no la requiere: basta con `python -m app.main --sync-validity` desde `ingestion/` y reiniciar `mcp_server`.

1. Cambia el valor en `Settings.py` o la versión del componente modificado: `PARTITION_VERSION`, `TOKENIZER_VERSION` o `DETECTION_RULES_VERSION`. Si cambias el tokenizador, actualiza sus dos copias, la de `ingestion` y la de `mcp_server`.
2. Actualiza los mismos valores de configuración en `mcp_server`.
3. Ejecuta `python -m app.main` desde `ingestion/`. Crea una colección nueva, porque su nombre incluye esas versiones, sin tocar la activa.
4. Evalúa la colección nueva con los casos de referencia. El arnés se crea en la tarea 13.
5. Si los resultados no empeoran, ejecuta `python -m app.main --activate`. Si empeoran, descarta la colección nueva.
6. Conserva la colección anterior como retroceso. Para volver a ella, restaura la configuración anterior y ejecuta `python -m app.main --activate`.
7. Cuando ya no la necesites, bórrala:

```powershell
curl.exe -X DELETE http://localhost:6333/collections/NOMBRE_DE_LA_COLECCION
```
