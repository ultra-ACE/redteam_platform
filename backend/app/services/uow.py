from sqlalchemy.orm import Session

from app.repositories import (
    AttackTemplateRepository,
    BenchmarkRepository,
    BenchmarkVersionRepository,
    EvaluationTaskRepository,
    FileRepository,
    JudgeProfileRepository,
    JudgeResultRepository,
    ManualReviewRepository,
    ModelRepository,
    ReportRepository,
    RuleDefinitionRepository,
    RuleSetRepository,
    RuleValidationResultRepository,
    TaskAttemptRepository,
    TaskCaseRepository,
    TaskModelBindingRepository,
    TestCaseRepository,
)


class UnitOfWork:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.benchmarks = BenchmarkRepository(session)
        self.benchmark_versions = BenchmarkVersionRepository(session)
        self.test_cases = TestCaseRepository(session)
        self.models = ModelRepository(session)
        self.attack_templates = AttackTemplateRepository(session)
        self.evaluation_tasks = EvaluationTaskRepository(session)
        self.task_model_bindings = TaskModelBindingRepository(session)
        self.task_cases = TaskCaseRepository(session)
        self.task_attempts = TaskAttemptRepository(session)
        self.judge_profiles = JudgeProfileRepository(session)
        self.judge_results = JudgeResultRepository(session)
        self.rule_sets = RuleSetRepository(session)
        self.rule_definitions = RuleDefinitionRepository(session)
        self.rule_validation_results = RuleValidationResultRepository(session)
        self.manual_reviews = ManualReviewRepository(session)
        self.reports = ReportRepository(session)
        self.files = FileRepository(session)

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
