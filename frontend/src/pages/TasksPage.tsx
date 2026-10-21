import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  CheckSquareOutlined,
  ClearOutlined,
  EyeOutlined,
  PauseCircleOutlined,
  PlayCircleOutlined,
  PlusOutlined,
  RedoOutlined,
  ReloadOutlined,
  StopOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import {
  Alert,
  Button,
  Col,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Progress,
  Row,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  message,
} from 'antd';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  cancelTask,
  createTask,
  listAttackTemplates,
  listBenchmarks,
  listJudgeProfiles,
  listModels,
  listTasks,
  listTestCases,
  pauseTask,
  resumeTask,
  retryFailedTask,
  startTask,
} from '../api';
import { PageHeader, TaskStatusTag } from '../components/ui';
import type { EvaluationTask, TestCase } from '../types/api';
import { formatDateTime } from '../utils/format';

const STRATEGY_TYPES = [
  { value: 'static', label: '静态模板（不变换）' },
  { value: 'transform', label: '纯变换（Base64 / Puzzler）' },
  { value: 'iterative', label: 'PAIR 迭代（多轮）' },
];

const STRATEGY_CODES: Record<string, Array<{ value: string; label: string }>> = {
  static: [{ value: 'static', label: 'static · 原样发送' }],
  transform: [
    { value: 'base64', label: 'base64 · Base64 编码' },
    { value: 'puzzler', label: 'puzzler · Puzzler 谜题' },
  ],
  iterative: [{ value: 'pair', label: 'pair · PAIR 迭代' }],
};

