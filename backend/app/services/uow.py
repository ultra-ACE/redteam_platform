from sqlalchemy.orm import Session

from app.repositories import (
    AttackMethodRepository,
    AttackTemplateRepository,
    AuditLogRepository,
    BenchmarkRepository,
    BenchmarkRiskMappingRepository,
    BenchmarkVersionRepository,
    EvaluationTaskRepository,
    FileRepository,
    IdempotencyKeyRepository,
    JudgeProfileRepository,
    JudgeResultRepository,
    ManualReviewRepository,
    ModelRepository,
    ReportRepository,
    ReportTemplateRepository,
    ReportTemplateVersionRepository,
    RiskAssessmentRepository,
    RiskCategoryRepository,
    RiskDimensionScoreRepository,
    RiskLabelAliasRepository,
    RiskTaxonomyRepository,
    RuleDefinitionRepository,
    RuleSetRepository,
    RuleValidationResultRepository,
    StatisticsSnapshotRepository,
    SystemConfigRepository,
    TaskAttemptRepository,
    TaskCaseRepository,
    TaskEventRepository,
    TaskModelBindingRepository,
    TestCaseRepository,
    TestCaseRiskLabelRepository,
)


class UnitOfWork:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.benchmarks = BenchmarkRepository(session)
        self.benchmark_versions = BenchmarkVersionRepository(session)
        self.test_cases = TestCaseRepository(session)
        self.test_case_risk_labels = TestCaseRiskLabelRepository(session)
        self.risk_taxonomies = RiskTaxonomyRepository(session)
        self.risk_categories = RiskCategoryRepository(session)
        self.benchmark_risk_mappings = BenchmarkRiskMappingRepository(session)
        self.risk_label_aliases = RiskLabelAliasRepository(session)
        self.models = ModelRepository(session)
        self.attack_methods = AttackMethodRepository(session)
        self.attack_templates = AttackTemplateRepository(session)
        self.evaluation_tasks = EvaluationTaskRepository(session)
        self.task_model_bindings = TaskModelBindingRepository(session)
        self.task_cases = TaskCaseRepository(session)
        self.task_attempts = TaskAttemptRepository(session)
        self.task_events = TaskEventRepository(session)
        self.judge_profiles = JudgeProfileRepository(session)
        self.judge_results = JudgeResultRepository(session)
        self.rule_sets = RuleSetRepository(session)
        self.rule_definitions = RuleDefinitionRepository(session)
        self.rule_validation_results = RuleValidationResultRepository(session)
        self.risk_assessments = RiskAssessmentRepository(session)
        self.risk_dimension_scores = RiskDimensionScoreRepository(session)
        self.manual_reviews = ManualReviewRepository(session)
        self.statistics_snapshots = StatisticsSnapshotRepository(session)
        self.reports = ReportRepository(session)
        self.report_templates = ReportTemplateRepository(session)
        self.report_template_versions = ReportTemplateVersionRepository(session)
        self.files = FileRepository(session)
        self.system_configs = SystemConfigRepository(session)
        self.audit_logs = AuditLogRepository(session)
        self.idempotency_keys = IdempotencyKeyRepository(session)

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()

    def close(self) -> None:
        self.session.close()

    def __enter__(self) -> "UnitOfWork":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        self.close()
