# LLM Guard 前端

大模型越狱攻击安全评测平台前端，技术栈：

- Vite
- React + TypeScript
- Ant Design
- React Router
- TanStack Query
- Axios
- Recharts

## 页面

- 工作台
- 统计分析
- 模型管理
- Benchmark 管理
- 攻击模板
- 风险分类
- 评测任务
- 任务详情
- 结果查询
- 人工复核
- Judge 配置
- 报告中心
- 报告模板
- 系统配置
- 审计日志

## 启动

```powershell
npm install
npm run dev
```

默认地址：

```text
http://127.0.0.1:5173
```

Vite 已配置代理：

```text
/api -> http://127.0.0.1:8000
```

因此启动前端前，请先确保后端运行在 `127.0.0.1:8000`。

## 构建与检查

```powershell
npm run typecheck
npm run build
```

## 环境变量

复制 `.env.example` 为 `.env`：

```text
VITE_API_BASE_URL=/api/v1
```

如果不使用 Vite 代理，也可以改成完整后端地址，例如：

```text
VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

## 当前前端状态

- 已完成整体布局、侧边栏、顶部栏和 15 个页面路由。
- 已完成模型管理、评测任务、任务详情、统计分析、报告生成、报告模板页面。
- 已对接后端 OpenAPI 中的主要接口。
- Benchmark 导入、攻击模板 CRUD、风险映射、Judge 配置、人工复核等页面已建立视觉骨架，等待后端管理接口完善后继续接真实数据。

## 风险分类与映射

页面路径：

```text
/risk-taxonomy
```

功能：

- 新建和选择风险体系。
- 查看和新建风险分类树。
- 选择 Benchmark 和版本。
- 查看标签映射进度。
- 为原始标签选择统一风险类别。
- 保存映射并刷新未映射数量。

## 攻击方法与攻击模板

页面路径：

```text
/attack-templates
```

功能：

- 攻击方法创建、编辑、停用。
- 攻击模板创建、编辑、停用。
- 模板变量标签管理。
- 变量校验：检测变量、缺失变量、未使用变量、未声明变量。
- 模板预览与变量渲染。
- 版本列表、创建新版本、发布版本。

## Judge 配置管理

页面路径：

```text
/judge
```

功能：

- Judge 配置列表。
- 新建、编辑、停用 Judge。
- 配置 Judge 类型、模型、策略和 Prompt 模板。
- 配置 Judge 参数 JSON。
- 查询任务 Judge 可信度。
- 重新评价 Judge 结果。

## 人工复核管理

页面路径：

```text
/reviews
```

功能：

- 待复核队列。
- 复核历史。
- 复核详情。
- 测试 Prompt 和模型输出查看。
- Judge、规则命中和原始风险查看。
- 风险类别修正。
- 风险分修正。
- 复核意见提交。


## Docker 构建

项目根目录的 `docker-compose.yml` 会构建前端镜像，并用 Nginx 托管静态文件、代理 `/api` 到 FastAPI 服务。

单独构建前端镜像：

```powershell
docker build -t llm-eval-frontend:local .
```
