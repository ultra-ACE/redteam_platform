from pathlib import Path

import yaml

from app.main import app


def test_openapi_contains_expected_paths() -> None:
    schema = app.openapi()
    paths = schema["paths"]
    expected = {
        "/health",
        "/system-configs",
        "/system-configs/{config_key}",
        "/audit-logs",
        "/benchmarks/import",
        "/benchmarks",
        "/benchmarks/{benchmark_id}/versions",
        "/risk-taxonomies",
        "/risk-taxonomies/{taxonomy_id}/categories",
        "/benchmark-versions/{benchmark_version_id}/risk-mappings/batch",
        "/benchmark-versions/{benchmark_version_id}/mapping-status",
        "/test-cases",
        "/test-cases/{test_case_id}",
        "/models",
        "/models/{model_id}/health-check",
        "/attack-methods",
        "/attack-templates",
        "/attack-templates/{template_id}/preview",
        "/evaluation-tasks",
        "/evaluation-tasks/{task_id}/status",
        "/evaluation-tasks/{task_id}/results",
        "/evaluation-tasks/{task_id}/actions/start",
        "/evaluation-tasks/{task_id}/actions/cancel",
        "/evaluation-tasks/{task_id}/actions/retry-failed",
        "/judge-profiles",
        "/evaluation-tasks/{task_id}/judge-trust",
        "/judge-results/{judge_result_id}/re-evaluate",
        "/task-attempts/{attempt_id}/risk",
        "/evaluation-tasks/{task_id}/risk-summary",
        "/manual-reviews",
        "/evaluation-tasks/{task_id}/statistics",
        "/reports",
        "/reports/{report_id}",
        "/reports/{report_id}/download",
        "/files",
        "/files/{file_id}/download",
        "/evaluation-tasks/{task_id}/events",
        "/report-templates",
        "/report-templates/{template_id}/versions",
        "/report-template-versions/{version_id}",
        "/report-template-versions/{version_id}/publish",
    }
    expected = {f"/api/v1{path}" for path in expected}
    assert expected.issubset(set(paths))


def test_openapi_operations_have_single_tag() -> None:
    schema = app.openapi()
    methods = {"get", "post", "patch", "put", "delete"}
    for path, path_item in schema["paths"].items():
        for method, operation in path_item.items():
            if method not in methods:
                continue
            tags = operation.get("tags", [])
            assert len(tags) == 1, f"{method.upper()} {path} has tags: {tags}"


def test_static_openapi_matches_live_operations() -> None:
    live_schema = app.openapi()
    static_schema = yaml.safe_load(
        (Path(__file__).resolve().parents[2] / "openapi.yaml").read_text(encoding="utf-8")
    )
    methods = {"get", "post", "put", "patch", "delete"}

    def operations(schema):
        return {
            (method.upper(), path, operation.get("operationId"))
            for path, path_item in schema["paths"].items()
            for method, operation in path_item.items()
            if method in methods
        }

    assert operations(static_schema) == operations(live_schema)
