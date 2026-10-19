import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  EyeOutlined,
  PauseCircleOutlined,
  PlayCircleOutlined,
  PlusOutlined,
  RedoOutlined,
  ReloadOutlined,
  StopOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { Button, Form, Input, InputNumber, Modal, Popconfirm, Progress, Select, Space, Table, message } from 'antd';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  cancelTask,
  createTask,
  listAttackTemplates,
  listBenchmarkVersions,
  listBenchmarks,
  listJudgeProfiles,
  listModels,
  listTasks,
  pauseTask,
  resumeTask,
  retryFailedTask,
  startTask,
} from '../api';
import { PageHeader, TaskStatusTag } from '../components/ui';
import type { EvaluationTask } from '../types/api';
import { formatDateTime } from '../utils/format';

export function TasksPage() {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [form] = Form.useForm();
  const queryClient = useQueryClient();
  const benchmarkId = Form.useWatch('benchmark_id', form);

  const tasksQuery = useQuery({ queryKey: ['tasks'], queryFn: () => listTasks({ page_size: 200 }) });
  const modelsQuery = useQuery({ queryKey: ['models', 'tasks'], queryFn: () => listModels({ page_size: 200 }) });
  const benchmarksQuery = useQuery({ queryKey: ['benchmarks', 'tasks'], queryFn: () => listBenchmarks({ page_size: 200 }) });
  const versionsQuery = useQuery({
    queryKey: ['benchmark-versions', benchmarkId],
    queryFn: () => listBenchmarkVersions(benchmarkId),
    enabled: Boolean(benchmarkId),
  });
  const templatesQuery = useQuery({
    queryKey: ['attack-templates', 'tasks'],
    queryFn: () => listAttackTemplates({ page_size: 200 }),
  });
  const judgesQuery = useQuery({
    queryKey: ['judge-profiles', 'tasks'],
    queryFn: () => listJudgeProfiles({ page_size: 200 }),
  });

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
        description="选择 Benchmark、被测模型、Judge 和规则集，创建越狱安全评测任务，并支持暂停/继续/断点续跑。"
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
          { title: '状态', dataIndex: 'status', width: 130, render: (value) => <TaskStatusTag status={value} /> },
          {
            title: '进度',
            dataIndex: 'progress',
            width: 180,
            render: (value) => <Progress percent={Math.round((value ?? 0) * 100)} size="small" />,
          },
          { title: '用例数', dataIndex: 'total_cases', width: 100 },
          { title: '完成 / 失败', width: 120, render: (_, record) => `${record.completed_cases} / ${record.failed_cases}` },
          { title: '创建时间', dataIndex: 'created_at', render: formatDateTime },
          {
            title: '操作',
            width: 340,
            render: (_, record) => (
              <Space wrap>
                <Button type="link" icon={<EyeOutlined />} onClick={() => navigate(`/tasks/${record.task_id}`)}>
                  详情
                </Button>
                {record.status === 'draft' ? (
                  <Button
                    type="link"
                    icon={<ThunderboltOutlined />}
                    loading={startMutation.isPending}
                    onClick={() => startMutation.mutate(record.task_id)}
                  >
                    启动
                  </Button>
                ) : null}
                {canPause(record.status) ? (
                  <Button
                    type="link"
                    icon={<PauseCircleOutlined />}
                    loading={pauseMutation.isPending}
                    onClick={() => pauseMutation.mutate(record.task_id)}
                  >
                    暂停
                  </Button>
                ) : null}
                {canResume(record.status) ? (
                  <Button
                    type="link"
                    icon={<PlayCircleOutlined />}
                    loading={resumeMutation.isPending}
                    onClick={() => resumeMutation.mutate(record.task_id)}
                  >
                    继续
                  </Button>
                ) : null}
                {record.status === 'failed' || record.status === 'partially_failed' ? (
                  <Button
                    type="link"
                    icon={<RedoOutlined />}
                    loading={retryMutation.isPending}
                    onClick={() => retryMutation.mutate(record.task_id)}
                  >
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
                    <Button type="link" danger icon={<StopOutlined />} loading={cancelMutation.isPending}>
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
        width={720}
        onCancel={() => setOpen(false)}
        onOk={() => form.submit()}
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
            concurrency: 2,
          }}
          onFinish={(values) => {
            createMutation.mutate({
              name: values.name,
              benchmark_version_id: values.benchmark_version_id,
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
            });
          }}
        >
          <Form.Item name="name" label="任务名称" rules={[{ required: true }]}>
            <Input placeholder="例如：Qwen2.5-7B 越狱基线评测" />
          </Form.Item>
          <Form.Item name="benchmark_id" label="Benchmark" rules={[{ required: true }]}>
            <Select
              placeholder="选择 Benchmark"
              options={(benchmarksQuery.data?.items ?? []).map((item) => ({
                value: item.benchmark_id,
                label: `${item.name}（${item.slug}）`,
              }))}
            />
          </Form.Item>
          <Form.Item name="benchmark_version_id" label="Benchmark 版本" rules={[{ required: true }]}>
            <Select
              placeholder="选择版本"
              loading={versionsQuery.isLoading}
              options={(versionsQuery.data?.items ?? []).map((item) => ({
                value: item.benchmark_version_id,
                label: `${item.version} · ${item.case_count} 条用例`,
              }))}
            />
          </Form.Item>
          <Form.Item
            name="model_ids"
            label="被测模型"
            rules={[{ required: true, type: 'array', min: 1, message: '请至少选择一个被测模型' }]}
          >
            <Select
              mode="multiple"
              placeholder="选择一个或多个模型进行对比"
              options={(modelsQuery.data?.items ?? [])
                .filter((item) => item.usage_scope === 'target' || item.usage_scope === 'both')
                .map((item) => ({ value: item.model_id, label: `${item.name} · ${item.adapter_type}` }))}
            />
          </Form.Item>
          <Form.Item
            name="attack_template_ids"
            label="攻击模板"
            extra="不选则使用原始 Prompt 直接请求（相当于 direct_request 基线）"
          >
            <Select
              mode="multiple"
              allowClear
              placeholder="选择一个或多个攻击模板"
              loading={templatesQuery.isLoading}
              options={(templatesQuery.data?.items ?? []).map((item) => ({
                value: item.attack_template_id,
                label: `${item.name} · ${item.version}`,
              }))}
            />
          </Form.Item>
          <Form.Item
            name="judge_profile_ids"
            label="Judge 配置"
            extra="不选则只使用引擎内置的默认规则 Judge"
          >
            <Select
              mode="multiple"
              allowClear
              placeholder="选择一个或多个 Judge（建议同时选规则 Judge 和模型 Judge）"
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