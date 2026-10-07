import { useState } from 'react';
import { PlusOutlined, ReloadOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { Button, Form, Input, Modal, Select, Space, Table, Tag, message } from 'antd';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { checkModelHealth, createModel, listModels } from '../api';
import { EmptyPanel, PageHeader } from '../components/ui';
import type { ModelRecord } from '../types/api';
import { formatDateTime } from '../utils/format';

export function ModelsPage() {
  const [open, setOpen] = useState(false);
  const [form] = Form.useForm();
  const queryClient = useQueryClient();

  const modelsQuery = useQuery({ queryKey: ['models'], queryFn: () => listModels({ page_size: 200 }) });

  const createMutation = useMutation({
    mutationFn: createModel,
    onSuccess: () => {
      message.success('模型已创建');
      setOpen(false);
      form.resetFields();
      queryClient.invalidateQueries({ queryKey: ['models'] });
    },
    onError: (error: Error) => message.error(error.message),
  });

  const healthMutation = useMutation({
    mutationFn: checkModelHealth,
    onSuccess: (data) => message.success(`模型状态：${data.status}`),
    onError: (error: Error) => message.error(error.message),
  });

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

      {!modelsQuery.isLoading && !modelsQuery.data?.items.length ? (
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
              title: '状态',
              dataIndex: 'enabled',
              width: 100,
              render: (value) => <Tag color={value ? 'success' : 'default'}>{value ? '启用' : '停用'}</Tag>,
            },
            { title: '创建时间', dataIndex: 'created_at', render: formatDateTime },
            {
              title: '操作',
              width: 150,
              render: (_, record) => (
                <Button
                  type="link"
                  icon={<ThunderboltOutlined />}
                  loading={healthMutation.isPending}
                  onClick={() => healthMutation.mutate(record.model_id)}
                >
                  连接测试
                </Button>
              ),
            },
          ]}
        />
      )}

      <Modal
        title="新建模型"
        open={open}
        onCancel={() => setOpen(false)}
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
          <Form.Item name="secret_ref" label="密钥引用">
            <Input placeholder="env:QWEN_API_KEY，不填表示无密钥" />
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
