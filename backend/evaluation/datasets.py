"""Load, validate, and fingerprint CSV or JSON evaluation datasets."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, SchemaError
from pydantic import ValidationError

from backend.evaluation.schemas import DatasetCase, DatasetDocument

CSV_REQUIRED_COLUMNS = {
    "test_case_id",
    "task_category",
    "input_prompt",
    "reference_answer",
    "evaluation_method",
    "dataset_version",
}


class DatasetValidationError(ValueError):
    """Raised when a dataset is malformed or contains ambiguous case IDs."""


def _case_list(cases: list[dict[str, Any]]) -> list[DatasetCase]:
    try:
        validated = [DatasetCase.model_validate(item) for item in cases]
    except ValidationError as exc:
        raise DatasetValidationError(str(exc)) from exc

    seen: set[str] = set()
    for case in validated:
        if case.test_case_id in seen:
            raise DatasetValidationError(f"duplicate test_case_id: {case.test_case_id}")
        seen.add(case.test_case_id)

    versions = {case.dataset_version for case in validated}
    if len(versions) > 1:
        raise DatasetValidationError("all cases in a dataset must use the same dataset_version")
    for case in validated:
        if case.expected_output_schema is not None:
            try:
                Draft202012Validator.check_schema(case.expected_output_schema)
            except SchemaError as exc:
                raise DatasetValidationError(
                    f"case {case.test_case_id} has an invalid expected_output_schema: {exc.message}"
                ) from exc
    return validated


def load_dataset(path: str | Path) -> DatasetDocument:
    """Load a CSV or JSON dataset and calculate a SHA-256 over its exact source bytes."""
    source = Path(path)
    raw = source.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise DatasetValidationError("dataset must be UTF-8 encoded") from exc

    if source.suffix.lower() == ".csv":
        reader = csv.DictReader(io.StringIO(text, newline=""))
        headers = set(reader.fieldnames or [])
        missing = CSV_REQUIRED_COLUMNS - headers
        if missing:
            raise DatasetValidationError(
                f"CSV is missing required columns: {', '.join(sorted(missing))}"
            )
        rows: list[dict[str, Any]] = []
        for line_number, row in enumerate(reader, start=2):
            if None in row:
                raise DatasetValidationError(
                    f"CSV row {line_number} has more values than the header"
                )
            normalized: dict[str, Any] = dict(row)
            for key in ("reference_answer", "reference_context", "difficulty"):
                if normalized.get(key) == "":
                    normalized[key] = None
            schema_value = normalized.get("expected_output_schema")
            if schema_value == "":
                normalized["expected_output_schema"] = None
            if schema_value:
                try:
                    normalized["expected_output_schema"] = json.loads(schema_value)
                except json.JSONDecodeError as exc:
                    raise DatasetValidationError(
                        f"CSV row {line_number} has invalid expected_output_schema JSON"
                    ) from exc
            normalized["tags"] = [
                tag.strip() for tag in (normalized.get("tags") or "").split(";") if tag.strip()
            ]
            rows.append(normalized)
        cases = _case_list(rows)
        versions = {case.dataset_version for case in cases}
        version = next(iter(versions))
        name, description = source.stem, ""
    elif source.suffix.lower() == ".json":
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise DatasetValidationError(f"invalid JSON: {exc.msg}") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("cases"), list):
            raise DatasetValidationError("JSON dataset must be an object containing a cases array")
        try:
            cases = _case_list(payload["cases"])
        except DatasetValidationError:
            raise
        version = str(payload.get("dataset_version", "")).strip()
        name = str(payload.get("dataset_name", source.stem)).strip()
        description = str(payload.get("description", ""))
        if not version or not name:
            raise DatasetValidationError(
                "JSON dataset must include non-empty dataset_name and dataset_version"
            )
        if any(case.dataset_version != version for case in cases):
            raise DatasetValidationError(
                "case dataset_version values must match the top-level dataset_version"
            )
    else:
        raise DatasetValidationError("supported dataset formats are .csv and .json")

    try:
        return DatasetDocument(
            dataset_name=name,
            dataset_version=version,
            description=description,
            source_sha256=digest,
            cases=cases,
        )
    except ValidationError as exc:
        raise DatasetValidationError(str(exc)) from exc
