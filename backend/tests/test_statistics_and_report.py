import json
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.db.models  # noqa: F401
from app.db.base import Base
from app.db.models import (
    Benchmark,
    BenchmarkVersion,
    EvaluationTask,
    JudgeProfile,
    JudgeResult,
    ManualReview,
    ModelRegistry,
    Report,
    RiskAssessment,
    RiskCategory,
    RiskTaxonomy,
    RuleDefinition,
    RuleSet,
    RuleValidationResult,
    TaskAttempt,
    TaskCase,
    TaskModelBinding,
    TestCase,
)
from app.schemas import ReportCreateRequest, ReportFormat
from app.services.reporting import ReportService
from app.services.statistics import StatisticsService
from app.services.uow import UnitOfWork


def _seed_task(session: Session) -> tuple[int, int]:
    taxonomy = RiskTaxonomy(name="test-taxonomy", version="v1", is_default=True)
    benchmark = Benchmark(name="test-bench", slug="test-bench", source_type="local")
    session.add_all([taxonomy, benchmark])
    session.flush()

    category = RiskCategory(
        taxonomy_id=taxonomy.id,
        code="harmful.violence",
        name="暴力内容",
        severity_weight=80,
    )
    version = BenchmarkVersion(benchmark_id=benchmark.id, version="v1", status="ready")
    session.add_all([category, version])
    session.flush()

    test_case = TestCase(
        benchmark_version_id=version.id,
        external_id="case-001",
        prompt="测试提示词",
        status="active",
    )
    model = ModelRegistry(
        name="mock-model",
        provider="local",
        adapter_type="mock",
        base_url="http://mock.local",
        model_name="mock-model",
        usage_scope="target",
    )
    session.add_all([test_case, model])
    session.flush()

    task = EvaluationTask(
        name="test-task",
        benchmark_version_id=version.id,
        risk_taxonomy_id=taxonomy.id,
        status="succeeded",
        total_cases=1,
        completed_cases=1,
        progress=1.0,
        config={},
    )
    session.add(task)
    session.flush()

    session.add(TaskModelBinding(task_id=task.id, model_id=model.id, role="target"))
    task_case = TaskCase(
        task_id=task.id,
        test_case_id=test_case.id,
        case_key="case-001:0",
        status="succeeded",
    )
    session.add(task_case)
    session.flush()

    attempt = TaskAttempt(
        task_case_id=task_case.id,
        model_id=model.id,
        attempt_no=1,
        status="succeeded",
        output_text="危险输出",
        latency_ms=10,
    )
    session.add(attempt)
    session.flush()

    profile = JudgeProfile(name="test-judge", judge_type="rule", strategy="keyword")
    session.add(profile)
    session.flush()

    judge_result = JudgeResult(
        task_attempt_id=attempt.id,
        judge_profile_id=profile.id,
        run_no=1,
        verdict="unsafe",
        risk_category_id=category.id,
        confidence=0.9,
        trust_score=0.8,
        status="succeeded",
    )
    session.add(judge_result)
    session.flush()

    rule_set = RuleSet(name="test-rules", version="v1")
    session.add(rule_set)
    session.flush()
    rule = RuleDefinition(
        rule_set_id=rule_set.id,
        code="violence",
        rule_type="keyword",
        severity="high",
        definition={"keywords": ["危险"]},
    )
    session.add(rule)
    session.flush()
    session.add(
        RuleValidationResult(
            task_attempt_id=attempt.id,
            rule_definition_id=rule.id,
            passed=False,
            severity="high",
            hit_count=2,
            matched_evidence={"keyword": "危险"},
        )
    )

    assessment = RiskAssessment(
        task_attempt_id=attempt.id,
        overall_score=88.0,
        risk_level="critical",
        confidence=0.8,
        uncertainty=0.2,
        judge_trust_score=0.8,
        score_version="risk-v1",
        rule_override_applied=True,
        calculated_at=datetime.now(timezone.utc),
    )
    session.add(assessment)
    session.flush()

    session.add(
        ManualReview(
            task_attempt_id=attempt.id,
            judge_result_id=judge_result.id,
            risk_assessment_id=assessment.id,
            trigger_reason="judge_low_trust",
            status="pending",
        )
    )
    session.commit()
    return task.id, model.id


def test_statistics_service(tmp_path) -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        task_id, _ = _seed_task(session)
        stats = StatisticsService(UnitOfWork(session)).get_task_statistics(task_id)
        assert stats is not None
        assert stats.total_results == 1
        assert stats.unsafe_count == 1
        assert stats.attack_success_rate == 1.0
        assert stats.average_risk_score == 88.0
        assert stats.judge_average_trust == 0.8
        assert stats.manual_review_rate == 1.0
        assert stats.rule_hit_rate == 1.0
        assert stats.risk_level_distribution["critical"] == 1


def test_report_service_json(tmp_path) -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        task_id, _ = _seed_task(session)
        uow = UnitOfWork(session)
        service = ReportService(uow)
        report = service.create_report(
            ReportCreateRequest(
                task_id=task_id,
                report_type="full",
                format=ReportFormat.json,
                include=["summary", "case_details"],
                filters={},
            )
        )
        session.commit()

        generated = service.generate_report(report.id, base_dir=tmp_path)
        assert generated is not None
        assert generated.status == "ready"
        assert generated.file_id is not None

        stored_file = uow.files.get(generated.file_id)
        assert stored_file is not None
        report_path = tmp_path / str(report.id) / f"report-{report.id}.json"
        assert report_path.exists()
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        assert payload["task"]["task_id"] == task_id
        assert payload["statistics"]["total_results"] == 1
