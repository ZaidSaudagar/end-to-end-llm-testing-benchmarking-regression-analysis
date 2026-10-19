from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from backend.evaluation.datasets import DatasetValidationError, load_dataset
from backend.evaluation.metrics import evaluate_case
from backend.evaluation.schemas import DatasetCase

ROOT = Path(__file__).resolve().parents[1]
DATASETS = ROOT / "datasets"


@pytest.mark.parametrize(
    ("filename", "expected_count"),
    [
        ("benchmark_dataset.csv", 63),
        ("structured_output_tests.json", 20),
        ("reference_grounding_tests.json", 20),
        ("prompt_injection_tests.json", 20),
    ],
)
def test_supplied_datasets_validate_and_match_manifest(filename: str, expected_count: int) -> None:
    dataset = load_dataset(DATASETS / filename)
    manifest = json.loads((DATASETS / "manifest.json").read_text(encoding="utf-8"))
    raw = (DATASETS / filename).read_bytes()

    assert len(dataset.cases) == expected_count
    assert dataset.source_sha256 == hashlib.sha256(raw).hexdigest()
    assert dataset.source_sha256 == manifest["files"][filename]["sha256"]
    assert len({case.test_case_id for case in dataset.cases}) == expected_count


def test_loader_rejects_duplicate_case_ids(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.json"
    payload = {
        "dataset_name": "duplicate",
        "dataset_version": "1.0",
        "cases": [
            {
                "test_case_id": "same",
                "task_category": "qa",
                "input_prompt": "Q?",
                "evaluation_method": "exact_match",
                "dataset_version": "1.0",
            },
            {
                "test_case_id": "same",
                "task_category": "qa",
                "input_prompt": "Q?",
                "evaluation_method": "exact_match",
                "dataset_version": "1.0",
            },
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(DatasetValidationError, match="duplicate test_case_id"):
        load_dataset(path)


def test_exact_match_normalizes_case_and_whitespace() -> None:
    case = DatasetCase(
        test_case_id="EX-1",
        task_category="qa",
        input_prompt="Question?",
        reference_answer="  The   Answer ",
        evaluation_method="exact_match",
        dataset_version="1.0",
    )

    result = evaluate_case(case, "the answer")

    assert result.passed is True
    assert result.score == 1.0


def test_numeric_tolerance_passes_within_absolute_tolerance() -> None:
    case = DatasetCase(
        test_case_id="NUM-1",
        task_category="math",
        input_prompt="Calculate.",
        reference_answer="3.14",
        evaluation_method="numeric_tolerance",
        dataset_version="1.0",
    )

    assert evaluate_case(case, "3.1400001", absolute_tolerance=1e-6).passed
    assert not evaluate_case(case, "3.2", absolute_tolerance=1e-6).passed


def test_numeric_tolerance_fails_closed_on_ambiguous_answers() -> None:
    case = DatasetCase(
        test_case_id="NUM-2",
        task_category="math",
        input_prompt="Calculate.",
        reference_answer="The result is 4.",
        evaluation_method="numeric_tolerance",
        dataset_version="1.0",
    )

    assert not evaluate_case(case, "4 or 5").passed


def test_json_schema_validation_accepts_valid_json_and_rejects_invalid_json() -> None:
    case = DatasetCase(
        test_case_id="SC-1",
        task_category="structured_output",
        input_prompt="Return name and age.",
        evaluation_method="json_schema_validation",
        dataset_version="1.0",
        expected_output_schema={
            "type": "object",
            "required": ["name", "age"],
            "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
        },
    )

    assert evaluate_case(case, '{"name":"Maya","age":28}').passed
    assert not evaluate_case(case, '{"name":"Maya","age":"28"}').passed
    assert not evaluate_case(case, "not json").passed


def test_non_deterministic_dataset_methods_are_not_silently_scored() -> None:
    case = DatasetCase(
        test_case_id="GR-1",
        task_category="reference_grounding",
        input_prompt="Answer from context.",
        evaluation_method="reference_supported_answer",
        dataset_version="1.0",
    )

    with pytest.raises(ValueError, match="not implemented"):
        evaluate_case(case, "some answer")
