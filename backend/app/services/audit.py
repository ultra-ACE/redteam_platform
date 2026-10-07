import re
from typing import Any

from app.db.models import AuditLog
from app.db.session import SessionLocal
from app.services.base import BaseService
from app.services.uow import UnitOfWork

_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

_DOWNLOAD_ROUTES = (
    (re.compile(r"^/api/v1/reports/(?P<resource_id>\d+)/download$"), "report.download", "report"),
    (re.compile(r"^/api/v1/files/(?P<resource_id>\d+)/download$"), "file.download", "file"),
)

_AUDIT_ROUTES = (
    (re.compile(r"^/api/v1/models$"), "POST", "model.create", "model"),
    (re.compile(r"^/api/v1/models/(?P<resource_id>\d+)/health-check$"), "POST", "model.health_check", "model"),
    (re.compile(r"^/api/v1/system-configs/[^/]+$"), "PATCH", "system_config.update", "system_config"),
    (re.compile(r"^/api/v1/benchmarks/import$"), "POST", "benchmark.import", "benchmark"),
    (re.compile(r"^/api/v1/test-cases/(?P<resource_id>\d+)$"), "PATCH", "test_case.update", "test_case"),
    (re.compile(r"^/api/v1/risk-taxonomies$"), "POST", "risk_taxonomy.create", "risk_taxonomy"),
    (re.compile(r"^/api/v1/risk-taxonomies/(?P<resource_id>\d+)/categories$"), "POST", "risk_category.create", "risk_category"),
    (re.compile(r"^/api/v1/benchmark-versions/(?P<resource_id>\d+)/risk-mappings/batch$"), "POST", "risk_mapping.batch_upsert", "risk_mapping"),
    (re.compile(r"^/api/v1/attack-methods$"), "POST", "attack_method.create", "attack_method"),
    (re.compile(r"^/api/v1/attack-methods/(?P<resource_id>\d+)$"), "PATCH", "attack_method.update", "attack_method"),
    (re.compile(r"^/api/v1/attack-methods/(?P<resource_id>\d+)$"), "DELETE", "attack_method.disable", "attack_method"),
    (re.compile(r"^/api/v1/attack-templates$"), "POST", "attack_template.create", "attack_template"),
    (re.compile(r"^/api/v1/attack-templates/(?P<resource_id>\d+)/validate$"), "POST", "attack_template.validate", "attack_template"),
    (re.compile(r"^/api/v1/attack-templates/(?P<resource_id>\d+)/preview$"), "POST", "attack_template.preview", "attack_template"),
    (re.compile(r"^/api/v1/attack-templates/(?P<resource_id>\d+)/versions$"), "POST", "attack_template.create_version", "attack_template"),
    (re.compile(r"^/api/v1/attack-templates/(?P<resource_id>\d+)/publish$"), "POST", "attack_template.publish", "attack_template"),
    (re.compile(r"^/api/v1/attack-templates/(?P<resource_id>\d+)$"), "PATCH", "attack_template.update", "attack_template"),
    (re.compile(r"^/api/v1/attack-templates/(?P<resource_id>\d+)$"), "DELETE", "attack_template.disable", "attack_template"),
    (re.compile(r"^/api/v1/evaluation-tasks$"), "POST", "evaluation_task.create", "evaluation_task"),
    (re.compile(r"^/api/v1/evaluation-tasks/(?P<resource_id>\d+)/actions/start$"), "POST", "evaluation_task.start", "evaluation_task"),
    (re.compile(r"^/api/v1/evaluation-tasks/(?P<resource_id>\d+)/actions/cancel$"), "POST", "evaluation_task.cancel", "evaluation_task"),
    (re.compile(r"^/api/v1/evaluation-tasks/(?P<resource_id>\d+)/actions/retry-failed$"), "POST", "evaluation_task.retry_failed", "evaluation_task"),
    (re.compile(r"^/api/v1/judge-profiles$"), "POST", "judge_profile.create", "judge_profile"),
    (re.compile(r"^/api/v1/judge-profiles/(?P<resource_id>\d+)$"), "PATCH", "judge_profile.update", "judge_profile"),
    (re.compile(r"^/api/v1/judge-profiles/(?P<resource_id>\d+)$"), "DELETE", "judge_profile.disable", "judge_profile"),
    (re.compile(r"^/api/v1/judge-results/(?P<resource_id>\d+)/re-evaluate$"), "POST", "judge_result.re_evaluate", "judge_result"),
    (re.compile(r"^/api/v1/manual-reviews$"), "POST", "manual_review.create", "manual_review"),
    (re.compile(r"^/api/v1/manual-reviews/(?P<resource_id>\d+)$"), "PATCH", "manual_review.update", "manual_review"),
    (re.compile(r"^/api/v1/reports$"), "POST", "report.create", "report"),
    (re.compile(r"^/api/v1/report-templates$"), "POST", "report_template.create", "report_template"),
    (re.compile(r"^/api/v1/report-templates/(?P<resource_id>\d+)/versions$"), "POST", "report_template.create_version", "report_template"),
    (re.compile(r"^/api/v1/report-template-versions/(?P<resource_id>\d+)/publish$"), "POST", "report_template_version.publish", "report_template_version"),
    (re.compile(r"^/api/v1/files$"), "POST", "file.upload", "file"),
)


