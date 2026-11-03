# evaluation

Arnés de evaluación. Ejecuta los casos de referencia contra el servidor, reporta anclaje, relevancia, desviación y latencia, y guarda la evidencia en `data/evidence/`.

## Cómo ejecutarlo

Desde esta carpeta, con el `venv` activado, Qdrant arriba y el corpus cargado:

```powershell
# Evaluación completa. La primera vez, laya descarga su modelo.
python -m app.main

# Solo las métricas deterministas, sin laya
python -m app.main --no-judge

# Comprobar que dos ejecuciones den lo mismo
python -m app.main --reproducibility

# Comparar con la partición de tamaño fijo
cd ..\ingestion
python -m app.main --baseline
cd ..\evaluation
python -m app.main --collection corpus_baseline_fixed_size --label fixed_size --no-judge

# Pruebas: no requieren Qdrant, el servidor ni laya
python -m pytest
```

## Estructura

```
app/
├── config/         Settings
├── models/         CaseVerdict, CaseResult
├── repositories/   CaseRepository, McpClientRepository, LayaJudge
├── services/       CaseEvaluator, MetricsReport
└── main.py         ejecuta los casos y guarda la evidencia
tests/              test_case_evaluator
```

## Cómo funciona

### 1. Ejecuta los casos por MCP
`McpClientRepository` arranca `mcp_server` y llama a `search_documents` por `stdio`, como cualquier cliente. Así se mide el contrato publicado y la latencia real de la llamada, no funciones internas.

### 2. Evalúa el comportamiento
`CaseEvaluator` compara la respuesta con lo que espera cada caso, de forma determinista. Revisa lo que recibe el usuario, incluida la sección padre.

| Resultado | Significado |
|---|---|
| `correct` | Se comportó como se esperaba |
| `wrong_answer` | Respondió sin el texto esperado, o con un sucesor equivocado |
| `stale_value` | Mostró un valor derogado |
| `refused_valid` | Rechazó una pregunta válida |
| `false_answer` | Respondió algo que debía rechazar |
| `exposed` | Mostró un documento excluido o el texto malicioso |
| `tool_error` | La herramienta falló |

### 3. Juzga con `laya`
`LayaJudge` usa el checkpoint multilingüe de `laya`, en una revisión fija, porque el corpus está en español. Corre localmente.

### 4. Métricas

| Métrica | Qué mide | Tipo |
|---|---|---|
| **Tasa de desviación** | Casos que no se comportan como se esperaba | Determinista |
| **`hit_rate`** | Casos en que el fragmento esperado llega como pasaje o sección padre | Determinista |
| **`mrr`** | Qué tan arriba aparece el fragmento esperado como pasaje | Determinista |
| **Latencia** | Mediana, percentil 95 y máximo, frente a los 5 s de EI16 | Determinista |
| **Anclaje** | Probabilidad de que los pasajes sustenten la respuesta esperada (`noul`) | `laya` |
| **Control del anclaje** | La misma medida con pasajes de otro documento, que no contienen la respuesta | `laya` |
| **Relevancia** | Parte de los pasajes que contienen la respuesta (`choice`) | `laya` |

**El control sirve para validar al juez:** si el anclaje real y el del control salen parecidos, `laya` no está distinguiendo, y ese valor no debe usarse.

Los resultados se reportan **por origen de los casos**. La medición más independiente es la de los casos `new`.

### 5. Evidencia
Guarda `evaluation_<label>_cases.csv`, con una fila por caso, y `evaluation_<label>_summary.json`, con las métricas.

## Pruebas

**`test_case_evaluator.py`** cubre las reglas de cada resultado y el cálculo de las métricas, sin el servidor ni `laya`.
