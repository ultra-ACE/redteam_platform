# 成员 2 / 成员 3 操作指南

## 共同规则

- 组长先提交并推送 `codex/contract-freeze`。
- 成员从该分支创建自己的分支，不要继续使用旧版风险逻辑。
- 下列共享文件只能由组长修改：

```text
backend/app/db/models/**
backend/app/schemas/**
backend/app/repositories/**
backend/app/services/uow.py
backend/app/services/domain.py
backend/app/api/v1/router.py
frontend/src/api/index.ts
frontend/src/types/api.ts
frontend/src/router.tsx
frontend/src/layouts/AppLayout.tsx
openapi.yaml
```

- 共享接口不够用时，先让组长修改，不要直接绕过契约。
- 不允许恢复风险分类、风险分、报告模板、系统配置和审计日志。

## 一、成员 2：模型、攻击方式、HTML 报告

创建分支：

```powershell
git switch codex/contract-freeze
git switch -c feature/member2-model-attack-report
```

允许修改：

```text
frontend/src/pages/ModelsPage.tsx
frontend/src/pages/AttackTemplatesPage.tsx
frontend/src/pages/ReportsPage.tsx
backend/app/api/v1/routes/model.py
backend/app/api/v1/routes/attack.py
backend/app/api/v1/routes/report.py
backend/app/services/attack_templates.py
backend/app/services/reporting.py
backend/app/adapters/**
backend/tests/test_model_crud.py
backend/tests/test_attack_templates_contract.py
backend/tests/test_html_report.py
```

### 任务 1：模型编辑

- `ModelsPage.tsx` 增加编辑按钮和编辑弹窗。
- 编辑时调用已冻结的 `updateModel(modelId, values)`。
- 提交后刷新模型列表。
- 后端已有 `PATCH /api/v1/models/{model_id}`，不要新增第二套接口。

### 任务 2：攻击方式写死

- 攻击方式固定为：

```text
direct_request
role_play
prefix_injection
refusal_suppression
```

- 前端去掉攻击方法的增、删、改、停用。
- 攻击模板表单只使用 `method_code`，不再使用 `attack_method_id`。
- 不新增 `attack_methods` 表。

### 任务 3：HTML 报告

- 报告只生成 HTML，不提供 PDF、JSON、Markdown、CSV。
- 创建报告固定发送 `format: 'html'`。
- HTML 必须包含：

```text
任务信息
Judge 判定分布
数据集类型分布
攻击成功率
规则命中率
Judge 平均可信度
逐条结果与详情链接
```

- HTML 必须自包含，不依赖 CDN。

提交前执行：

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q

cd ..\frontend
npm run typecheck
npm run build
```

## 二、成员 3：数据集、任务暂停与续跑

创建分支：

```powershell
git switch codex/contract-freeze
git switch -c feature/member3-dataset-task-resume
```

允许修改：

```text
backend/app/services/dataset_adapters/**
backend/app/services/benchmark_import.py
backend/app/api/v1/routes/benchmark.py
frontend/src/pages/BenchmarksPage.tsx
benchmark_datasets/zh_*
backend/app/services/execution.py
backend/app/workers/tasks.py
backend/app/workers/queue.py
backend/app/workers/celery_app.py
backend/app/workers/recovery.py
backend/app/api/v1/routes/tasks.py
frontend/src/pages/TasksPage.tsx
frontend/src/pages/TaskDetailPage.tsx
backend/tests/test_dataset_adapters.py
backend/tests/test_benchmark_import.py
backend/tests/test_task_resume.py
backend/tests/test_task_events.py
```

### 任务 1：中文数据集

- 至少提交一份中文数据集样例。
- 中文适配器识别：

```text
提示词         -> prompt
数据集类型     -> dataset_type
样本类型       -> sample_kind
原始标签       -> raw_labels
语言           -> language
```

- `dataset_type` 只允许 `benign`、`harmful`、`jailbreak`。
- `sample_kind` 只允许 `seed`、`template`。
- 原始标签只作为元数据保存，不再映射风险类别。

### 任务 2：导入与展示

- 将 `dataset_type` 和 `sample_kind` 写入 `test_cases`。
- 导入结果返回 `dataset_type_counts`。
- `BenchmarksPage.tsx` 展示数据集类型和样本类型。
- 删除风险标签归一、未映射标签和风险类别相关展示。

### 任务 3：暂停、继续、断点续跑

已有接口：

```text
POST /api/v1/evaluation-tasks/{task_id}/actions/pause
POST /api/v1/evaluation-tasks/{task_id}/actions/resume
POST /api/v1/evaluation-tasks/{task_id}/actions/cancel
```

实现要求：

- `run_task_case` 开始前检查 `cancel_requested` 和 `pause_requested`。
- 暂停后停止派发新用例，已开始的请求允许安全结束。
- 继续时只派发 `pending` 用例，`succeeded` 用例不得重跑。
- 保存 Celery task id 到 `task_cases.celery_task_id`。
- 执行过程中更新 `task_cases.last_heartbeat_at` 和 `task_attempts.last_heartbeat_at`。
- 后端或 Worker 重启后，扫描未完成任务：
  - `pending` 用例重新入队。
  - heartbeat 超时的 `running` 用例重新置为 `pending` 或标记失败。
  - 已完成用例不再执行。
- 新增 `backend/app/workers/recovery.py`，由 Worker 启动时触发恢复。
- `task_cases`、`task_attempts` 必须保留。

提交前执行：

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q

cd ..\frontend
npm run typecheck
npm run build
```

## 三、提交与合并

```powershell
git fetch origin
git rebase origin/codex/contract-freeze
git push origin <自己的分支>
```

- 每人只提交自己列出的文件。
- 合并顺序：成员 2、成员 3、最后由组长统一集成。
- 组长合并后重新导出 `openapi.yaml`，并做一次后端测试和前端构建。

## 四、常见问题

### 看不到 contract-freeze-v1

`git branch -r` 只列远端分支，不会显示 tag。检查 tag 要用：

```powershell
git fetch origin --tags
git tag -l "contract-freeze*"
git ls-remote --tags origin
```

确认 tag 指向的提交：

```powershell
git rev-list -n 1 contract-freeze-v1
```

`contract-freeze-v1` 与 `origin/codex/contract-freeze` 指向同一个提交，用哪个作为 rebase 基线都可以。

### 前端报错

```text
does not provide an export named 'updateModel'
```

说明成员分支没有契约冻结里的 `frontend/src/api/index.ts`。执行：

```powershell
git fetch origin
git rebase origin/codex/contract-freeze
```

然后重启前端：

```powershell
cd frontend
Remove-Item -Recurse -Force node_modules\.vite -ErrorAction SilentlyContinue
npm run dev
```

### 后端请求 PATCH /models/{model_id} 返回 404

说明运行的是旧后端进程或旧分支。确认代码包含：

```text
backend/app/api/v1/routes/model.py
```

然后停止旧进程并重启：

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

`favicon.ico 404` 不影响页面运行，可以暂时忽略。