class AuditLogService(BaseService):
    def record(
        self,
        *,
        actor: str,
        action: str,
        resource_type: str,
        resource_id: int | None = None,
        before_data: dict[str, Any] | None = None,
        after_data: dict[str, Any] | None = None,
        request_id: str | None = None,
        ip: str | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            actor=actor,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            before_data=before_data,
            after_data=after_data,
            request_id=request_id,
            ip=ip,
        )
        return self.uow.audit_logs.add(entry)


def write_audit_log(
    *,
    actor: str,
    action: str,
    resource_type: str,
    resource_id: int | None,
    before_data: dict[str, Any] | None,
    after_data: dict[str, Any] | None,
    request_id: str,
    ip: str | None,
) -> None:
    session = SessionLocal()
    uow = UnitOfWork(session)
    try:
        AuditLogService(uow).record(
            actor=actor,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            before_data=before_data,
            after_data=after_data,
            request_id=request_id,
            ip=ip,
        )
        uow.commit()
    except Exception:
        uow.rollback()
        raise
    finally:
        uow.close()


def resolve_audit_target(method: str, path: str) -> tuple[str, str, int | None] | None:
    if method == "GET":
        for pattern, action, resource_type in _DOWNLOAD_ROUTES:
            match = pattern.match(path)
            if match:
                return action, resource_type, _resource_id(match)
        return None

    if method not in _WRITE_METHODS:
        return None

    for pattern, expected_method, action, resource_type in _AUDIT_ROUTES:
        if method != expected_method:
            continue
        match = pattern.match(path)
        if match:
            return action, resource_type, _resource_id(match, path)

    if not path.startswith("/api/v1/"):
        return None

    resource_type = _fallback_resource_type(path)
    return f"{resource_type}.{method.lower()}", resource_type, _extract_resource_id(path)


def _resource_id(match: re.Match[str] | None, path: str | None = None) -> int | None:
    if match and "resource_id" in match.groupdict():
        value = match.group("resource_id")
        if value is not None:
            return int(value)
    return _extract_resource_id(path or "")


def _extract_resource_id(path: str) -> int | None:
    for segment in path.split("/"):
        if segment.isdigit():
            return int(segment)
    return None


def _fallback_resource_type(path: str) -> str:
    segments = [segment for segment in path.split("/") if segment and segment not in {"api", "v1"}]
    if not segments:
        return "system"
    value = segments[0].replace("-", "_")
    if value == "evaluation_tasks":
        return "evaluation_task"
    return value
