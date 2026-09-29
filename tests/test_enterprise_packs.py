"""Reusable financial evaluation packs conform to the shared typed contract."""

import json
from pathlib import Path

from src.enterprise.schemas import EvaluationCaseContract

PACK_DIR = Path(__file__).resolve().parents[1] / "data" / "packs"


def test_aml_and_complaint_packs_validate_without_duplicate_case_ids():
    ids = set()
    for name in ("aml_assistant.json", "complaint_handling.json"):
        pack = json.loads((PACK_DIR / name).read_text(encoding="utf-8"))
        assert pack["synthetic"] is True
        assert pack["cases"]
        for raw in pack["cases"]:
            case = EvaluationCaseContract.model_validate(
                {
                    **raw,
                    "status": "APPROVED",
                    "created_by": "synthetic-author",
                    "approved_by": "synthetic-reviewer",
                }
            )
            assert case.id not in ids
            ids.add(case.id)
