import { apiClient } from './client';
import type {
  ApiEnvelope,
  AttackMethod,
  AttackTemplate,
  AttackTemplatePreviewResult,
  AttackTemplateValidationResult,
  AttemptDetail,
  AuditLog,
  Benchmark,
  BenchmarkImportResult,
  BenchmarkVersion,
  EvaluationResult,
  EvaluationTask,
  HealthData,
  JudgeProfile,
  JudgeReEvaluateResult,
  JudgeTrustSummary,
  ManualReview,
  ManualReviewDetail,
  ModelRecord,
  PaginatedData,
  Report,
  ReportTemplate,
  ReportTemplateVersion,
  RetryFailedData,
  RiskCategory,
  RiskMappingStatus,
  RiskTaxonomy,
  Statistics,
  StoredFile,
  SystemConfig,
  TaskStatusData,
  TestCase,
} from '../types/api';

export const getHealth = async () => {
  const { data } = await apiClient.get<ApiEnvelope<HealthData>>('/health');
  return data.data;
};

export const listModels = async (params?: Record<string, unknown>) => {
  const { data } = await apiClient.get<ApiEnvelope<PaginatedData<ModelRecord>>>('/models', { params });
  return data.data;
};

export const createModel = async (payload: Record<string, unknown>) => {
  const { data } = await apiClient.post<ApiEnvelope<ModelRecord>>('/models', payload);
  return data.data;
};

export type ModelHealthResult = {
  model_id: number;
  status: string;
  latency_ms?: number;
  error_message?: string | null;
};

export const checkModelHealth = async (modelId: number) => {
  const { data } = await apiClient.post<ApiEnvelope<ModelHealthResult>>(
    `/models/${modelId}/health-check`,
    undefined,
    { timeout: 30000 },
  );
  return data.data;
};


