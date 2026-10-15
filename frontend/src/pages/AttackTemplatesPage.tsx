import { useEffect, useState } from 'react';
import { EyeOutlined, PlusOutlined, SaveOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { Alert, Button, Col, Descriptions, Form, Input, List, Modal, Row, Select, Space, Table, Tag, message } from 'antd';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createAttackTemplate,
  createAttackTemplateVersion,
  disableAttackTemplate,
  listAttackMethods,
  listAttackTemplates,
  listAttackTemplateVersions,
  previewAttackTemplate,
  publishAttackTemplateVersion,
  updateAttackTemplate,
} from '../api';
import { EmptyPanel, PageHeader } from '../components/ui';
import type { AttackTemplate, AttackTemplatePreviewResult } from '../types/api';

export function AttackTemplatesPage() {
  const queryClient = useQueryClient();
  const [templateOpen, setTemplateOpen] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<AttackTemplate | null>(null);
  const [previewTemplate, setPreviewTemplate] = useState<AttackTemplate | null>(null);
  const [previewResult, setPreviewResult] = useState<AttackTemplatePreviewResult | null>(null);
  const [previewVariables, setPreviewVariables] = useState<Record<string, string>>({});
  const [versionTemplate, setVersionTemplate] = useState<AttackTemplate | null>(null);
  const [templateForm] = Form.useForm();
  const [versionForm] = Form.useForm();

  const methodsQuery = useQuery({ queryKey: ['attack-methods'], queryFn: listAttackMethods });
  const templatesQuery = useQuery({ queryKey: ['attack-templates'], queryFn: () => listAttackTemplates({ page_size: 200 }) });
  const versionsQuery = useQuery({
    queryKey: ['attack-template-versions', versionTemplate?.attack_template_id],
    queryFn: () => listAttackTemplateVersions(versionTemplate!.attack_template_id),
    enabled: Boolean(versionTemplate?.attack_template_id),
  });

  useEffect(() => {
    if (editingTemplate) {
      templateForm.setFieldsValue(editingTemplate);
    } else {
      templateForm.resetFields();
      templateForm.setFieldsValue({ method_code: 'direct_request', version: 'v1', status: 'active', variables: [] });
    }
  }, [editingTemplate, templateForm]);

  const templateMutation = useMutation({
    mutationFn: (values: Record<string, unknown>) =>
      editingTemplate ? updateAttackTemplate(editingTemplate.attack_template_id, values) : createAttackTemplate(values),
    onSuccess: () => {
      message.success(editingTemplate ? '攻击模板已更新' : '攻击模板已创建');
      setTemplateOpen(false);
      setEditingTemplate(null);
      queryClient.invalidateQueries({ queryKey: ['attack-templates'] });
    },
    onError: (error: Error) => message.error(error.message),
  });

  const previewMutation = useMutation({
    mutationFn: () => previewAttackTemplate(previewTemplate!.attack_template_id, previewVariables),
    onSuccess: (result) => setPreviewResult(result),
    onError: (error: Error) => message.error(error.message),
  });

  const versionMutation = useMutation({
    mutationFn: (values: Record<string, unknown>) =>
      createAttackTemplateVersion(versionTemplate!.attack_template_id, values),
    onSuccess: () => {
      message.success('模板版本已创建');
      versionForm.resetFields();
      queryClient.invalidateQueries({ queryKey: ['attack-template-versions'] });
      queryClient.invalidateQueries({ queryKey: ['attack-templates'] });
    },
    onError: (error: Error) => message.error(error.message),
  });

  const publishMutation = useMutation({
    mutationFn: publishAttackTemplateVersion,
    onSuccess: () => {
      message.success('模板版本已发布');
      queryClient.invalidateQueries({ queryKey: ['attack-template-versions'] });
      queryClient.invalidateQueries({ queryKey: ['attack-templates'] });
    },
    onError: (error: Error) => message.error(error.message),
  });

  const methods = methodsQuery.data?.items ?? [];
  const templates = templatesQuery.data?.items ?? [];
  const versions = versionsQuery.data ?? [];

  const openPreview = (template: AttackTemplate) => {
    setPreviewTemplate(template);
    setPreviewResult(null);
    setPreviewVariables({});
    previewMutation.mutate(undefined, {
      onSuccess: (result) => {
        setPreviewResult(result);
        const initial: Record<string, string> = {};
        for (const name of result.detected_variables) initial[name] = '';
        setPreviewVariables(initial);
      },
    });
  };

  return (
    <div className="page-stack">
      <PageHeader
        title="攻击方法与模板"
        description="攻击方式固定为四种，只维护 Prompt 模板、变量校验、预览和版本发布。"
        extra={
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => {
              setEditingTemplate(null);
              setTemplateOpen(true);
            }}
          >
            新建攻击模板
          </Button>
        }
      />

      <Alert
        type="info"
        showIcon
        message="固定攻击方式"
        description={methods.map((item) => `${item.name}（${item.code}）`).join(' · ')}
      />

      {templates.length ? (
        <Table<AttackTemplate>
          rowKey="attack_template_id"
          loading={templatesQuery.isLoading}
          dataSource={templates}
          pagination={{ pageSize: 10 }}
          columns={[
            { title: 'ID', dataIndex: 'attack_template_id', width: 80 },
            { title: '名称', dataIndex: 'name' },
            { title: '攻击方式', dataIndex: 'method_code', width: 170, render: (value) => <Tag color="purple">{value}</Tag> },
            { title: '版本', dataIndex: 'version', width: 90, render: (value) => <Tag color="blue">{value}</Tag> },
            { title: '变量', dataIndex: 'variables', render: (value: string[]) => <Space wrap>{(value ?? []).map((item) => <Tag key={item}>{item}</Tag>)}</Space> },
            { title: '状态', dataIndex: 'status', width: 100, render: (value) => <Tag color={value === 'active' ? 'success' : 'default'}>{value}</Tag> },
            {
              title: '操作',
              width: 280,
              render: (_, record) => (
                <Space>
                  <Button type="link" icon={<EyeOutlined />} onClick={() => openPreview(record)}>预览</Button>
                  <Button
                    type="link"
                    icon={<ThunderboltOutlined />}
                    onClick={() => {
                      setVersionTemplate(record);
                      versionForm.resetFields();
                      versionForm.setFieldsValue({ status: 'draft' });
                    }}
                  >
                    版本
                  </Button>
                  <Button type="link" onClick={() => { setEditingTemplate(record); setTemplateOpen(true); }}>编辑</Button>
                  <Button
                    type="link"
                    danger
                    disabled={record.status === 'disabled'}
                    onClick={() => disableAttackTemplate(record.attack_template_id).then(() => queryClient.invalidateQueries({ queryKey: ['attack-templates'] }))}
                  >
                    停用
                  </Button>
                </Space>
              ),
            },
          ]}
        />
      ) : (
        <EmptyPanel title="暂无攻击模板" description="创建攻击模板并绑定固定的攻击方式。" />
      )}

      <Modal
        title={editingTemplate ? '编辑攻击模板' : '新建攻击模板'}
        open={templateOpen}
        width={760}
        onCancel={() => setTemplateOpen(false)}
        onOk={() => templateForm.submit()}
        confirmLoading={templateMutation.isPending}
      >
        <Form form={templateForm} layout="vertical" onFinish={(values) => templateMutation.mutate(values)}>
          <Form.Item name="method_code" label="攻击方式" rules={[{ required: true }]}>
            <Select
              disabled={Boolean(editingTemplate)}
              options={methods.map((item) => ({ value: item.code, label: `${item.name} · ${item.code}` }))}
            />
          </Form.Item>
          <Form.Item name="name" label="模板名称" rules={[{ required: true }]}>
            <Input placeholder="角色扮演模板" />
          </Form.Item>
          <Form.Item name="version" label="版本" rules={[{ required: true }]}>
            <Input disabled={Boolean(editingTemplate)} />
          </Form.Item>
          <Form.Item name="template_text" label="模板内容" rules={[{ required: true }]}>
            <Input.TextArea rows={7} placeholder="你现在扮演 {role}，请回答：{prompt}" />
          </Form.Item>
          <Form.Item name="variables" label="变量列表">
            <Select mode="tags" placeholder="输入变量名，例如 role、prompt" />
          </Form.Item>
          <Form.Item name="status" label="状态">
            <Select options={[{ value: 'active' }, { value: 'draft' }, { value: 'disabled' }]} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={`模板预览 · ${previewTemplate?.name ?? ''}`}
        open={Boolean(previewTemplate)}
        width={760}
        onCancel={() => setPreviewTemplate(null)}
        footer={[
          <Button key="close" onClick={() => setPreviewTemplate(null)}>关闭</Button>,
          <Button key="refresh" type="primary" icon={<EyeOutlined />} loading={previewMutation.isPending} onClick={() => previewMutation.mutate()}>
            重新预览
          </Button>,
        ]}
      >
        {previewResult ? (
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <Alert
              type={previewResult.valid ? 'success' : 'warning'}
              showIcon
              message={previewResult.valid ? '变量校验通过' : '变量校验存在问题'}
            />
            <Descriptions column={1} size="small">
              <Descriptions.Item label="检测到的变量">{previewResult.detected_variables.join(', ') || '无'}</Descriptions.Item>
            </Descriptions>
            {previewResult.detected_variables.map((name) => (
              <Input
                key={name}
                addonBefore={name}
                value={previewVariables[name] ?? ''}
                onChange={(event) => setPreviewVariables((current) => ({ ...current, [name]: event.target.value }))}
                placeholder={`请输入 ${name}`}
              />
            ))}
            <pre className="code-block">{previewResult.rendered_prompt}</pre>
          </Space>
        ) : null}
      </Modal>

      <Modal title={`版本管理 · ${versionTemplate?.name ?? ''}`} open={Boolean(versionTemplate)} width={760} onCancel={() => setVersionTemplate(null)} footer={null}>
        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          <List
            dataSource={versions}
            renderItem={(item) => (
              <List.Item
                actions={[
                  item.status !== 'active' ? (
                    <Button key="publish" type="link" onClick={() => publishMutation.mutate(item.attack_template_id)}>发布</Button>
                  ) : <Tag key="active" color="success">当前版本</Tag>,
                ]}
              >
                <List.Item.Meta
                  title={<Space><Tag color="blue">{item.version}</Tag><Tag color={item.status === 'active' ? 'success' : 'default'}>{item.status}</Tag></Space>}
                  description={<pre className="code-block" style={{ marginTop: 8, maxHeight: 120, overflow: 'auto' }}>{item.template_text}</pre>}
                />
              </List.Item>
            )}
          />
          <Form form={versionForm} layout="vertical" initialValues={{ status: 'draft' }} onFinish={(values) => versionMutation.mutate(values)}>
            <Row gutter={16}>
              <Col span={12}>
                <Form.Item name="version" label="新版本号" rules={[{ required: true }]}>
                  <Input placeholder="v2" />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item name="status" label="状态">
                  <Select options={[{ value: 'draft' }, { value: 'active' }, { value: 'disabled' }]} />
                </Form.Item>
              </Col>
            </Row>
            <Form.Item name="template_text" label="模板内容（留空则复制当前版本）">
              <Input.TextArea rows={5} />
            </Form.Item>
            <Button type="primary" icon={<SaveOutlined />} loading={versionMutation.isPending} onClick={() => versionForm.submit()}>
              创建新版本
            </Button>
          </Form>
        </Space>
      </Modal>
    </div>
  );
}
