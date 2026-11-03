"""Chooses the rejection threshold on the augmented set and measures it once on a
separate validation set, whose results never influence the choice. Saves CSV evidence."""
import csv
import logging
from pathlib import Path

from app.composition import build_search_service
from app.config.Settings import settings

for noisy_logger in ("httpx", "httpx2", "huggingface_hub", "sentence_transformers"):
    logging.getLogger(noisy_logger).setLevel(logging.WARNING)

_EVIDENCE_DIR = Path(__file__).resolve().parents[2] / "data" / "evidence"

# Augmented set: chooses the threshold. Question and the fragment that answers it.
AUGMENTED_ANSWERABLE = [
    ("¿Cuál es la tolerancia de conciliación volumétrica?", "PRO-MED-007@2#3"),
    ("¿Qué se hace con una diferencia que está dentro de la tolerancia?", "PRO-MED-007@2#3.1"),
    ("¿En qué plazo se investigan las diferencias superiores a la tolerancia?", "PRO-MED-007@2#3.2"),
    ("¿A quién se escala una diferencia mayor al uno por ciento del volumen?", "PRO-MED-007@2#3.3"),
    ("¿Cómo se calcula la diferencia de balance de un tramo?", "PRO-MED-007@2#2.1"),
    ("¿Quién firma el acta de conciliación mensual?", "PRO-MED-007@2#4"),
    ("¿Cuál es el umbral de alarma de presión del tramo Caucasia – Coveñas?", "PRO-OPE-012@3#3.1"),
    ("¿Qué se considera sospecha de sustracción?", "PRO-OPE-012@3#3.2"),
    ("¿A quién notifica el operador cuando se confirma una anomalía de presión?", "PRO-OPE-012@3#4.1"),
    ("¿En qué plazo se reporta un hurto a la autoridad competente?", "PRO-SEG-015@1#3"),
    ("¿Qué contenido mínimo debe tener el reporte de un evento de hurto?", "PRO-SEG-015@1#4"),
    ("¿Cómo se preserva la evidencia de un hurto de hidrocarburos?", "PRO-SEG-015@1#5"),
    ("¿Cuál es la incertidumbre máxima admisible en la transferencia de custodia?", "RES-CREG-0043-2024@unversioned#art-2"),
    ("¿Cada cuánto se verifica el factor del medidor en los puntos de salida a buque?", "RES-CREG-0043-2024@unversioned#art-3"),
    ("¿En cuántos días se reportan las desviaciones de medición?", "RES-CREG-0043-2024@unversioned#art-5"),
    ("¿Con qué periodicidad se envía el reporte de pérdidas de hidrocarburos?", "RES-ANH-0471-2023@unversioned#art-2"),
    ("¿Cuánto tiempo se conservan los soportes de medición y conciliación?", "RES-ANH-0471-2023@unversioned#art-4"),
    ("¿Cuál es la máxima presión de operación admisible del tramo Ayacucho – Coveñas?", "MAN-OPE-001@3#3.1"),
    ("¿Qué autorización se necesita para operar por encima del noventa por ciento del MAOP?", "MAN-OPE-001@3#3.2"),
    ("¿Con qué frecuencia se lubrican los sellos de las válvulas?", "MAN-MTO-002@1#3"),
    ("¿Qué se requiere antes de intervenir una válvula de línea?", "MAN-MTO-002@1#4"),
    ("¿Cuál es la secuencia obligatoria de bloqueo y etiquetado?", "PRO-HSE-003@4#3"),
    ("¿Quién puede retirar la etiqueta de bloqueo de otra persona?", "PRO-HSE-003@4#4"),
    ("¿Después de cuánto tiempo de parada aplica el arranque en frío de una bomba?", "PRO-OPE-021@1#1"),
    ("¿Qué se hace si hay una desviación durante el arranque en frío?", "PRO-OPE-021@1#4"),
    ("¿Cuál es el límite de temperatura de cojinetes de la bomba principal de Ayacucho?", "FIC-ACT-P101@2#2"),
    ("¿Quién certifica la vigencia de un documento mientras no exista el registro único?", "ACTA-CTO-2025-11@unversioned#4.2"),
    ("¿Qué recomienda el fabricante para los actuadores de válvula serie VX?", "COM-PRV-0098@unversioned#recomendacion"),
]

AUGMENTED_OUT_OF_CORPUS = [
    "¿Cuál es el precio internacional del barril de crudo Brent?",
    "¿Cuál es el salario de un operador del Centro de Control?",
    "¿Cuál es la capital de Colombia?",
    "¿Cómo solicito mis vacaciones en la compañía?",
    "¿Qué tarifa de transporte se cobra por barril a los remitentes?",
    "¿Cuántos pozos activos tiene la compañía en los Llanos Orientales?",
    "¿Cuál es el procedimiento de soldadura para reparar un ducto submarino?",
    "¿Con qué frecuencia se inspeccionan los ductos con raspadores inteligentes?",
    "¿Cuál es la política de ciberseguridad del sistema SCADA?",
    "¿Cuáles son los requisitos de la certificación ISO 14001?",
    "¿Cuál es el plan de manejo ambiental ante un derrame en un río?",
    "¿Quién es el presidente de PetroAndes?",
    "¿Qué capacidad de almacenamiento tiene el terminal de Coveñas?",
    "¿Cuál es la receta para preparar una bandeja paisa?",
    "¿Cómo se calcula la regalía de un contrato de exploración?",
    "¿Qué dotación de seguridad debe usar un visitante en la refinería?",
]

