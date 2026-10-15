# 三人分工与文件边界

## 一、成员 1：集成负责人

负责：数据库迁移、共享接口、删除风险分类和风险评分、最终合并与验收。

允许修改：

- `backend/app/db/models/**`
- `backend/alembic/versions/**`
- `backend/app/schemas/**`
- `backend/app/repositories/**`
- `backend/app/services/uow.py`
- `backend/app/services
- /__init__.py`
- `backend/app/services/domain.py`
- `backend/app/api/v1/router.py`
- `backend/app/main.py`
- `frontend/src/api/index.ts`
- `frontend/src/types/api.ts`
- `frontend/src/router.tsx`
- `frontend/src/layouts/AppLayout.tsx`
- `openapi.yaml`

同时负责删除：

- `backend/app/services/risk_scoring.py`
- `backend/app/services/risk_mapping.py`
- `backend/app/services/risk_aliases.py`
- `backend/app/api/v1/routes/risk.py`
- `frontend/src/pages/RiskTaxonomyPage.tsx`

## 二、成员 2：清理、报告、模型与攻击

负责：删除系统/审计/工作台/报告模板、HTML 报告、模型编辑、攻击方式写死。

允许修改：

- `frontend/src/pages/SystemPage.tsx`
- `frontend/src/pages/AuditPage.tsx`
- `frontend/src/pages/DashboardPage.tsx`
- `frontend/src/pages/ReportTemplatesPage.tsx`
- `frontend/src/pages/ReportsPage.tsx`
- `frontend/src/pages/ModelsPage.tsx`
- `frontend/src/pages/AttackTemplatesPage.tsx`
- `backend/app/api/v1/routes/system.py`
- `backend/app/api/v1/routes/report.py`
- `backend/app/api/v1/routes/report_templates.py`
- `backend/app/api/v1/routes/model.py`
- `backend/app/api/v1/routes/attack.py`
- `backend/app/services/reporting.py`
- `backend/app/services/attack_templates.py`
- `backend/app/adapters/**`
- `backend/tests/test_report_links.py`
- `backend/tests/test_report_templates.py`
- `backend/tests/test_attack_templates.py`
- `backend/tests/test_model_crud.py`

## 三、成员 3：数据集与任务

负责：中文数据集、良性/有害/越狱类型、任务暂停/继续/断点续跑。

允许修改：

- `backend/app/services/dataset_adapters/**`
- `backend/app/services/benchmark_import.py`
- `backend/app/api/v1/routes/benchmark.py`
- `frontend/src/pages/BenchmarksPage.tsx`
- `benchmark_datasets/zh_*`
- `backend/app/services/execution.py`
- `backend/app/workers/tasks.py`
- `backend/app/workers/queue.py`
- `backend/app/workers/celery_app.py`
- `backend/app/workers/recovery.py`
- `backend/app/api/v1/routes/tasks.py`
- `frontend/src/pages/TasksPage.tsx`
- `frontend/src/pages/TaskDetailPage.tsx`
- `backend/tests/test_dataset_adapters.py`
- `backend/tests/test_benchmark_import.py`
- `backend/tests/test_task_execution.py`
- `backend/tests/test_task_events.py`

## 四、后续注意事项

- 成员 1 先冻结数据库字段和共享接口，成员 2、3 再开始开发。
- 每个人只修改自己列出的文件；需要共享字段或公共 API 时，交给成员 1 修改。
- 不允许成员 2、3 修改 `openapi.yaml`，由成员 1 统一重新导出。
- 风险分类、风险映射、风险总分和默认权重全部删除。
- 报告只使用 Judge 判定、Judge 可信度、规则命中、攻击成功率和数据集类型统计。
- 原始数据集标签只作为元数据保存，不再映射风险类别。
- 删除系统业务功能时，必须保留 `/api/v1/health`。
- 任务执行链删除 `quantify_risk`，规则校验完成后直接进入统计和报告。
- 合并顺序：成员 1 契约冻结 -> 成员 2 -> 成员 3 -> 成员 1 统一测试。
