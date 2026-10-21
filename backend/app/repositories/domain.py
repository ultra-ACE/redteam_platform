from sqlalchemy import select, update

from app.db.models import (
    AttackTemplate,
    Benchmark,
    EvaluationTask,
    JudgeProfile,
    JudgeResult,
    ManualReview,
    ModelRegistry,
    Report,
    RuleDefinition,
    RuleSet,
    RuleValidationResult,
    StoredFile,
    TaskAttempt,
    TaskCase,
    TaskModelBinding,
    TestCase,
)
from app.repositories.base import BaseRepository


class BenchmarkRepository(BaseRepository[Benchmark]):
    model = Benchmark


class TestCaseRepository(BaseRepository[TestCase]):
    model = TestCase


class ModelRepository(BaseRepository[ModelRegistry]):
    model = ModelRegistry


class AttackTemplateRepository(BaseRepository[AttackTemplate]):
    model = AttackTemplate


class EvaluationTaskRepository(BaseRepository[EvaluationTask]):
    model = EvaluationTask

    def get_by_status(self, status: str) -> list[EvaluationTask]:
        stmt = select(EvaluationTask).where(EvaluationTask.status == status)
        return list(self.session.scalars(stmt).all())


class TaskModelBindingRepository(BaseRepository[TaskModelBinding]):
    model = TaskModelBinding


class TaskCaseRepository(BaseRepository[TaskCase]):
    model = TaskCase


class TaskAttemptRepository(BaseRepository[TaskAttempt]):
    model = TaskAttempt


class JudgeProfileRepository(BaseRepository[JudgeProfile]):
    model = JudgeProfile


class JudgeResultRepository(BaseRepository[JudgeResult]):
    model = JudgeResult


class RuleSetRepository(BaseRepository[RuleSet]):
    model = RuleSet


class RuleDefinitionRepository(BaseRepository[RuleDefinition]):
    model = RuleDefinition


class RuleValidationResultRepository(BaseRepository[RuleValidationResult]):
    model = RuleValidationResult


class ManualReviewRepository(BaseRepository[ManualReview]):
    model = ManualReview


class ReportRepository(BaseRepository[Report]):
    model = Report

    def claim_for_generation(self, report_id: int) -> bool:
        result = self.session.execute(
            update(Report)
            .where(Report.id == report_id, Report.status == "queued")
            .values(status="generating")
        )
        return (result.rowcount or 0) == 1


class FileRepository(BaseRepository[StoredFile]):
    model = StoredFile
