import { useState } from 'react';
import { DeleteOutlined, PlusOutlined, ReloadOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { Alert, Button, Form, Input, Modal, Popconfirm, Select, Space, Table, Tag, message } from 'antd';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { checkModelHealth, createModel, deleteModel, listModels, updateModel } from '../api';
import { EmptyPanel, PageHeader } from '../components/ui';
import type { ModelRecord } from '../types/api';
import { formatDateTime } from '../utils/format';

function modelErrorMessage(error: unknown): string {
  if (typeof error === 'object' && error !== null && 'response' in error) {
    const response = (
      error as { response?: { data?: { detail?: unknown } } }
    ).response;
    if (typeof response?.data?.detail === 'string') return response.data.detail;
  }
  return error instanceof Error ? error.message : '操作失败';
}

export function ModelsPage() {
  const [open, setOpen] = useState(false);
  const [editingModel, setEditingModel] = useState<ModelRecord | null>(null);
  const [form] = Form.useForm();
  const queryClient = useQueryClient();

  const modelsQuery = useQuery({ queryKey: ['models'], queryFn: () => listModels({ page_size: 200 }) });

  const createMutation = useMutation({
    mutationFn: (values: Record<string, unknown>) =>
      editingModel ? updateModel(editingModel.model_id, values) : createModel(values),
    onSuccess: () => {
      message.success(editingModel ? '模型已更新' : '模型已创建');
      setOpen(false);
      setEditingModel(null);
      form.resetFields();
      queryClient.invalidateQueries({ queryKey: ['models'] });
    },
    onError: (error: unknown) => message.error(modelErrorMessage(error)),
  });

  const [checkingModelId, setCheckingModelId] = useState<number | null>(null);
  const [healthResults, setHealthResults] = useState<
    Record<number, { status: string; latencyMs?: number; error?: string }>
  >({});

  const deleteMutation = useMutation({
    mutationFn: deleteModel,
    onSuccess: (_, modelId) => {
      message.success('模型已删除');
      setHealthResults((current) => {
        const next = { ...current };
        delete next[modelId];
        return next;
      });
      queryClient.invalidateQueries({ queryKey: ['models'] });
    },
    onError: (error: unknown) => message.error(modelErrorMessage(error)),
  });

  const runHealthCheck = async (modelId: number) => {
    setCheckingModelId(modelId);
    try {
      const data = await checkModelHealth(modelId);
      setHealthResults((prev) => ({
        ...prev,
        [modelId]: { status: data.status, latencyMs: data.latency_ms },
      }));
      if (data.status === 'healthy') {
        message.success(`连接正常，延迟 ${data.latency_ms ?? '-'} ms`);
      } else {
        message.warning(`连接异常：${data.error_message ?? data.status}`);
      }
    } catch (error) {
      const text = error instanceof Error ? error.message : '连接测试失败';
      setHealthResults((prev) => ({ ...prev, [modelId]: { status: 'error', error: text } }));
      message.error(text);
    } finally {
      setCheckingModelId(null);
    }
  };

  return (
    <div className="page-stack">
      <PageHeader
        title="模型管理"
        description="统一管理被测模型和 Judge 模型。API Key 只保存引用，不保存明文。"
        extra={
          <Space>
            <Button icon={<ReloadOutlined />} onClick={() => modelsQuery.refetch()}>
              刷新
            </Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setOpen(true)}>
              新建模型
            </Button>
          </Space>
        }
      />

      {modelsQuery.isError ? (
        <Alert
          type="error"
          showIcon
          message="模型列表加载失败"
          description={
            (modelsQuery.error as Error)?.message ??
            '无法连接到后端服务，请确认 api 容器是否正常运行。'
          }
          action={
            <Button size="small" onClick={() => modelsQuery.refetch()}>
              重试
            </Button>
          }
        />
      ) : !modelsQuery.isLoading && !modelsQuery.data?.items.length ? (
        <EmptyPanel
          title="还没有接入模型"
          description="先创建一个模型配置，支持 OpenAI-compatible、Ollama、Custom HTTP 和 Mock 适配器。"
          action={
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setOpen(true)}>
              新建模型
            </Button>
          }
        />
      ) : (
        <Table<ModelRecord>
          rowKey="model_id"
          loading={modelsQuery.isLoading}
          dataSource={modelsQuery.data?.items ?? []}
          pagination={{ pageSize: 10 }}
          columns={[
            { title: 'ID', dataIndex: 'model_id', width: 80 },
            { title: '模型名称', dataIndex: 'name' },
            { title: '模型标识', dataIndex: 'model_name' },
            { title: '适配器', dataIndex: 'adapter_type', render: (value) => <Tag color="blue">{value}</Tag> },
            { title: '用途', dataIndex: 'usage_scope', render: (value) => <Tag color="purple">{value}</Tag> },
            {
              title: '密钥',
              dataIndex: 'secret_ref',
              width: 190,
              render: (value: string | null | undefined) =>
                value ? <Tag color="default">{value}</Tag> : <Tag>未配置</Tag>,
            },
            {
              title: '状态',
              dataIndex: 'enabled',
              width: 100,
              render: (value) => <Tag color={value ? 'success' : 'default'}>{value ? '启用' : '停用'}</Tag>,
            },
            { title: '创建时间', dataIndex: 'created_at', render: formatDateTime },
            {
              title: '连接状态',
              width: 170,
              render: (_, record) => {
                const result = healthResults[record.model_id];
                if (!result) return <Tag>未测试</Tag>;
                if (result.status === 'healthy') {
                  return <Tag color="success">正常 · {result.latencyMs ?? '-'} ms</Tag>;
                }
                if (result.status === 'error') {
                  return (
                    <Tag color="error" title={result.error}>
                      失败
                    </Tag>
                  );
                }
                return <Tag color="warning">{result.status}</Tag>;
              },
            },
            {
              title: '操作',
              width: 260,
              render: (_, record) => (
                <Space>
                  <Button
                    type="link"
                    onClick={() => {
                      setEditingModel(record);
                      setOpen(true);
                      form.setFieldsValue({ ...record, secret_ref: '' });
                    }}
                  >
                    编辑
                  </Button>
                  <Button
                    type="link"
                    icon={<ThunderboltOutlined />}
                    loading={checkingModelId === record.model_id}
                    disabled={checkingModelId !== null && checkingModelId !== record.model_id}
                    onClick={() => runHealthCheck(record.model_id)}
                  >
                    连接测试
                  </Button>
                  <Popconfirm
                    title="删除该模型？"
                    description="仅未被任务、历史结果或 Judge 配置引用的模型可以删除。"
                    okText="删除"
                    cancelText="取消"
                    okButtonProps={{ danger: true }}
                    onConfirm={() => deleteMutation.mutate(record.model_id)}
                  >
                    <Button
                      type="link"
                      danger
                      icon={<DeleteOutlined />}
                      loading={deleteMutation.isPending}
                    >
                      删除
                    </Button>
                  </Popconfirm>
                </Space>
              ),
            },
          ]}
        />
      )}

      <Modal
        title={editingModel ? '编辑模型' : '新建模型'}
        open={open}
        onCancel={() => {
          setOpen(false);
          setEditingModel(null);
          form.resetFields();
        }}
        onOk={() => form.submit()}
        confirmLoading={createMutation.isPending}
        destroyOnClose
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={{ adapter_type: 'openai_compatible', usage_scope: 'target', enabled: true }}
          onFinish={(values) => createMutation.mutate(values)}
        >
          <Form.Item name="name" label="模型名称" rules={[{ required: true }]}>
            <Input placeholder="例如：Qwen2.5-7B" />
          </Form.Item>
          <Form.Item name="provider" label="提供方" rules={[{ required: true }]}>
            <Input placeholder="例如：local / openai / ollama" />
          </Form.Item>
          <Form.Item name="adapter_type" label="适配器类型" rules={[{ required: true }]}>
            <Select
              options={[
                { value: 'openai_compatible', label: 'OpenAI-compatible' },
                { value: 'ollama', label: 'Ollama' },
                { value: 'custom_http', label: 'Custom HTTP' },
                { value: 'mock', label: 'Mock' },
              ]}
            />
          </Form.Item>
          <Form.Item name="base_url" label="服务地址" rules={[{ required: true }]}>
            <Input placeholder="http://127.0.0.1:11434/v1" />
          </Form.Item>
          <Form.Item name="model_name" label="模型标识" rules={[{ required: true }]}>
            <Input placeholder="qwen2.5:7b" />
          </Form.Item>
          <Form.Item
            name="secret_ref"
            label="密钥引用"
            extra={
              editingModel?.secret_configured
                ? `当前已配置：${editingModel.secret_ref ?? '****'}。留空表示不修改，重新填写才会覆盖。`
                : '格式为 env:变量名 或 literal:真实Key。推荐 env:DEEPSEEK_API_KEY，把 Key 写在 .env 中，避免明文入库。'
            }
          >
            <Input placeholder={editingModel ? '留空表示不修改' : 'env:DEEPSEEK_API_KEY'} />
          </Form.Item>
          <Form.Item name="usage_scope" label="用途" rules={[{ required: true }]}>
            <Select
              options={[
                { value: 'target', label: '被测模型' },
                { value: 'judge', label: 'Judge 模型' },
                { value: 'both', label: '两者都支持' },
              ]}
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