# Validation set: new questions, written before seeing any of their results.
VALIDATION_ANSWERABLE = [
    ("¿Qué porcentaje de diferencia se acepta en la conciliación de un tramo?", "PRO-MED-007@2#3"),
    ("¿Hay que investigar las diferencias que no superan la tolerancia?", "PRO-MED-007@2#3.1"),
    ("¿Se tienen en cuenta los volúmenes de purga al calcular la diferencia?", "PRO-MED-007@2#2.1"),
    ("¿Qué ventana de evaluación aplica a las anomalías de presión?", "PRO-OPE-012@3#3.1"),
    ("¿Qué procedimiento se activa ante una sospecha de sustracción?", "PRO-OPE-012@3#4.3"),
    ("¿Cuánto tiempo hay para avisar a Seguridad Física de un hurto?", "PRO-SEG-015@1#3"),
    ("¿Cuándo se activa el procedimiento de hurto de hidrocarburos?", "PRO-SEG-015@1#2.1"),
    ("¿Cada cuánto se verifica un medidor en los puntos que no son de salida a buque?", "RES-CREG-0043-2024@unversioned#art-3"),
    ("¿Qué trazabilidad deben tener los patrones de verificación?", "RES-CREG-0043-2024@unversioned#art-4"),
    ("¿Qué debe incluir el reporte mensual de pérdidas de hidrocarburos?", "RES-ANH-0471-2023@unversioned#art-3"),
    ("¿Cuál es el MAOP del tramo Caucasia – Coveñas?", "MAN-OPE-001@3#3.1"),
    ("¿Qué verifica el operador de medición al inicio de cada turno?", "MAN-OPE-004@2#3.1"),
    ("¿Qué incertidumbre declara el medidor de Coveñas de salida a buque?", "MAN-OPE-004@2#3.2"),
    ("¿Cuál es el plan de mantenimiento preventivo de las válvulas?", "MAN-MTO-002@1#3"),
    ("¿Qué debe cumplirse antes de iniciar una intervención sobre equipos con energías peligrosas?", "PRO-HSE-003@4#2"),
    ("¿Qué condiciones previas exige el arranque en frío de una bomba?", "PRO-OPE-021@1#2"),
    ("¿Qué presión de descarga de diseño tiene la bomba principal de Ayacucho?", "FIC-ACT-P101@2#2"),
    ("¿Qué intervenciones mayores ha tenido la bomba principal de Ayacucho?", "FIC-ACT-P101@2#3"),
    ("¿Qué instruyó el comité sobre el registro único de vigencia documental?", "ACTA-CTO-2025-11@unversioned#4.1"),
    ("¿Qué requiere la actualización del firmware de los computadores de flujo?", "COM-PRV-0134@unversioned#condiciones-de-aplicacion"),
]

VALIDATION_OUT_OF_CORPUS = [
    "¿Cuál es la política de teletrabajo de la compañía?",
    "¿Cómo se liquida el auxilio de transporte de los empleados?",
    "¿Cuál es el punto de ebullición del diésel?",
    "¿Cuánto cuesta un galón de gasolina en Bogotá?",
    "¿Qué normas aplican al transporte de gas natural licuado?",
    "¿Cómo se calibra un cromatógrafo de gases?",
    "¿Cuántas refinerías tiene la compañía?",
    "¿Qué proveedor suministra los medidores de ultrasonido?",
    "¿Cuál es el horario del casino de la estación?",
    "¿Quién ganó el mundial de fútbol de 2014?",
    "¿Cuál es el procedimiento para contratar a un nuevo proveedor?",
    "¿Cómo se trata el agua de producción en un campo petrolero?",
]

THRESHOLDS = [round(0.78 + step * 0.005, 3) for step in range(25)]


def measure(service, query: str) -> list[tuple[str, float]]:
    """Return the hybrid fragments with their cosine, as ResponseComposer sees them."""
    outcome = service.search(query, settings.default_result_limit)
    cosine = {fragment.fragment_id: fragment.score for fragment in outcome.dense}
    return [(fragment.fragment_id, cosine.get(fragment.fragment_id, 0.0)) for fragment in outcome.hybrid]


def classify(expected: str | None, hits: list[tuple[str, float]], threshold: float) -> str:
    """Classify a question: correct, wrong_fragment, lost, false_answer or rejected."""
    selected = [fragment for fragment, cosine in hits if cosine >= threshold]
    if expected is None:
        return "false_answer" if selected else "rejected"
    if expected in selected:
        return "correct"
    return "wrong_fragment" if selected else "lost"