export function TasksPage() {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [form] = Form.useForm();
  const queryClient = useQueryClient();

  const seedBenchmarkId = Form.useWatch('seed_benchmark_id', form);
  const selectedSeedIds = Form.useWatch('seed_test_case_ids', form) as number[] | undefined;
  const strategyType = Form.useWatch('strategy_type', form);
  const strategyCode = Form.useWatch('strategy_code', form);
  const [seedSearchInput, setSeedSearchInput] = useState('');
  const [seedKeyword, setSeedKeyword] = useState('');
  const [seedOptions, setSeedOptions] = useState<TestCase[]>([]);
  const [seedBatchLoading, setSeedBatchLoading] = useState(false);

  const tasksQuery = useQuery({ queryKey: ['tasks'], queryFn: () => listTasks({ page_size: 200 }) });
  const modelsQuery = useQuery({ queryKey: ['models', 'tasks'], queryFn: () => listModels({ page_size: 200 }) });
  const templatesQuery = useQuery({
    queryKey: ['attack-templates', 'tasks'],
    queryFn: () => listAttackTemplates({ page_size: 200 }),
  });
  const judgesQuery = useQuery({
    queryKey: ['judge-profiles', 'tasks'],
    queryFn: () => listJudgeProfiles({ page_size: 200 }),
  });
  const benchmarksQuery = useQuery({
    queryKey: ['benchmarks', 'tasks'],
    queryFn: () => listBenchmarks({ page_size: 200 }),
  });

  useEffect(() => {
    const timer = window.setTimeout(() => setSeedKeyword(seedSearchInput.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [seedSearchInput]);

  useEffect(() => {
    form.setFieldValue('seed_test_case_ids', []);
    setSeedOptions([]);
    setSeedSearchInput('');
    setSeedKeyword('');
  }, [seedBenchmarkId, form]);

  const seedQuery = useQuery({
    queryKey: ['seed-test-cases', seedBenchmarkId, seedKeyword],
    queryFn: () =>
      listTestCases({
        benchmark_id: seedBenchmarkId,
        keyword: seedKeyword || undefined,
        status: 'active',
        page: 1,
        page_size: 50,
      }),
    enabled: open && Boolean(seedBenchmarkId),
  });

  useEffect(() => {
    if (!open) return;
    const items = seedQuery.data?.items ?? [];
    if (!items.length) return;
    setSeedOptions((current) => {
      const byId = new Map(current.map((item) => [item.test_case_id, item]));
      items.forEach((item) => byId.set(item.test_case_id, item));
      return Array.from(byId.values());
    });
  }, [open, seedQuery.data]);

  const seedSelectOptions = useMemo(
    () =>
      seedOptions.map((item) => ({
        value: item.test_case_id,
        label: `${item.external_id} · ${(item.prompt || '').slice(0, 40)}${
          (item.prompt || '').length > 40 ? '…' : ''
        } · ${item.dataset_type}`,
      })),
    [seedOptions],
  );

  const selectAllSeeds = async () => {
    if (!seedBenchmarkId) {
      message.warning('请先选择种子库');
      return;
    }
    setSeedBatchLoading(true);
    try {
      const items: TestCase[] = [];
      let page = 1;
      for (let guard = 0; guard < 100; guard += 1) {
        const result = await listTestCases({
          benchmark_id: seedBenchmarkId,
          status: 'active',
          page,
          page_size: 200,
        });
        items.push(...result.items);
        if (!result.has_next || !result.items.length) break;
        page += 1;
      }
      setSeedOptions(items);
      form.setFieldValue(
        'seed_test_case_ids',
        items.map((item) => item.test_case_id),
      );
      message.success(`已选择当前种子库的 ${items.length} 条种子`);
    } catch (error) {
      message.error(error instanceof Error ? error.message : '批量选择失败');
    } finally {
      setSeedBatchLoading(false);
    }
  };

  const createMutation = useMutation({
    mutationFn: createTask,
    onSuccess: (task) => {
      message.success(`任务 #${task.task_id} 已创建`);
      setOpen(false);
      form.resetFields();
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
      navigate(`/tasks/${task.task_id}`);
    },
    onError: (error: Error) => message.error(error.message),
  });

  const startMutation = useMutation({
    mutationFn: startTask,
    onSuccess: () => {
      message.success('任务已启动');
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
    },
    onError: (error: Error) => message.error(error.message),
  });

  const pauseMutation = useMutation({
    mutationFn: pauseTask,
    onSuccess: () => {
      message.success('任务已暂停，已开始的用例会安全执行完成');
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
    },
    onError: (error: Error) => message.error(error.message),
  });

  const resumeMutation = useMutation({
    mutationFn: resumeTask,
    onSuccess: () => {
      message.success('任务已继续，仅重跑未完成的用例');
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
    },
    onError: (error: Error) => message.error(error.message),
  });

  const retryMutation = useMutation({
    mutationFn: retryFailedTask,
    onSuccess: (data) => {
      message.success(`已提交 ${data.retry_count} 个失败用例重试`);
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
    },
    onError: (error: Error) => message.error(error.message),
  });

  const cancelMutation = useMutation({
    mutationFn: cancelTask,
    onSuccess: () => {
      message.success('任务已取消');
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
    },
    onError: (error: Error) => message.error(error.message),
  });

  const canPause = (status: string) => status === 'running' || status === 'queued';
  const canResume = (status: string) => status === 'paused';
  const canCancel = (status: string) => ['running', 'queued', 'paused'].includes(status);

  return (
    <div className="page-stack">
      <PageHeader
        title="评测任务"
        description="选择种子问题、模板、被测模型与 Judge，创建越狱安全评测任务，并支持暂停、继续和断点续跑。"
        extra={
          <Space>
            <Button icon={<ReloadOutlined />} onClick={() => tasksQuery.refetch()}>
              刷新
            </Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setOpen(true)}>
              创建任务
            </Button>
          </Space>
        }
      />

      <Table<EvaluationTask>
        rowKey="task_id"
        loading={tasksQuery.isLoading}
        dataSource={tasksQuery.data?.items ?? []}
        pagination={{ pageSize: 10 }}
        columns={[
          { title: 'ID', dataIndex: 'task_id', width: 80 },
          { title: '任务名称', dataIndex: 'name' },
          {
            title: '状态',
            dataIndex: 'status',
            width: 130,
            render: (value) => <TaskStatusTag status={value} />,
          },
          {
            title: '进度',
            dataIndex: 'progress',
            width: 180,
            render: (value) => <Progress percent={Math.round((value ?? 0) * 100)} size="small" />,
          },
          { title: '用例数', dataIndex: 'total_cases', width: 100 },
          {
            title: '完成 / 失败',
            width: 120,
            render: (_, record) => `${record.completed_cases} / ${record.failed_cases}`,
          },
          { title: '创建时间', dataIndex: 'created_at', render: formatDateTime },
          {
            title: '操作',
            width: 340,
            render: (_, record) => (
              <Space wrap>
                <Button
                  type="link"
                  icon={<EyeOutlined />}
                  onClick={() => navigate(`/tasks/${record.task_id}`)}
                >
                  详情
                </Button>
                {record.status === 'draft' ? (
                  <Button type="link" icon={<ThunderboltOutlined />} loading={startMutation.isPending} onClick={() => startMutation.mutate(record.task_id)}>
                    启动
                  </Button>
                ) : null}
                {canPause(record.status) ? (
                  <Button type="link" icon={<PauseCircleOutlined />} loading={pauseMutation.isPending} onClick={() => pauseMutation.mutate(record.task_id)}>
                    暂停
                  </Button>
                ) : null}
                {canResume(record.status) ? (
                  <Button type="link" icon={<PlayCircleOutlined />} loading={resumeMutation.isPending} onClick={() => resumeMutation.mutate(record.task_id)}>
                    继续
                  </Button>
                ) : null}
                {record.status === 'failed' || record.status === 'partially_failed' ? (
                  <Button type="link" icon={<RedoOutlined />} loading={retryMutation.isPending} onClick={() => retryMutation.mutate(record.task_id)}>
                    重试失败
                  </Button>
                ) : null}
                {canCancel(record.status) ? (
                  <Popconfirm
                    title="确定要取消该任务吗？"
                    description="取消后无法恢复，已跑的用例将保留。"
                    onConfirm={() => cancelMutation.mutate(record.task_id)}
                    okText="确定"
                    cancelText="再想想"
                    okButtonProps={{ danger: true }}
                  >
                    <Button
                      type="link"
                      danger
                      icon={<StopOutlined />}
                      loading={cancelMutation.isPending}
                    >
                      取消
                    </Button>
                  </Popconfirm>
                ) : null}
              </Space>
            ),
          },
        ]}
      />

      <Modal
        title="创建评测任务"
        open={open}
        width={760}
        onCancel={() => setOpen(false)}
        onOk={() => form.submit()}
        afterClose={() => {
          setSeedSearchInput('');
          setSeedKeyword('');
          setSeedOptions([]);
        }}
        confirmLoading={createMutation.isPending}
        destroyOnClose
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={{
            model_ids: [],
            repeat: 1,
            timeout_seconds: 120,
            concurrency: 4,
            seed_benchmark_id: undefined,
            seed_test_case_ids: [],
            sample_size: 50,
            seed_dataset_type: undefined,
            strategy_type: 'static',
            strategy_code: 'static',
            strategy_style: 'riddle',
            strategy_enabled: true,
            max_rounds: 3,
          }}
          onFinish={(values) => {
            const strategyCodeValue = values.strategy_code ?? 'static';
            const strategyConfig: Record<string, unknown> = {};
            if (strategyCodeValue === 'puzzler') {
              strategyConfig.style = values.strategy_style ?? 'riddle';
            }
            if (values.strategy_type === 'iterative') {
              strategyConfig.max_rounds = values.max_rounds ?? 3;
            }
            createMutation.mutate({
              name: values.name,
              benchmark_id: values.seed_benchmark_id,
              seed_test_case_ids: values.seed_test_case_ids ?? [],
              sample_size: values.sample_size ?? 50,
              model_bindings: (values.model_ids ?? []).map((modelId: number) => ({
                model_id: modelId,
                role: 'target',
                model_params: {
                  temperature: values.temperature ?? 0.2,
                  max_tokens: values.max_tokens ?? 1024,
                },
              })),
              attack_template_ids: values.attack_template_ids ?? [],
              judge_profile_ids: values.judge_profile_ids ?? [],
              rule_set_ids: [],
              execution: {
                repeat: values.repeat,
                timeout_seconds: values.timeout_seconds,
                retry: { max_attempts: 1, backoff_seconds: 3 },
                concurrency: values.concurrency,
              },
              max_rounds: values.max_rounds ?? 3,
              attacker_model_id:
                values.strategy_type === 'iterative' ? values.attacker_model_id : undefined,
              attack_strategy: {
                type: values.strategy_type ?? 'static',
                code: strategyCodeValue,
                config: strategyConfig,
                enabled: values.strategy_enabled !== false,
              },
            } as any);
          }}
        >
          <Form.Item name="name" label="任务名称" rules={[{ required: true }]}>
            <Input placeholder="例如：Qwen2.5-7B 越狱基线评测" />
          </Form.Item>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="seed_benchmark_id"
                label="种子库"
                rules={[{ required: true, message: '请选择种子库' }]}
              >
                <Select
                  showSearch
                  optionFilterProp="label"
                  placeholder="选择种子库"
                  loading={benchmarksQuery.isLoading}
                  options={(benchmarksQuery.data?.items ?? []).map((item) => ({
                    value: item.benchmark_id,
                    label: `${item.name}（${item.slug}）`,
                  }))}
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="sample_size"
                label="自动采样条数"
                extra="未手动选择种子时生效"
              >
                <InputNumber min={1} max={100000} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            name="seed_test_case_ids"
            label={
              <Space>
                种子问题
                {selectedSeedIds?.length ? (
                  <Tag color="blue">已选 {selectedSeedIds.length} 条</Tag>
                ) : null}
              </Space>
            }
            extra="选择种子库后可搜索；点击“全选当前库”批量选择。未选择种子时按采样条数自动抽取"
          >
            <Space.Compact style={{ width: '100%' }}>
              <Select
                mode="multiple"
                allowClear
                showSearch
                maxTagCount="responsive"
                filterOption={false}
                style={{ flex: 1 }}
                placeholder={seedBenchmarkId ? '搜索或选择种子问题' : '请先选择种子库'}
                disabled={!seedBenchmarkId}
                loading={seedQuery.isFetching}
                onSearch={setSeedSearchInput}
                options={seedSelectOptions}
                notFoundContent={
                  seedQuery.isFetching
                    ? '搜索中…'
                    : seedKeyword
                      ? '没有匹配的种子'
                      : '输入关键词开始搜索'
                }
              />
              <Button
                icon={<CheckSquareOutlined />}
                loading={seedBatchLoading}
                disabled={!seedBenchmarkId}
                onClick={selectAllSeeds}
              >
                全选当前库
              </Button>
              <Button
                icon={<ClearOutlined />}
                disabled={!selectedSeedIds?.length}
                onClick={() => form.setFieldValue('seed_test_case_ids', [])}
              >
                清空
              </Button>
            </Space.Compact>
          </Form.Item>

          <Form.Item name="model_ids" label="被测模型" rules={[{ required: true, type: 'array', min: 1, message: '请至少选择一个被测模型' }]}>
            <Select
              mode="multiple"
              placeholder="选择一个或多个模型进行对比"
              options={(modelsQuery.data?.items ?? [])
                .filter((item) => item.usage_scope === 'target' || item.usage_scope === 'both')
                .map((item) => ({
                  value: item.model_id,
                  label: `${item.name} · ${item.adapter_type}`,
                }))}
            />
          </Form.Item>

          <Form.Item
            name="attack_template_ids"
            label="模板"
            extra="模板是官方越狱 Prompt；不选则直接使用种子原文请求"
          >
            <Select
              mode="multiple"
              allowClear
              placeholder="选择一个或多个模板"
              loading={templatesQuery.isLoading}
              options={(templatesQuery.data?.items ?? []).map((item) => ({
                value: item.attack_template_id,
                label: `${item.name} · ${item.version}`,
              }))}
            />
          </Form.Item>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="strategy_type" label="攻击方式">
                <Select
                  options={STRATEGY_TYPES}
                  onChange={(value) => {
                    const defaultCode =
                      value === 'transform' ? 'base64' : value === 'iterative' ? 'pair' : 'static';
                    form.setFieldValue('strategy_code', defaultCode);
                  }}
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="strategy_code" label="具体方式">
                <Select
                  options={STRATEGY_CODES[strategyType ?? 'static'] ?? STRATEGY_CODES.static}
                />
              </Form.Item>
            </Col>
          </Row>

          {strategyCode === 'puzzler' ? (
            <Form.Item name="strategy_style" label="Puzzler 风格">
              <Select
                options={[
                  { value: 'riddle', label: 'riddle · 谜题' },
                  { value: 'story', label: 'story · 故事' },
                  { value: 'reverse', label: 'reverse · 倒序' },
                ]}
              />
            </Form.Item>
          ) : null}

          <Form.Item
            name="strategy_enabled"
            label="启用策略变换"
            valuePropName="checked"
            extra="关闭后即使选择了 Base64 / Puzzler 也按原始 Prompt 发送"
          >
            <Switch checkedChildren="启用" unCheckedChildren="停用" />
          </Form.Item>

          {strategyType === 'iterative' ? (
            <>
              <Alert
                type="info"
                showIcon
                style={{ marginBottom: 16 }}
                message="PAIR 迭代需要攻击模型"
                description="攻击模型生成 → 目标模型回答 → Judge 判定 → 根据反馈改写；命中 unsafe 会提前停止。"
              />
              <Row gutter={16}>
                <Col span={16}>
                  <Form.Item
                    name="attacker_model_id"
                    label="攻击模型（PAIR）"
                    rules={[{ required: true, message: 'PAIR 迭代必须选择攻击模型' }]}
                  >
                    <Select
                      showSearch
                      optionFilterProp="label"
                      placeholder="选择 OpenAI-compatible 或 Ollama 模型"
                      options={(modelsQuery.data?.items ?? [])
                        .filter((item) =>
                          ['openai_compatible', 'ollama'].includes(item.adapter_type),
                        )
                        .map((item) => ({
                          value: item.model_id,
                          label: `${item.name} · ${item.adapter_type}`,
                        }))}
                    />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item name="max_rounds" label="最大迭代轮数">
                    <InputNumber min={1} max={20} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
              </Row>
            </>
          ) : null}

          <Form.Item
            name="judge_profile_ids"
            label="Judge 配置"
            extra="不选则只使用引擎内置的默认规则 Judge"
          >
            <Select
              mode="multiple"
              allowClear
              placeholder="选择一个或多个 Judge"
              loading={judgesQuery.isLoading}
              options={(judgesQuery.data?.items ?? []).map((item) => ({
                value: item.judge_profile_id,
                label: `${item.name} · ${item.judge_type}`,
              }))}
            />
          </Form.Item>

          <Space size={16} style={{ display: 'flex' }}>
            <Form.Item name="repeat" label="重复次数" style={{ flex: 1 }}>
              <InputNumber min={1} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item name="timeout_seconds" label="单次超时（秒）" style={{ flex: 1 }}>
              <InputNumber min={1} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item name="concurrency" label="并发数" style={{ flex: 1 }}>
              <InputNumber min={1} style={{ width: '100%' }} />
            </Form.Item>
          </Space>
        </Form>
      </Modal>
    </div>
  );
}