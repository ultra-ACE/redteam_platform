import csv
import hashlib
import html
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jinja2 import Template

from app.core.config import settings
from app.db.models import Report, ReportTemplate, ReportTemplateVersion, StoredFile, TaskCase
from app.services.base import BaseService
from app.services.results import EvaluationResultService
from app.services.statistics import StatisticsService


class RawHtml(str):
    """已由本模块拼装并转义的 HTML 片段，_html_table 不再二次转义。"""


class ReportService(BaseService):
    @staticmethod
    def _attempt_url(task_id: Any, attempt_id: Any) -> str:
        """生成指向前端「任务详情 + 自动展开尝试抽屉」的绝对链接。"""
        base = settings.frontend_base_url.rstrip("/")
        return f"{base}/tasks/{task_id}?attempt={attempt_id}"

    def _attempt_link_html(self, task_id: Any, attempt_id: Any) -> str:
        url = html.escape(self._attempt_url(task_id, attempt_id), quote=True)
        return f'<a href="{url}">{html.escape(str(attempt_id))}</a>'

    def create_report(self, payload: Any) -> Report:
        report = Report(
            task_id=payload.task_id,
            report_type=payload.report_type,
            format=payload.format.value if hasattr(payload.format, "value") else payload.format,
            template_version_id=payload.template_version_id,
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
            "mime_type": stored_file.mime_type or "application/octet-stream",
        }

    def generate_report(self, report_id: int, base_dir: Path | None = None) -> Report | None:
        report = self.uow.reports.get(report_id)
        if report is None:
            return None

        task = self.uow.evaluation_tasks.get(report.task_id)
        if task is None:
            report.status = "failed"
            report.error_message = "task not found"
            report.finished_at = datetime.now(timezone.utc)
            self.uow.session.flush()
            self.uow.commit()
            return report

        report.status = "generating"
        self.uow.session.flush()
        self.uow.commit()

        try:
            statistics = StatisticsService(self.uow).get_task_statistics(report.task_id, persist=True)
            results = EvaluationResultService(self.uow).list_all_results(report.task_id)
            data = {
                "report": {
                    "report_id": report.id,
                    "task_id": report.task_id,
                    "report_type": report.report_type,
                    "format": report.format,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                },
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
                "results": [
                    {
                        **item.model_dump(mode="json"),
                        "detail_url": self._attempt_url(report.task_id, item.attempt_id),
                    }
                    for item in results
                ],
            }

            template_version = (
                self.uow.report_template_versions.get(report.template_version_id)
                if report.template_version_id
                else None
            )
            if template_version is not None and template_version.format != "pdf":
                rendered = Template(template_version.content).render(**data)
                content, extension, mime_type = self._content_for_format(template_version.format, rendered)
            else:
                content, extension, mime_type = self._render_content(report.format, data)
            output_dir = (base_dir or (Path(settings.data_dir) / "reports")) / str(report.id)
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"report-{report.id}.{extension}"
            output_path.write_bytes(content)

            stored_file = StoredFile(
                original_name=f"report-{report.id}.{extension}",
                stored_path=str(output_path),
                mime_type=mime_type,
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

    def _content_for_format(self, report_format: str, content: str) -> tuple[bytes, str, str]:
        if report_format == "json":
            return content.encode("utf-8"), "json", "application/json"
        if report_format == "md":
            return content.encode("utf-8"), "md", "text/markdown"
        if report_format == "html":
            return content.encode("utf-8"), "html", "text/html"
        if report_format == "csv":
            return content.encode("utf-8-sig"), "csv", "text/csv"
        raise ValueError(f"unsupported template format: {report_format}")

    def _render_content(self, report_format: str, data: dict[str, Any]) -> tuple[bytes, str, str]:
        if report_format == "json":
            return json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"), "json", "application/json"
        if report_format == "md":
            return self._build_markdown(data).encode("utf-8"), "md", "text/markdown"
        if report_format == "html":
            return self._build_html(data).encode("utf-8"), "html", "text/html"
        if report_format == "csv":
            return self._build_csv(data).encode("utf-8-sig"), "csv", "text/csv"
        if report_format == "pdf":
            return self._build_pdf(data), "pdf", "application/pdf"
        raise ValueError(f"unsupported report format: {report_format}")

    def _build_markdown(self, data: dict[str, Any]) -> str:
        task = data["task"]
        stats = data["statistics"]
        results = data["results"]
        lines = [
            "# 大模型安全评测报告",
            "",
            "## 任务信息",
            "",
            "| 项目 | 内容 |",
            "|---|---|",
            f"| 任务 ID | {task['task_id']} |",
            f"| 任务名称 | {task['name']} |",
            f"| 任务状态 | {task['status']} |",
            f"| 总用例数 | {task['total_cases']} |",
            f"| 已完成 | {task['completed_cases']} |",
            f"| 失败数 | {task['failed_cases']} |",
            "",
            "## 总体指标",
            "",
            "| 指标 | 数值 |",
            "|---|---:|",
            f"| 结果总数 | {stats.get('total_results', 0)} |",
            f"| 安全 / 不安全 / 不确定 | {stats.get('safe_count', 0)} / {stats.get('unsafe_count', 0)} / {stats.get('uncertain_count', 0)} |",
            f"| 攻击成功率 | {stats.get('attack_success_rate', 0)} |",
            f"| 平均风险分 | {stats.get('average_risk_score', 0)} |",
            f"| Judge 平均可信度 | {stats.get('judge_average_trust', 0)} |",
            f"| 人工复核率 | {stats.get('manual_review_rate', 0)} |",
            f"| 规则命中率 | {stats.get('rule_hit_rate', 0)} |",
            "",
            "## 风险等级分布",
            "",
            "| 风险等级 | 数量 |",
            "|---|---:|",
        ]
        for level, count in stats.get("risk_level_distribution", {}).items():
            lines.append(f"| {level} | {count} |")
        lines.extend([
            "",
            "## 风险类别分布",
            "",
            "| 风险类别 | 数量 | 平均风险分 |",
            "|---|---:|---:|",
        ])
        for item in stats.get("risk_category_distribution", []):
            lines.append(f"| {item['code']} | {item['count']} | {item['average_score']} |")

        lines.extend([
            "",
            "## 模型对比",
            "",
            "| 模型 ID | 数量 | 不安全数 | 攻击成功率 | 平均风险分 |",
            "|---:|---:|---:|---:|---:|",
        ])
        for item in stats.get("model_breakdown", []):
            lines.append(
                f"| {item['model_id']} | {item['count']} | {item['unsafe_count']} | "
                f"{item['attack_success_rate']} | {item['average_risk_score']} |"
            )

        lines.extend([
            "",
            "## 高风险案例 Top 10",
            "",
            "> 尝试 ID 为可点击链接，点击后打开前端任务详情并自动展开该条完整证据链（原始提示词、模型输出、Judge、规则命中、六维风险）。",
            "",
            "| 尝试 ID | 外部用例 ID | 模型 ID | 模板 ID | 风险分 | 风险等级 |",
            "|---:|---|---:|---:|---:|---|",
        ])
        for item in stats.get("top_risky_cases", []):
            link = f"[{item['attempt_id']}]({self._attempt_url(task['task_id'], item['attempt_id'])})"
            lines.append(
                f"| {link} | {item.get('external_id') or ''} | {item['model_id']} | "
                f"{item.get('attack_template_id') or ''} | {item['overall_score']} | {item['risk_level']} |"
            )

        lines.extend([
            "",
            "## 逐条结果摘要",
            "",
            "| 尝试 ID | 用例 ID | 模型 ID | Judge | 风险分 | 风险等级 | 复核状态 |",
            "|---:|---|---:|---|---:|---|---|",
        ])
        for item in results[:200]:
            judge = item.get("judge") or {}
            risk = item.get("risk") or {}
            link = f"[{item['attempt_id']}]({self._attempt_url(task['task_id'], item['attempt_id'])})"
            lines.append(
                f"| {link} | {item.get('external_id') or ''} | {item['model_id']} | "
                f"{judge.get('verdict', '')} | {risk.get('overall_score', '')} | "
                f"{risk.get('risk_level', '')} | {item.get('manual_review_status', '')} |"
            )
        return "\n".join(lines) + "\n"

    def _build_html(self, data: dict[str, Any]) -> str:
        task = data["task"]
        stats = data["statistics"]
        results = data["results"]
        level_rows = [(level, count) for level, count in stats.get("risk_level_distribution", {}).items()]
        category_rows = [
            (item["code"], item["count"], item["average_score"])
            for item in stats.get("risk_category_distribution", [])
        ]
        result_rows = [
            (
                RawHtml(self._attempt_link_html(task["task_id"], item["attempt_id"])),
                item.get("external_id") or "",
                item["model_id"],
                (item.get("judge") or {}).get("verdict", ""),
                (item.get("risk") or {}).get("overall_score", ""),
                (item.get("risk") or {}).get("risk_level", ""),
                item.get("manual_review_status", ""),
            )
            for item in results[:200]
        ]
        top_rows = [
            (
                RawHtml(self._attempt_link_html(task["task_id"], item["attempt_id"])),
                item.get("external_id") or "",
                item["model_id"],
                item.get("attack_template_id") or "",
                item["overall_score"],
                item["risk_level"],
            )
            for item in stats.get("top_risky_cases", [])
        ]
        return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>大模型安全评测报告</title>
  <style>
    body {{ font-family: Arial, "Microsoft YaHei", sans-serif; margin: 32px; color: #222; }}
    table {{ border-collapse: collapse; width: 100%; margin-bottom: 24px; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
    th {{ background: #f3f6fa; }}
  </style>
</head>
<body>
  <h1>大模型安全评测报告</h1>
  <h2>任务信息</h2>
  {self._html_table(["任务 ID", "任务名称", "状态", "总用例", "已完成", "失败数"], [[task["task_id"], task["name"], task["status"], task["total_cases"], task["completed_cases"], task["failed_cases"]]])}
  <h2>总体指标</h2>
  {self._html_table(["指标", "数值"], [["结果总数", stats.get("total_results", 0)], ["攻击成功率", stats.get("attack_success_rate", 0)], ["平均风险分", stats.get("average_risk_score", 0)], ["Judge 平均可信度", stats.get("judge_average_trust", 0)], ["人工复核率", stats.get("manual_review_rate", 0)], ["规则命中率", stats.get("rule_hit_rate", 0)]])}
  <h2>风险等级分布</h2>
  {self._html_table(["风险等级", "数量"], level_rows)}
  <h2>风险类别分布</h2>
  {self._html_table(["风险类别", "数量", "平均风险分"], category_rows)}
  <h2>高风险案例 Top 10</h2>
  <p>点击尝试 ID 可打开前端任务详情，并自动展开该条的原始提示词、模型输出、Judge 判断、规则命中与六维风险。</p>
  {self._html_table(["尝试 ID", "外部用例 ID", "模型 ID", "模板 ID", "风险分", "风险等级"], top_rows)}
  <h2>逐条结果摘要</h2>
  {self._html_table(["尝试 ID", "用例 ID", "模型 ID", "Judge", "风险分", "风险等级", "复核状态"], result_rows)}
</body>
</html>
"""

    def _build_csv(self, data: dict[str, Any]) -> str:
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer)
        task = data["task"]
        stats = data["statistics"]
        writer.writerow(["section", "key", "value"])
        for key, value in task.items():
            writer.writerow(["task", key, value])
        for key, value in stats.items():
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)
            writer.writerow(["statistics", key, value])
        writer.writerow([])
        writer.writerow([
            "attempt_id",
            "external_id",
            "model_id",
            "attack_template_id",
            "verdict",
            "risk_score",
            "risk_level",
            "manual_review_status",
            "detail_url",
        ])
        for item in data["results"]:
            judge = item.get("judge") or {}
            risk = item.get("risk") or {}
            writer.writerow([
                item["attempt_id"],
                item.get("external_id") or "",
                item["model_id"],
                item.get("attack_template_id") or "",
                judge.get("verdict", ""),
                risk.get("overall_score", ""),
                risk.get("risk_level", ""),
                item.get("manual_review_status", ""),
                self._attempt_url(task["task_id"], item["attempt_id"]),
            ])
        return buffer.getvalue()

    def _build_pdf(self, data: dict[str, Any]) -> bytes:
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.cidfonts import UnicodeCIDFont
            from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
        except ImportError as exc:
            raise RuntimeError("reportlab is required for PDF report generation") from exc

        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        buffer = io.BytesIO()
        document = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        styles["Title"].fontName = "STSong-Light"
        styles["Heading2"].fontName = "STSong-Light"
        styles["BodyText"].fontName = "STSong-Light"

        task = data["task"]
        stats = data["statistics"]
        story = [
            Paragraph("大模型安全评测报告", styles["Title"]),
            Spacer(1, 12),
            Paragraph("任务信息", styles["Heading2"]),
            Table(
                [
                    ["任务 ID", task["task_id"]],
                    ["任务名称", task["name"]],
                    ["状态", task["status"]],
                    ["总用例数", task["total_cases"]],
                    ["已完成", task["completed_cases"]],
                    ["失败数", task["failed_cases"]],
                ],
                colWidths=[120, 360],
            ),
            Spacer(1, 12),
            Paragraph("总体指标", styles["Heading2"]),
            Table(
                [
                    ["结果总数", stats.get("total_results", 0)],
                    ["攻击成功率", stats.get("attack_success_rate", 0)],
                    ["平均风险分", stats.get("average_risk_score", 0)],
                    ["Judge 平均可信度", stats.get("judge_average_trust", 0)],
                    ["人工复核率", stats.get("manual_review_rate", 0)],
                    ["规则命中率", stats.get("rule_hit_rate", 0)],
                ],
                colWidths=[180, 300],
            ),
        ]

        for table in story:
            if isinstance(table, Table):
                table.setStyle(
                    TableStyle(
                        [
                            ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
                            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                            ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ]
                    )
                )

        story.append(Spacer(1, 12))
        story.append(Paragraph("高风险案例 Top 10", styles["Heading2"]))
        story.append(Paragraph("尝试 ID 为可点击链接，点击可打开前端任务详情并展开完整证据链。", styles["BodyText"]))
        top_rows = [["尝试 ID", "用例 ID", "风险分", "风险等级"]]
        for item in stats.get("top_risky_cases", []):
            url = self._attempt_url(task["task_id"], item["attempt_id"]).replace("&", "&amp;")
            top_rows.append([
                Paragraph(f'<link href="{url}"><u>{item["attempt_id"]}</u></link>', styles["BodyText"]),
                item.get("external_id") or "",
                item["overall_score"],
                item["risk_level"],
            ])
        top_table = Table(top_rows, colWidths=[100, 180, 100, 100])
        top_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ]
            )
        )
        story.append(top_table)
        document.build(story)
        return buffer.getvalue()

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


class ReportTemplateService(BaseService):
    def list_templates(self, page: int = 1, page_size: int = 20) -> list[ReportTemplate]:
        return self.uow.report_templates.list(page=page, page_size=page_size)

    def create_template(self, payload: Any) -> ReportTemplate:
        template = ReportTemplate(
            code=payload.code,
            name=payload.name,
            description=payload.description,
            status="active",
        )
        return self.uow.report_templates.add(template)

    def list_versions(self, template_id: int, page: int = 1, page_size: int = 20) -> list[ReportTemplateVersion]:
        return self.uow.report_template_versions.list(
            page=page,
            page_size=page_size,
            template_id=template_id,
        )

    def create_version(self, template_id: int, payload: Any) -> ReportTemplateVersion:
        version = ReportTemplateVersion(
            template_id=template_id,
            version=payload.version,
            format=payload.format.value if hasattr(payload.format, "value") else payload.format,
            content=payload.content,
            variables_schema=payload.variables_schema,
            status=payload.status,
        )
        return self.uow.report_template_versions.add(version)

    def get_version(self, version_id: int) -> ReportTemplateVersion | None:
        return self.uow.report_template_versions.get(version_id)

    def publish_version(self, version_id: int) -> ReportTemplateVersion | None:
        version = self.uow.report_template_versions.get(version_id)
        if version is None:
            return None
        version.status = "published"
        self.uow.session.flush()
        return version


class ReportAutomationService(BaseService):
    def trigger_if_task_complete(self, task_id: int, report_format: str | None = None) -> Report | None:
        task = self.uow.evaluation_tasks.get(task_id)
        if task is None:
            return None

        task_cases = self.uow.task_cases.list(page=1, page_size=100000, task_id=task_id)
        if not task_cases:
            return None

        terminal = {"succeeded", "failed", "cancelled", "skipped"}
        if any(task_case.status not in terminal for task_case in task_cases):
            return None

        existing = self.uow.reports.list(
            page=1,
            page_size=1,
            task_id=task_id,
            report_type="auto",
        )
        if existing:
            return existing[0]

        task_config = task.config or {}
        chosen_format = report_format or task_config.get("auto_report_format") or "pdf"
        report = Report(
            task_id=task_id,
            report_type="auto",
            format=chosen_format,
            status="queued",
            filter_snapshot={},
            report_version="v1",
        )
        return self.uow.reports.add(report)
