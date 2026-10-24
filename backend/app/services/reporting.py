import hashlib
import html
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from app.core.config import settings
from app.db.models import Report, StoredFile, TaskCase
from app.services.base import BaseService
from app.services.results import EvaluationResultService
from app.services.statistics import StatisticsService


class RawHtml(str):
    """Already escaped HTML produced by this module."""


class ReportService(BaseService):
    MAX_UNSAFE_CASES = 10

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
            unsafe_cases = self._build_unsafe_cases(results)
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
                "context": self._task_context(task),
                "statistics": statistics.model_dump(mode="json") if statistics else {},
                "unsafe_cases": unsafe_cases,
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

    def _task_context(self, task) -> dict[str, Any]:
        config = dict(task.config or {})
        bindings = self.uow.task_model_bindings.list(
            page=1,
            page_size=100,
            task_id=task.id,
        )
        target_models: list[dict[str, Any]] = []
        attacker_model: dict[str, Any] | None = None
        for binding in bindings:
            model = self.uow.models.get(binding.model_id)
            item = {
                "model_id": binding.model_id,
                "name": model.name if model else f"模型 {binding.model_id}",
                "provider": model.provider if model else None,
                "adapter_type": model.adapter_type if model else None,
                "model_name": model.model_name if model else None,
            }
            if binding.role == "attacker":
                attacker_model = item
            elif binding.role == "target":
                target_models.append(item)

        judge_profiles: list[dict[str, Any]] = []
        for profile_id in config.get("judge_profile_ids") or []:
            profile = self.uow.judge_profiles.get(int(profile_id))
            if profile is None:
                continue
            judge_model = (
                self.uow.models.get(profile.judge_model_id)
                if profile.judge_model_id
                else None
            )
            judge_profiles.append(
                {
                    "judge_profile_id": profile.id,
                    "name": profile.name,
                    "judge_type": profile.judge_type,
                    "strategy": profile.strategy,
                    "judge_model_name": judge_model.name if judge_model else None,
                    "judge_model_id": profile.judge_model_id,
                }
            )

        templates: list[dict[str, Any]] = []
        for template_id in config.get("attack_template_ids") or []:
            template = self.uow.attack_templates.get(int(template_id))
            if template is None:
                continue
            templates.append(
                {
                    "attack_template_id": template.id,
                    "library_name": template.library_name,
                    "name": template.name,
                    "version": template.version,
                }
            )

        benchmark = (
            self.uow.benchmarks.get(task.benchmark_id)
            if task.benchmark_id is not None
            else None
        )
        strategy = config.get("attack_strategy") or {}
        strategy_code = str(strategy.get("code") or "static")
        method_labels = {
            "static": "静态模板",
            "base64": "Base64 编码变换",
            "puzzler": "Puzzler 谜题改写",
            "pair": "PAIR 多轮迭代",
        }
        strategy_config = strategy.get("config") or {}
        max_rounds = (
            config.get("max_rounds")
            or strategy_config.get("max_rounds")
            or (config.get("execution") or {}).get("max_rounds")
        )
        return {
            "benchmark_name": benchmark.name if benchmark else None,
            "target_models": target_models,
            "attacker_model": attacker_model,
            "judge_profiles": judge_profiles,
            "templates": templates,
            "attack_method_code": strategy_code,
            "attack_method_label": method_labels.get(
                strategy_code,
                f"静态模板（{strategy_code}）",
            ),
            "sample_size": config.get("sample_size"),
            "max_rounds": max_rounds,
            "rule_set_ids": config.get("rule_set_ids") or [],
        }

    def _build_unsafe_cases(self, results: list[Any]) -> list[dict[str, Any]]:
        cases: list[dict[str, Any]] = []
        result_service = EvaluationResultService(self.uow)
        for representative in StatisticsService.select_case_results(results):
            if representative.judge is None or representative.judge.verdict != "unsafe":
                continue
            detail = result_service.get_attempt_detail(representative.attempt_id)
            model = self.uow.models.get(representative.model_id)
            template = (
                self.uow.attack_templates.get(detail.attack_template_id)
                if detail is not None and detail.attack_template_id
                else None
            )
            judge = detail.judge if detail is not None else None
            cases.append(
                {
                    "attempt_id": representative.attempt_id,
                    "external_id": representative.external_id,
                    "model_name": model.name if model else f"模型 {representative.model_id}",
                    "template_name": template.name if template else None,
                    "template_library": template.library_name if template else None,
                    "round_no": representative.round_no,
                    "attack_method": representative.attack_strategy,
                    "prompt": (
                        detail.rendered_prompt
                        if detail is not None and detail.rendered_prompt
                        else representative.prompt_excerpt
                    ),
                    "model_output": (
                        detail.model_output
                        if detail is not None and detail.model_output
                        else representative.model_output_excerpt
                    ),
                    "judge_profile_name": (
                        judge.judge_profile_name if judge is not None else None
                    ),
                    "judge_confidence": (
                        judge.confidence
                        if judge is not None
                        else representative.judge.confidence
                    ),
                    "judge_reasoning": (
                        judge.reasoning if judge is not None else None
                    ),
                }
            )
        return cases[: self.MAX_UNSAFE_CASES]

    @staticmethod
    def _percent(value: Any) -> str:
        try:
            return f"{float(value) * 100:.1f}%"
        except (TypeError, ValueError):
            return "0.0%"

    @staticmethod
    def _text_block(value: Any) -> RawHtml:
        return RawHtml(f"<pre>{html.escape(str(value or ''))}</pre>")

    def _build_html(self, data: dict[str, Any]) -> str:
        task = data["task"]
        context = data["context"]
        stats = data["statistics"]
        unsafe_cases = data["unsafe_cases"]
        target_rows = [
            [
                item["name"],
                item["model_id"],
                item["provider"] or "-",
                item["adapter_type"] or "-",
                item["model_name"] or "-",
            ]
            for item in context["target_models"]
        ]
        judge_rows = [
            [
                item["name"],
                item["judge_profile_id"],
                "模型 Judge" if item["judge_type"] == "model" else "规则 Judge",
                item["judge_model_name"] or "-",
                item["strategy"],
            ]
            for item in context["judge_profiles"]
        ]
        template_rows = [
            [
                item["library_name"],
                item["name"],
                item["version"],
            ]
            for item in context["templates"]
        ]
        overall_asr = float(stats.get("attack_success_rate") or 0)
        model_rows = []
        for index, item in enumerate(
            sorted(
                stats.get("model_breakdown") or [],
                key=lambda row: (
                    -float(row.get("attack_success_rate") or 0),
                    str(row.get("model_name") or ""),
                ),
            ),
            start=1,
        ):
            asr = float(item.get("attack_success_rate") or 0)
            delta = (asr - overall_asr) * 100
            delta_text = (
                f"{delta:+.1f} 个百分点"
                if abs(delta) >= 0.05
                else "0.0 个百分点"
            )
            model_rows.append(
                [
                    index,
                    item.get("model_name") or f"模型 {item.get('model_id', '-')}",
                    item.get("count", 0),
                    item.get("unsafe_count", 0),
                    self._percent(asr),
                    delta_text,
                ]
            )
        unsafe_sections = []
        for case in unsafe_cases:
            unsafe_sections.append(
                f"""
                <article class="case">
                  <h3>{html.escape(str(case["external_id"] or "-"))} · {html.escape(case["model_name"])}</h3>
                  {self._html_table(
                      ["字段", "内容"],
                      [
                          ["攻击方式", context["attack_method_label"]],
                          ["模板", f'{case["template_library"] or "-"} / {case["template_name"] or "-"}'],
                          ["迭代轮次", case["round_no"] if case["round_no"] is not None else "-"],
                          ["Judge", case["judge_profile_name"] or "-"],
                          ["Judge 可信度", self._percent(case["judge_confidence"])],
                      ],
                  )}
                  <h4>实际发送给模型的 Prompt</h4>
                  {self._text_block(case["prompt"])}
                  <h4>模型输出</h4>
                  {self._text_block(case["model_output"])}
                  <h4>Judge 理由</h4>
                  {self._text_block(case["judge_reasoning"] or "无")}
                </article>
                """
            )
        unsafe_content = (
            "\n".join(unsafe_sections)
            if unsafe_sections
            else "<p>本次任务未发现被 Judge 判定为有害的用例。</p>"
        )
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
    pre {{ white-space: pre-wrap; overflow-wrap: anywhere; margin: 8px 0 18px; padding: 12px; background: #f7f9fc; border-radius: 6px; }}
    .case {{ border: 1px solid #dce3ee; border-radius: 8px; padding: 18px; margin: 16px 0; }}
    .case h3 {{ margin-top: 0; }}
  </style>
</head>
<body>
<main>
  <h1>大模型越狱攻击安全评测报告</h1>
  <section>
    <h2>任务设置</h2>
    {self._html_table(["字段", "内容"], [
        ["任务 ID", task["task_id"]],
        ["任务名称", task["name"]],
        ["任务状态", task["status"]],
        ["种子库", context["benchmark_name"] or "-"],
        ["攻击方式", f'{context["attack_method_label"]}（{context["attack_method_code"]}）'],
        ["采样条数", context["sample_size"] if context["sample_size"] is not None else "-"],
        ["最大迭代轮数", context["max_rounds"] if context["max_rounds"] is not None else "-"],
        ["规则集 ID", ", ".join(str(item) for item in context["rule_set_ids"]) or "-"],
    ])}
    <h3>使用的模板</h3>
    {self._html_table(["模板库", "模板名称", "版本"], template_rows) if template_rows else "<p>未选择模板</p>"}
  </section>
  <section>
    <h2>被测模型</h2>
    {self._html_table(["模型", "ID", "Provider", "适配器", "模型名"], target_rows) if target_rows else "<p>未配置被测模型</p>"}
    <h3>攻击模型（PAIR）</h3>
    {self._html_table(["模型", "ID", "Provider", "适配器", "模型名"], [[context["attacker_model"]["name"], context["attacker_model"]["model_id"], context["attacker_model"]["provider"] or "-", context["attacker_model"]["adapter_type"] or "-", context["attacker_model"]["model_name"] or "-"]]) if context["attacker_model"] else "<p>本次未使用攻击模型</p>"}
  </section>
  <section>
    <h2>Judge 配置</h2>
    {self._html_table(["Judge 名称", "ID", "类型", "Judge 模型", "策略"], judge_rows) if judge_rows else "<p>使用系统默认规则 Judge</p>"}
  </section>
  <section>
    <h2>总体指标</h2>
    {self._html_table(["指标", "数值"], [
        ["已完成用例", stats.get("total_results", 0)],
        ["安全用例", stats.get("safe_count", 0)],
        ["有害用例", stats.get("unsafe_count", 0)],
        ["不确定用例", stats.get("uncertain_count", 0)],
        ["攻击成功率", self._percent(stats.get("attack_success_rate", 0))],
        ["Judge 平均可信度", self._percent(stats.get("judge_average_trust", 0))],
        ["规则命中率", self._percent(stats.get("rule_hit_rate", 0))],
    ])}
  </section>
  <section>
    <h2>模型 ASR 横向对比</h2>
    <p>ASR = 有害用例数 / 已完成评测用例数；PAIR 多轮用例只按最终结论计一次。</p>
    {self._html_table(
        ["排名", "被测模型", "已完成用例", "有害用例", "ASR", "较总体 ASR"],
        model_rows,
    ) if model_rows else "<p>暂无模型对比数据。</p>"}
  </section>
  <section>
    <h2>有害用例模型输出（最多展示 10 条）</h2>
    <p>以下仅列出最终判定为 unsafe 的用例，安全用例和不相关明细不展开。</p>
    {unsafe_content}
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

        # 性能修复（T8）：这里原来每次都会 list 全量 task_cases 再逐条判断，
        # 而它会在每条结果完成规则校验后被调用一次，结果数一多就是 O(n²) 扫描。
        # 现在只依赖主任务计数 + 一条 COUNT 查询。
        total = task.total_cases or self.uow.task_cases.count(task_id=task_id)
        if total <= 0:
            return None, False
        terminal = ["succeeded", "failed", "cancelled", "skipped"]
        terminal_count = int(
            self.uow.session.scalar(
                select(func.count())
                .select_from(TaskCase)
                .where(TaskCase.task_id == task_id, TaskCase.status.in_(terminal))
            )
            or 0
        )
        if terminal_count < total:
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
