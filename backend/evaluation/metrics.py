"""Deterministic checks supported by the initial evaluation core."""

from __future__ import annotations

import math
import re
from typing import Any

from jsonschema import Draft202012Validator

from backend.evaluation.schemas import DatasetCase, EvaluationResult

_NUMBER = re.compile(r"[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)?(?:\.\d+)?")


def _normalized_text(value: Any) -> str:
    return " ".join(str(value).split()).casefold()


def _one_number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = float(value)
        return number if math.isfinite(number) else None
    text = str(value).replace(",", "")
    matches = [
        match.group(0)
        for match in _NUMBER.finditer(text)
        if match.group(0) and any(c.isdigit() for c in match.group(0))
    ]
    if len(matches) != 1:
        return None
    try:
        number = float(matches[0])
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def evaluate_case(
    case: DatasetCase,
    actual: Any,
    *,
    absolute_tolerance: float = 1e-6,
    relative_tolerance: float = 0.0,
) -> EvaluationResult:
    """Evaluate a case using an explicitly deterministic method; unsupported methods fail closed."""
    method = case.evaluation_method.casefold()

    if method == "exact_match":
        passed = case.reference_answer is not None and _normalized_text(
            case.reference_answer
        ) == _normalized_text(actual)
        return EvaluationResult(
            test_case_id=case.test_case_id,
            evaluation_method=method,
            passed=passed,
            score=float(passed),
            expected=case.reference_answer,
            actual=actual,
            details=(
                "Whitespace and letter case are normalized; semantic equivalence is not inferred."
            ),
        )

    if method == "numeric_tolerance":
        if absolute_tolerance < 0 or relative_tolerance < 0:
            raise ValueError("numeric tolerances must be non-negative")
        expected_number = (
            _one_number(case.reference_answer) if case.reference_answer is not None else None
        )
        actual_number = _one_number(actual)
        passed = (
            expected_number is not None
            and actual_number is not None
            and math.isclose(
                expected_number,
                actual_number,
                rel_tol=relative_tolerance,
                abs_tol=absolute_tolerance,
            )
        )
        return EvaluationResult(
            test_case_id=case.test_case_id,
            evaluation_method=method,
            passed=passed,
            score=float(passed),
            expected=expected_number,
            actual=actual_number,
            details=(
                f"Numeric comparison uses absolute tolerance {absolute_tolerance} and "
                f"relative tolerance {relative_tolerance}."
            ),
        )

    if method == "json_schema_validation":
        if case.expected_output_schema is None:
            raise ValueError(f"case {case.test_case_id} has no expected_output_schema")
        candidate = actual
        if isinstance(candidate, str):
            import json

            try:
                candidate = json.loads(candidate)
            except json.JSONDecodeError as exc:
                return EvaluationResult(
                    test_case_id=case.test_case_id,
                    evaluation_method=method,
                    passed=False,
                    score=0.0,
                    expected=case.expected_output_schema,
                    actual=actual,
                    details=f"Response is not valid JSON: {exc.msg}.",
                )
        errors = sorted(
            Draft202012Validator(case.expected_output_schema).iter_errors(candidate),
            key=lambda error: error.json_path,
        )
        passed = not errors
        details = (
            "JSON value satisfies the supplied schema."
            if passed
            else "; ".join(error.message for error in errors[:5])
        )
        return EvaluationResult(
            test_case_id=case.test_case_id,
            evaluation_method=method,
            passed=passed,
            score=float(passed),
            expected=case.expected_output_schema,
            actual=candidate,
            details=details,
        )

    raise ValueError(
        f"evaluation method {case.evaluation_method!r} is not implemented as a deterministic check"
    )
