import hashlib
import html
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.db.models import Report, StoredFile
from app.services.base import BaseService
from app.services.results import EvaluationResultService
from app.services.statistics import StatisticsService


class RawHtml(str):
    """Already escaped HTML produced by this module."""


class ReportService(BaseService):
    @staticmethod
    def _attempt_url(task_id: Any, attempt_id: Any) -> str:
        base = settings.frontend_base_url.rstrip("/")
        return f"{base}/tasks/{task_id}?attempt={attempt_id}"

    def _attempt_link_html(self, task_id: Any, attempt_id: Any) -> str:
        url = html.escape(self._attempt_url(task_id, attempt_id), quote=True)
        return f'<a href="{url}">{html.escape(str(attempt_id))}</a>'

    def create_report(self, payload: Any) -> Report:
        report = Report(
            task_id=payload.task_id,
            report_type=payload.report_type,
            format="html",
            status="queued",
            filter_snapshot=payload.filters,
        )
        return self.uow.reports.add(report)

    def get_report(self, report_id: int) -> Report | None:
        return self.uow.reports.get(report_id)

    def get_download_info(self, report_id: int) -> dict[str, str] | None:
        report = self.uow.reports.get(report_id)
        if report is None or report.status != "ready" or report.file_id is None:
            return None
        stored_file = self.uow.files.get(report.file_id)
        if stored_file is None:
            return None
        return {
            "path": stored_file.stored_path,
            "filename": stored_file.original_name,
            "mime_type": stored_file.mime_type or "text/html",
        }

    def generate_report(self, report_id: int, base_dir: Path | None = None) -> Report | None:
        report = self.uow.reports.get(report_id)
        if report is None or report.status != "queued":
            return report
        if not self.uow.reports.claim_for_generation(report_id):
            self.uow.session.rollback()
            return self.uow.reports.get(report_id)
        self.uow.commit()
        report = self.uow.reports.get(report_id)

        task = self.uow.evaluation_tasks.get(report.task_id)
        if task is None:
            report.status = "failed"
            report.error_message = "task not found"
            report.finished_at = datetime.now(timezone.utc)
            self.uow.session.flush()
            self.uow.commit()
            return report

        try:
            statistics = StatisticsService(self.uow).get_task_statistics(report.task_id)
            results = EvaluationResultService(self.uow).list_all_results(report.task_id)
            data = {
                "task": {
                    "task_id": task.id,
                    "name": task.name,
                    "status": task.status,
                    "progress": task.progress,
                    "total_cases": task.total_cases,
                    "completed_cases": task.completed_cases,
                    "failed_cases": task.failed_cases,
                },
                "statistics": statistics.model_dump(mode="json") if statistics else {},
                "results": [item.model_dump(mode="json") for item in results],
            }
            content = self._build_html(data).encode("utf-8")
            output_dir = (base_dir or (Path(settings.data_dir) / "reports")) / str(report.id)
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"report-{report.id}.html"
            output_path.write_bytes(content)

            stored_file = StoredFile(
                original_name=f"report-{report.id}.html",
                stored_path=str(output_path),
                mime_type="text/html",
                size_bytes=len(content),
                sha256=hashlib.sha256(content).hexdigest(),
                owner_type="report",
                owner_id=report.id,
            )
            self.uow.files.add(stored_file)
            report.file_id = stored_file.id
            report.status = "ready"
            report.finished_at = datetime.now(timezone.utc)
            report.error_message = None
            self.uow.session.flush()
            self.uow.commit()
            return report
        except Exception as exc:
            self.uow.rollback()
            report = self.uow.reports.get(report_id)
            if report is not None:
                report.status = "failed"
                report.error_message = str(exc)
                report.finished_at = datetime.now(timezone.utc)
                self.uow.session.flush()
                self.uow.commit()
            return report

    def _build_html(self, data: dict[str, Any]) -> str:
        task = data["task"]
        stats = data["statistics"]
        results = data["results"]
        verdict_rows = list((stats.get("judge_verdict_distribution") or {}).items())
        dataset_rows = list((stats.get("dataset_type_distribution") or {}).items())
        result_rows = [
            (
                RawHtml(self._attempt_link_html(task["task_id"], item["attempt_id"])),
                item.get("external_id") or "",
                item.get("dataset_type") or "",
                item.get("sample_kind") or "",
                item.get("model_id"),
                (item.get("judge") or {}).get("verdict", ""),
                (item.get("rule_validation") or {}).get("hit_count", 0),
                item.get("manual_review_status", "none"),
            )
            for item in results
        ]
        return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>大模型越狱攻击安全评测报告</title>
  <style>
    :root {{ color-scheme: light; }}
    body {{ margin: 0; padding: 32px; color: #172033; background: #f6f8fb; font-family: "Microsoft YaHei", Arial, sans-serif; }}
    main {{ max-width: 1180px; margin: 0 auto; }}
    h1, h2 {{ margin: 0 0 16px; }}
    section {{ margin: 0 0 24px; padding: 22px; border: 1px solid #dce3ee; border-radius: 10px; background: #fff; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ padding: 9px 10px; border-bottom: 1px solid #e7ebf2; text-align: left; vertical-align: top; }}
    th {{ background: #f2f5fa; }}
    a {{ color: #2457c5; }}
  </style>
</head>
<body>
<main>
  <h1>大模型越狱攻击安全评测报告</h1>
  <section>
    <h2>任务信息</h2>
    {self._html_table(["任务 ID", "任务名称", "状态", "总用例", "已完成", "失败数"], [[task["task_id"], task["name"], task["status"], task["total_cases"], task["completed_cases"], task["failed_cases"]]])}
  </section>
  <section>
    <h2>总体指标</h2>
    {self._html_table(["指标", "数值"], [["结果总数", stats.get("total_results", 0)], ["攻击成功率", stats.get("attack_success_rate", 0)], ["Judge 平均可信度", stats.get("judge_average_trust", 0)], ["人工复核率", stats.get("manual_review_rate", 0)], ["规则命中率", stats.get("rule_hit_rate", 0)]])}
  </section>
  <section>
    <h2>Judge 判定分布</h2>
    {self._html_table(["判定", "数量"], verdict_rows)}
  </section>
  <section>
    <h2>数据集类型分布</h2>
    {self._html_table(["数据集类型", "数量"], dataset_rows)}
  </section>
  <section>
    <h2>逐条结果摘要</h2>
    {self._html_table(["尝试 ID", "外部用例 ID", "数据集类型", "样本类型", "模型 ID", "Judge", "规则命中", "复核状态"], result_rows)}
  </section>
</main>
</body>
</html>
"""

    def _html_table(self, headers: list[str], rows: list[list[Any]]) -> str:
        def render_cell(value: Any) -> str:
            if isinstance(value, RawHtml):
                return str(value)
            return html.escape(str(value))

        head = "".join(f"<th>{html.escape(str(item))}</th>" for item in headers)
        body = "".join(
            "<tr>" + "".join(f"<td>{render_cell(value)}</td>" for value in row) + "</tr>"
            for row in rows
        )
        return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


class ReportAutomationService(BaseService):
    def trigger_if_task_complete(self, task_id: int, report_format: str | None = None) -> Report | None:
        report, _ = self.ensure_auto_report(task_id)
        return report

    def ensure_auto_report(self, task_id: int) -> tuple[Report | None, bool]:
        task = self.uow.evaluation_tasks.get(task_id)
        if task is None:
            return None, False
        task_cases = self.uow.task_cases.list(page=1, page_size=100000, task_id=task_id)
        if not task_cases:
            return None, False
        terminal = {"succeeded", "failed", "cancelled", "skipped"}
        if any(task_case.status not in terminal for task_case in task_cases):
            return None, False
        existing = self.uow.reports.list(
            page=1,
            page_size=1,
            task_id=task_id,
            report_type="auto",
        )
        if existing:
            return existing[0], False
        report = Report(
            task_id=task_id,
            report_type="auto",
            format="html",
            status="queued",
            filter_snapshot={},
        )
        return self.uow.reports.add(report), True
