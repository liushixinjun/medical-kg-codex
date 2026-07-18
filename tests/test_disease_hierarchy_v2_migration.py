from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "公共执行层_kg_pipeline" / "疾病层级与标准诊断V2迁移.py"
SAMPLE_DIR = ROOT / "项目管理中心_project_management" / "139_CDSS标准主数据与疾病分型升级_20260719"


def load_module():
    spec = importlib.util.spec_from_file_location("disease_migration_v2", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_sample_package_passes_v2_validation():
    module = load_module()
    nodes = read_jsonl(SAMPLE_DIR / "05_AMI与心肌病V2样板_nodes.jsonl")
    relations = read_jsonl(SAMPLE_DIR / "06_AMI与心肌病V2样板_relations.jsonl")

    report = module.validate_package(nodes, relations, scope_name="AMI与心肌病样板")

    assert report["error_count"] == 0
    assert report["node_count"] == 20
    assert report["relationship_count"] == 19
    assert report["standard_diagnosis_count"] == 11


def test_validation_rejects_bad_category_and_missing_endpoint():
    module = load_module()
    nodes = [
        {
            "code": "SPEC-1",
            "entityType": "Specialty",
            "name": "测试学科",
            "aliases": [],
            "source_type": "governed_composite",
            "batch_id": "BATCH-1",
            "schema_version": "V2.0",
            "clinical_use_status": "review_ready",
        },
        {
            "code": "CAT-1",
            "entityType": "DiseaseCategory",
            "name": "测试大类",
            "aliases": [],
            "source_type": "governed_composite",
            "batch_id": "BATCH-1",
            "schema_version": "V2.0",
            "clinical_use_status": "review_ready",
            "is_diagnosable": True,
        },
    ]
    relations = [
        {
            "id": "REL-1",
            "source_code": "SPEC-1",
            "relationType": "has_disease_category",
            "target_code": "MISSING",
            "batch_id": "BATCH-1",
            "schema_version": "V2.0",
            "review_status": "passed",
            "clinical_review_status": "not_required",
        }
    ]

    report = module.validate_package(nodes, relations, scope_name="错误包")

    assert report["error_count"] == 2
    assert {item["code"] for item in report["errors"]} == {
        "DISEASE_CATEGORY_DIAGNOSABLE",
        "RELATION_ENDPOINT_MISSING",
    }


def test_legacy_classification_is_split_by_clinical_semantics():
    module = load_module()
    existing = {
        "ST段抬高型心肌梗死": "DIS-CARD-CAD-STEMI",
        "急性心包炎": "DIS-CARD-PERICARD-ACUTE",
    }

    assert module.classify_legacy_classification(
        "ST段抬高型心肌梗死", "CLASS-AMI-STEMI", existing
    )["action"] == "clinical_subtype"
    assert module.classify_legacy_classification(
        "GRACE评分＞140分为高危", "CLASS-GRACE-HIGH", existing
    )["action"] == "risk_stratification"
    assert module.classify_legacy_classification(
        "急性冠脉综合征分类要点5", "CLASS-ACS-POINT-5", existing
    )["action"] == "invalid_fragment"
    assert module.classify_legacy_classification(
        "1979年WHO曾将其分为五型", "CLASS-WHO-OLD", existing
    )["action"] == "invalid_fragment"


def test_structural_relation_conversion_is_one_way_and_deduplicated():
    module = load_module()
    old_relations = [
        {"source_code": "SPEC", "source_type": "Specialty", "relation_type": "has_category", "target_code": "CAT", "target_type": "DiseaseCategory"},
        {"source_code": "DIS", "source_type": "Disease", "relation_type": "belongs_to_category", "target_code": "CAT", "target_type": "DiseaseCategory"},
        {"source_code": "CAT", "source_type": "DiseaseCategory", "relation_type": "has_subcategory", "target_code": "SUB", "target_type": "DiseaseSubcategory"},
        {"source_code": "DIS", "source_type": "Disease", "relation_type": "belongs_to_subcategory", "target_code": "SUB", "target_type": "DiseaseSubcategory"},
        {"source_code": "SUB", "source_type": "DiseaseSubcategory", "relation_type": "has_disease", "target_code": "DIS", "target_type": "Disease"},
    ]

    converted = module.convert_structural_relations(old_relations, canonical_specialty_code="SPEC")
    triples = {(row["source_code"], row["relationType"], row["target_code"]) for row in converted}

    assert triples == {
        ("SPEC", "has_disease_category", "CAT"),
        ("CAT", "has_disease", "DIS"),
        ("CAT", "has_display_group", "SUB"),
        ("SUB", "groups_disease", "DIS"),
    }
    assert len(converted) == 4


def test_list_valued_legacy_endpoint_code_uses_first_canonical_code():
    module = load_module()

    assert module.scalar_endpoint_code(["RF-CARD-001", "RF-CARD-OLD-001"]) == "RF-CARD-001"
    assert module.scalar_endpoint_code("RF-CARD-001") == "RF-CARD-001"
    assert module.scalar_endpoint_code([]) == ""
