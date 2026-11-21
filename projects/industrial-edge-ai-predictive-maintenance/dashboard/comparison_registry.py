"""Immutable local synthetic comparisons; approval never authorizes deployment."""
from pathlib import Path
import math
import re

from experiment_registry import _digest, _json_bytes, _read_verified, _save_once

SCHEMA = "edgeops-model-comparison-v1"


def check_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("Comparison ID must be a lowercase SHA-256 digest")
    return value


def validate_result(result):
    if (result.get("provenance") != "synthetic-demo"
            or result.get("label_kind") != "synthetic-demonstration-only"
            or result.get("evaluation_scope") != "offline-research-only"
            or result.get("hardware_connected") is not False
            or result.get("model_deployed") is not False
            or result.get("real_world_accuracy") != "not-established"):
        raise ValueError("Invalid comparison provenance or deployment state")
    split = result["split"]
    if split["method"] != "global-chronological":
        raise ValueError("Chronological comparison required")
    for key in ("train_count", "validation_count", "test_count"):
        if type(split[key]) is not int or split[key] < 1:
            raise ValueError("Invalid partition size")
    ids = split["holdout_event_ids"]
    if (not isinstance(ids, list) or any(not isinstance(x, str) for x in ids)
            or len(ids) != split["test_count"] or len(set(ids)) != len(ids)):
        raise ValueError("Invalid common holdout")
    models = result["models"]
    if len(models) != 2 or {m["name"] for m in models} != {
            "standardized-deviation", "sklearn-logistic-regression"}:
        raise ValueError("Expected the two comparison baselines")
    for model in models:
        metrics = model["test_metrics"]
        for key in ("precision", "recall", "f1", "accuracy", "threshold"):
            value = metrics[key]
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError("Invalid comparison metric")
        if model["threshold"] != metrics["threshold"]:
            raise ValueError("Threshold mismatch")
        counts = [metrics[k] for k in ("tp", "tn", "fp", "fn")]
        if (any(type(x) is not int or x < 0 for x in counts)
                or sum(counts) != split["test_count"]
                or metrics["sample_count"] != split["test_count"]):
            raise ValueError("Invalid confusion matrix or holdout size")


def save_comparison(rows, artifact_root, *, train_fraction=0.6, validation_fraction=0.2):
    from sklearn_comparison import compare_same_holdout
    import sklearn
    import numpy
    rows = list(rows)
    result = compare_same_holdout(rows, train_fraction=train_fraction,
                                  validation_fraction=validation_fraction)
    validate_result(result)
    dataset = {"schema": SCHEMA, "provenance": "synthetic-demo",
               "rows": sorted(rows, key=lambda r: (r["captured_at"], r["event_id"]))}
    data = _json_bytes(dataset)
    dataset_sha = _digest(data)
    report = {"schema": SCHEMA, "dataset_sha256": dataset_sha,
              "training_config": {"train_fraction": train_fraction,
                                  "validation_fraction": validation_fraction,
                                  "threshold_selection": "validation-f1",
                                  "random_state": 17},
              "software_versions": {"sklearn": sklearn.__version__, "numpy": numpy.__version__},
              "source_sha256": {name: _digest((Path(__file__).parent / name).read_bytes())
                                for name in ("sklearn_comparison.py", "offline_baseline.py",
                                             "ml_evaluation.py", "comparison_registry.py")},
              "result": result}
    report_bytes = _json_bytes(report)
    comparison_id = _digest(report_bytes)
    root = Path(artifact_root).resolve()
    _save_once(root / "comparison-datasets" / (dataset_sha + ".json"), data)
    _save_once(root / "comparisons" / (comparison_id + ".json"), report_bytes)
    return {"comparison_id": comparison_id, "report": report}


def verify_comparison(artifact_root, comparison_id):
    root = Path(artifact_root).resolve()
    check_id(comparison_id)
    report = _read_verified(root / "comparisons" / (comparison_id + ".json"), comparison_id)
    if report.get("schema") != SCHEMA:
        raise ValueError("Invalid comparison schema")
    dataset_sha = check_id(report["dataset_sha256"])
    dataset = _read_verified(root / "comparison-datasets" / (dataset_sha + ".json"), dataset_sha)
    if dataset.get("schema") != SCHEMA or dataset.get("provenance") != "synthetic-demo":
        raise ValueError("Invalid comparison dataset")
    validate_result(report["result"])
    # Integrity is a byte fingerprint, not proof that an experiment is scientifically valid.
    return report
