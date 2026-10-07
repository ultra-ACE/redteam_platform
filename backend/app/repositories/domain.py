from sqlalchemy import select

from app.db.models import (
    AttackMethod,
    AttackTemplate,
    AuditLog,
    Benchmark,
    BenchmarkRiskMapping,
    BenchmarkVersion,
    EvaluationTask,
    IdempotencyKey,
    JudgeProfile,
    JudgeResult,
    ManualReview,
    ModelRegistry,
    Report,
    ReportTemplate,
    ReportTemplateVersion,
    RiskAssessment,
    RiskCategory,
    RiskDimensionScore,
    RiskTaxonomy,
    RuleDefinition,
    RuleSet,
    RuleValidationResult,
    StatisticsSnapshot,
    StoredFile,
    SystemConfig,
    TaskAttempt,
    TaskCase,
    TaskEvent,
    TaskModelBinding,
    TestCase,
    TestCaseRiskLabel,
)
from app.repositories.base import BaseRepository


class BenchmarkRepository(BaseRepository[Benchmark]):
    model = Benchmark


class BenchmarkVersionRepository(BaseRepository[BenchmarkVersion]):
    model = BenchmarkVersion


class TestCaseRepository(BaseRepository[TestCase]):
    model = TestCase


class TestCaseRiskLabelRepository(BaseRepository[TestCaseRiskLabel]):
    model = TestCaseRiskLabel


class RiskTaxonomyRepository(BaseRepository[RiskTaxonomy]):
    model = RiskTaxonomy


class RiskCategoryRepository(BaseRepository[RiskCategory]):
    model = RiskCategory


class BenchmarkRiskMappingRepository(BaseRepository[BenchmarkRiskMapping]):
    model = BenchmarkRiskMapping


class ModelRepository(BaseRepository[ModelRegistry]):
    model = ModelRegistry


class AttackMethodRepository(BaseRepository[AttackMethod]):
    model = AttackMethod


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


class TaskEventRepository(BaseRepository[TaskEvent]):
    model = TaskEvent


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


class RiskAssessmentRepository(BaseRepository[RiskAssessment]):
    model = RiskAssessment


class RiskDimensionScoreRepository(BaseRepository[RiskDimensionScore]):
    model = RiskDimensionScore


class ManualReviewRepository(BaseRepository[ManualReview]):
    model = ManualReview


class StatisticsSnapshotRepository(BaseRepository[StatisticsSnapshot]):
    model = StatisticsSnapshot


class ReportRepository(BaseRepository[Report]):
    model = Report


class ReportTemplateRepository(BaseRepository[ReportTemplate]):
    model = ReportTemplate


class ReportTemplateVersionRepository(BaseRepository[ReportTemplateVersion]):
    model = ReportTemplateVersion


class FileRepository(BaseRepository[StoredFile]):
    model = StoredFile


class SystemConfigRepository(BaseRepository[SystemConfig]):
    model = SystemConfig

    def get_by_key(self, config_key: str) -> SystemConfig | None:
        stmt = select(SystemConfig).where(SystemConfig.config_key == config_key)
        return self.session.scalar(stmt)


class AuditLogRepository(BaseRepository[AuditLog]):
    model = AuditLog


class IdempotencyKeyRepository(BaseRepository[IdempotencyKey]):
    model = IdempotencyKey