export const importBenchmark = async (payload: FormData) => {
  const { data } = await apiClient.post<ApiEnvelope<BenchmarkImportResult>>('/benchmarks/import', payload, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data.data;
};

export type DeleteSummary = {
  deleted_versions: number;
  deleted_test_cases: number;
  deleted_labels: number;
  deleted_mappings: number;
};

export const deleteBenchmark = async (benchmarkId: number) => {
  const { data } = await apiClient.delete<ApiEnvelope<DeleteSummary>>(`/benchmarks/${benchmarkId}`);
  return data.data;
};

export const deleteBenchmarkVersion = async (versionId: number) => {
  const { data } = await apiClient.delete<ApiEnvelope<DeleteSummary>>(`/benchmark-versions/${versionId}`);
  return data.data;
};

export const listBenchmarks = async (params?: Record<string, unknown>) => {
  const { data } = await apiClient.get<ApiEnvelope<PaginatedData<Benchmark>>>('/benchmarks', { params });
  return data.data;
};

export const listBenchmarkVersions = async (benchmarkId: number) => {
  const { data } = await apiClient.get<ApiEnvelope<PaginatedData<BenchmarkVersion>>>(
    `/benchmarks/${benchmarkId}/versions`,
  );
  return data.data;
};

export const listTestCases = async (params?: Record<string, unknown>) => {
  const { data } = await apiClient.get<ApiEnvelope<PaginatedData<TestCase>>>('/test-cases', { params });
  return data.data;
};

export const listTasks = async (params?: Record<string, unknown>) => {
  const { data } = await apiClient.get<ApiEnvelope<PaginatedData<EvaluationTask>>>('/evaluation-tasks', { params });
  return data.data;
};

export const createTask = async (payload: Record<string, unknown>) => {
  const { data } = await apiClient.post<ApiEnvelope<EvaluationTask>>('/evaluation-tasks', payload);
  return data.data;
};

export const getTaskStatus = async (taskId: number) => {
  const { data } = await apiClient.get<ApiEnvelope<TaskStatusData>>(`/evaluation-tasks/${taskId}/status`);
  return data.data;
};

export const getTaskEventsUrl = (taskId: number) => {
  const base = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';
  return `${base}/evaluation-tasks/${taskId}/events`;
};

export const getTaskResults = async (taskId: number, params?: Record<string, unknown>) => {
  const { data } = await apiClient.get<ApiEnvelope<PaginatedData<EvaluationResult>>>(
    `/evaluation-tasks/${taskId}/results`,
    { params },
  );
  return data.data;
};

export const getTaskStatistics = async (taskId: number) => {
  const { data } = await apiClient.get<ApiEnvelope<Statistics>>(`/evaluation-tasks/${taskId}/statistics`);
  return data.data;
};

export const getTaskAttemptDetail = async (attemptId: number) => {
  const { data } = await apiClient.get<ApiEnvelope<AttemptDetail>>(`/task-attempts/${attemptId}`);
  return data.data;
};

export const startTask = async (taskId: number) => {
  const { data } = await apiClient.post<ApiEnvelope<{ task_id: number; status: string }>>(
    `/evaluation-tasks/${taskId}/actions/start`,
  );
  return data.data;
};

export const cancelTask = async (taskId: number) => {
  const { data } = await apiClient.post<ApiEnvelope<{ task_id: number; status: string }>>(
    `/evaluation-tasks/${taskId}/actions/cancel`,
  );
  return data.data;
};

export const retryFailedTask = async (taskId: number) => {
  const { data } = await apiClient.post<ApiEnvelope<RetryFailedData>>(
    `/evaluation-tasks/${taskId}/actions/retry-failed`,
  );
  return data.data;
};

export const listReportTemplates = async (params?: Record<string, unknown>) => {
  const { data } = await apiClient.get<ApiEnvelope<PaginatedData<ReportTemplate>>>('/report-templates', { params });
  return data.data;
};

export const createReportTemplate = async (payload: Record<string, unknown>) => {
  const { data } = await apiClient.post<ApiEnvelope<ReportTemplate>>('/report-templates', payload);
  return data.data;
};

export const listReportTemplateVersions = async (templateId: number) => {
  const { data } = await apiClient.get<ApiEnvelope<PaginatedData<ReportTemplateVersion>>>(
    `/report-templates/${templateId}/versions`,
  );
  return data.data;
};

export const createReportTemplateVersion = async (templateId: number, payload: Record<string, unknown>) => {
  const { data } = await apiClient.post<ApiEnvelope<ReportTemplateVersion>>(
    `/report-templates/${templateId}/versions`,
    payload,
  );
  return data.data;
};

export const publishReportTemplateVersion = async (versionId: number) => {
  const { data } = await apiClient.post<ApiEnvelope<ReportTemplateVersion>>(
    `/report-template-versions/${versionId}/publish`,
  );
  return data.data;
};

export const createReport = async (payload: Record<string, unknown>) => {
  const { data } = await apiClient.post<ApiEnvelope<Report>>('/reports', payload);
  return data.data;
};

export const getReport = async (reportId: number) => {
  const { data } = await apiClient.get<ApiEnvelope<Report>>(`/reports/${reportId}`);
  return data.data;
};

export const downloadReport = async (reportId: number) => {
  const response = await apiClient.get(`/reports/${reportId}/download`, { responseType: 'blob' });
  return response;
};

export const listSystemConfigs = async (params?: Record<string, unknown>) => {
  const { data } = await apiClient.get<ApiEnvelope<PaginatedData<SystemConfig>>>('/system-configs', { params });
  return data.data;
};

export const updateSystemConfig = async (configKey: string, value: unknown) => {
  const { data } = await apiClient.patch<ApiEnvelope<SystemConfig>>(`/system-configs/${configKey}`, {
    config_value: value,
  });
  return data.data;
};

export const listAuditLogs = async (params?: Record<string, unknown>) => {
  const { data } = await apiClient.get<ApiEnvelope<PaginatedData<AuditLog>>>('/audit-logs', { params });
  return data.data;
};

export const listAttackMethods = async (params?: Record<string, unknown>) => {
  const { data } = await apiClient.get<ApiEnvelope<PaginatedData<AttackMethod>>>('/attack-methods', { params });
  return data.data;
};

export const createAttackTemplate = async (payload: Record<string, unknown>) => {
  const { data } = await apiClient.post<ApiEnvelope<AttackTemplate>>('/attack-templates', payload);
  return data.data;
};


export const createAttackMethod = async (payload: Record<string, unknown>) => {
  const { data } = await apiClient.post<ApiEnvelope<AttackMethod>>('/attack-methods', payload);
  return data.data;
};

export const updateAttackMethod = async (methodId: number, payload: Record<string, unknown>) => {
  const { data } = await apiClient.patch<ApiEnvelope<AttackMethod>>(`/attack-methods/${methodId}`, payload);
  return data.data;
};

export const disableAttackMethod = async (methodId: number) => {
  const { data } = await apiClient.delete<ApiEnvelope<AttackMethod>>(`/attack-methods/${methodId}`);
  return data.data;
};

export const listAttackTemplates = async (params?: Record<string, unknown>) => {
  const { data } = await apiClient.get<ApiEnvelope<PaginatedData<AttackTemplate>>>('/attack-templates', { params });
  return data.data;
};

export const updateAttackTemplate = async (templateId: number, payload: Record<string, unknown>) => {
  const { data } = await apiClient.patch<ApiEnvelope<AttackTemplate>>(`/attack-templates/${templateId}`, payload);
  return data.data;
};

export const disableAttackTemplate = async (templateId: number) => {
  const { data } = await apiClient.delete<ApiEnvelope<AttackTemplate>>(`/attack-templates/${templateId}`);
  return data.data;
};

export const validateAttackTemplate = async (templateId: number) => {
  const { data } = await apiClient.post<ApiEnvelope<AttackTemplateValidationResult>>(
    `/attack-templates/${templateId}/validate`,
  );
  return data.data;
};


export const previewAttackTemplate = async (templateId: number, variables: Record<string, unknown>) => {
  const { data } = await apiClient.post<ApiEnvelope<AttackTemplatePreviewResult>>(
    `/attack-templates/${templateId}/preview`,
    { variables },
  );
  return data.data;
};

export const listAttackTemplateVersions = async (templateId: number) => {
  const { data } = await apiClient.get<ApiEnvelope<AttackTemplate[]>>(`/attack-templates/${templateId}/versions`);
  return data.data;
};

export const createAttackTemplateVersion = async (templateId: number, payload: Record<string, unknown>) => {
  const { data } = await apiClient.post<ApiEnvelope<AttackTemplate>>(
    `/attack-templates/${templateId}/versions`,
    payload,
  );
  return data.data;
};

export const publishAttackTemplateVersion = async (templateId: number) => {
  const { data } = await apiClient.post<ApiEnvelope<AttackTemplate>>(`/attack-templates/${templateId}/publish`);
  return data.data;
};

export const listJudgeProfiles = async (params?: Record<string, unknown>) => {
  const { data } = await apiClient.get<ApiEnvelope<PaginatedData<JudgeProfile>>>('/judge-profiles', { params });
  return data.data;
};

export type RuleJudgeDefaults = {
  harmful_keywords: string[];
  refusal_keywords: string[];
  harmful_patterns: string[];
  unsafe_confidence: number;
  safe_confidence: number;
  uncertain_confidence: number;
};

export const getRuleJudgeDefaults = async () => {
  const { data } = await apiClient.get<ApiEnvelope<RuleJudgeDefaults>>('/judge-profiles/rule-defaults');
  return data.data;
};

export const createJudgeProfile = async (payload: Record<string, unknown>) => {
  const { data } = await apiClient.post<ApiEnvelope<JudgeProfile>>('/judge-profiles', payload);
  return data.data;
};


export const getJudgeProfile = async (profileId: number) => {
  const { data } = await apiClient.get<ApiEnvelope<JudgeProfile>>(`/judge-profiles/${profileId}`);
  return data.data;
};

export const updateJudgeProfile = async (profileId: number, payload: Record<string, unknown>) => {
  const { data } = await apiClient.patch<ApiEnvelope<JudgeProfile>>(`/judge-profiles/${profileId}`, payload);
  return data.data;
};

export const disableJudgeProfile = async (profileId: number) => {
  const { data } = await apiClient.delete<ApiEnvelope<JudgeProfile>>(`/judge-profiles/${profileId}`);
  return data.data;
};

export const getJudgeTrust = async (taskId: number) => {
  const { data } = await apiClient.get<ApiEnvelope<JudgeTrustSummary>>(`/evaluation-tasks/${taskId}/judge-trust`);
  return data.data;
};

export const reEvaluateJudgeResult = async (judgeResultId: number) => {
  const { data } = await apiClient.post<ApiEnvelope<JudgeReEvaluateResult>>(
    `/judge-results/${judgeResultId}/re-evaluate`,
  );
  return data.data;
};

export const listManualReviews = async (params?: Record<string, unknown>) => {
  const { data } = await apiClient.get<ApiEnvelope<PaginatedData<ManualReview>>>('/manual-reviews', { params });
  return data.data;
};


export const getManualReview = async (reviewId: number) => {
  const { data } = await apiClient.get<ApiEnvelope<ManualReviewDetail>>(`/manual-reviews/${reviewId}`);
  return data.data;
};

export const createManualReview = async (payload: Record<string, unknown>) => {
  const { data } = await apiClient.post<ApiEnvelope<ManualReviewDetail>>('/manual-reviews', payload);
  return data.data;
};

export const updateManualReview = async (reviewId: number, payload: Record<string, unknown>) => {
  const { data } = await apiClient.patch<ApiEnvelope<ManualReviewDetail>>(`/manual-reviews/${reviewId}`, payload);
  return data.data;
};

export const listRiskTaxonomies = async (params?: Record<string, unknown>) => {
  const { data } = await apiClient.get<ApiEnvelope<PaginatedData<RiskTaxonomy>>>('/risk-taxonomies', { params });
  return data.data;
};


export const listRiskCategories = async (taxonomyId: number) => {
  const { data } = await apiClient.get<ApiEnvelope<RiskCategory[]>>(`/risk-taxonomies/${taxonomyId}/categories`);
  return data.data;
};

export const createRiskCategory = async (taxonomyId: number, payload: Record<string, unknown>) => {
  const { data } = await apiClient.post<ApiEnvelope<RiskCategory>>(`/risk-taxonomies/${taxonomyId}/categories`, payload);
  return data.data;
};

export const getRiskMappingStatus = async (benchmarkVersionId: number) => {
  const { data } = await apiClient.get<ApiEnvelope<RiskMappingStatus>>(
    `/benchmark-versions/${benchmarkVersionId}/mapping-status`,
  );
  return data.data;
};

export const batchUpsertRiskMappings = async (benchmarkVersionId: number, mappings: Array<Record<string, unknown>>) => {
  const { data } = await apiClient.post<ApiEnvelope<{ created_count: number; updated_count: number; remaining_unresolved_count: number }>>(
    `/benchmark-versions/${benchmarkVersionId}/risk-mappings/batch`,
    { mappings },
  );
  return data.data;
};

export const createRiskTaxonomy = async (payload: Record<string, unknown>) => {
  const { data } = await apiClient.post<ApiEnvelope<RiskTaxonomy>>('/risk-taxonomies', payload);
  return data.data;
};


export const listFiles = async (params?: Record<string, unknown>) => {
  const { data } = await apiClient.get<ApiEnvelope<PaginatedData<StoredFile>>>('/files', { params });
  return data.data;
};

export const uploadFile = async (payload: FormData) => {
  const { data } = await apiClient.post<ApiEnvelope<StoredFile>>('/files', payload, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data.data;
};

export const getFile = async (fileId: number) => {
  const { data } = await apiClient.get<ApiEnvelope<StoredFile>>(`/files/${fileId}`);
  return data.data;
};

export const downloadFile = async (fileId: number) => {
  const response = await apiClient.get(`/files/${fileId}/download`, { responseType: 'blob' });
  return response;
};