def score(cases: list[tuple[str | None, list]], threshold: float) -> dict:
    """Count the outcomes at a threshold; accuracy counts correct answers and right refusals."""
    outcomes = [classify(expected, hits, threshold) for expected, hits in cases]
    counts = {name: outcomes.count(name) for name in ("correct", "wrong_fragment", "lost", "false_answer", "rejected")}
    counts["accuracy"] = (counts["correct"] + counts["rejected"]) / len(cases)
    return counts


def print_score(counts: dict, answerable: int, out_of_corpus: int) -> None:
    print(
        f"  Correct: {counts['correct']}/{answerable} | Wrong fragment: {counts['wrong_fragment']}/{answerable} | "
        f"Refused valid question: {counts['lost']}/{answerable}\n"
        f"  False answers: {counts['false_answer']}/{out_of_corpus} | Accuracy: {counts['accuracy']:.1%}"
    )


def write_csv(name: str, header: list[str], rows: list[list]) -> None:
    _EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    with (_EVIDENCE_DIR / name).open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file)
        writer.writerow(header)
        writer.writerows(rows)
    print(f"Saved {_EVIDENCE_DIR / name}")


def case_row(group: str, query: str, expected: str | None, hits: list, threshold: float) -> list:
    """One row per question: its fragments' cosines and its outcome at the chosen threshold."""
    best_fragment, best_cosine = max(hits, key=lambda hit: hit[1], default=("", 0.0))
    expected_cosine = next((cosine for fragment, cosine in hits if fragment == expected), None)
    return [
        group,
        query,
        expected or "",
        best_fragment,
        round(best_cosine, 4),
        "" if expected_cosine is None else round(expected_cosine, 4),
        classify(expected, hits, threshold),
    ]


def main() -> None:
    service, _ = build_search_service()
    augmented = [(expected, measure(service, query)) for query, expected in AUGMENTED_ANSWERABLE]
    augmented += [(None, measure(service, query)) for query in AUGMENTED_OUT_OF_CORPUS]
    validation = [(expected, measure(service, query)) for query, expected in VALIDATION_ANSWERABLE]
    validation += [(None, measure(service, query)) for query in VALIDATION_OUT_OF_CORPUS]

    print(f"Augmented set: {len(AUGMENTED_ANSWERABLE)} answerable, {len(AUGMENTED_OUT_OF_CORPUS)} out of corpus")
    print(f"Validation set: {len(VALIDATION_ANSWERABLE)} answerable, {len(VALIDATION_OUT_OF_CORPUS)} out of corpus\n")
    print("Threshold | Correct | Wrong fragment | Refused valid | False answers | Accuracy   (augmented set)")
    table = []
    for threshold in THRESHOLDS:
        counts = score(augmented, threshold)
        table.append([threshold, *counts.values()])
        print(
            f"{threshold:9.3f} | {counts['correct']:>7} | {counts['wrong_fragment']:>14} | {counts['lost']:>13} | "
            f"{counts['false_answer']:>13} | {counts['accuracy']:8.1%}"
        )

    # On a tie, the highest threshold: citing without support costs more than refusing.
    chosen = max(THRESHOLDS, key=lambda threshold: (score(augmented, threshold)["accuracy"], threshold))

    print(f"\nChosen threshold (from the augmented set only): {chosen:.3f}")
    print_score(score(augmented, chosen), len(AUGMENTED_ANSWERABLE), len(AUGMENTED_OUT_OF_CORPUS))
    print("\nResult on the validation set (unseen questions):")
    print_score(score(validation, chosen), len(VALIDATION_ANSWERABLE), len(VALIDATION_OUT_OF_CORPUS))

    print("\nAnswerable questions whose expected fragment was not retrieved at any threshold:")
    answerable = [case for case in [*augmented, *validation] if case[0] is not None]
    missed = [expected for expected, hits in answerable if expected not in [fragment for fragment, _ in hits]]
    print("  " + (", ".join(missed) if missed else "none"))
    print()

    write_csv(
        "augmented_thresholds.csv",
        ["threshold", "correct", "wrong_fragment", "refused_valid", "false_answer", "right_refusal", "accuracy"],
        table,
    )
    queries = [*[q for q, _ in AUGMENTED_ANSWERABLE], *AUGMENTED_OUT_OF_CORPUS]
    validation_queries = [*[q for q, _ in VALIDATION_ANSWERABLE], *VALIDATION_OUT_OF_CORPUS]
    rows = [case_row("augmented", q, e, h, chosen) for q, (e, h) in zip(queries, augmented)]
    rows += [case_row("validation", q, e, h, chosen) for q, (e, h) in zip(validation_queries, validation)]
    write_csv(
        "threshold_cases_by_set.csv",
        ["set", "query", "expected_fragment", "best_fragment", "best_cosine", "expected_cosine", f"outcome_at_{chosen:.3f}"],
        rows,
    )


if __name__ == "__main__":
    main()
