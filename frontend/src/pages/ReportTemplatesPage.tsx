import { useState } from 'react';
import { CheckCircleOutlined, PlusOutlined } from '@ant-design/icons';
import { Button, Card, Col, Form, Input, List, Modal, Row, Select, Space, Tag, message } from 'antd';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createReportTemplate,
  createReportTemplateVersion,
  listReportTemplateVersions,
  listReportTemplates,
  publishReportTemplateVersion,
} from '../api';
import { EmptyPanel, PageHeader } from '../components/ui';
import type { ReportTemplate, ReportTemplateVersion } from '../types/api';

export function ReportTemplatesPage() {
  const queryClient = useQueryClient();
  const [selectedTemplate, setSelectedTemplate] = useState<ReportTemplate | null>(null);
  const [templateOpen, setTemplateOpen] = useState(false);
  const [versionOpen, setVersionOpen] = useState(false);
  const [templateForm] = Form.useForm();
  const [versionForm] = Form.useForm();

  const templatesQuery = useQuery({ queryKey: ['report-templates'], queryFn: () => listReportTemplates({ page_size: 200 }) });
  const versionsQuery = useQuery({
    queryKey: ['report-template-versions', selectedTemplate?.template_id],
    queryFn: () => listReportTemplateVersions(selectedTemplate!.template_id),
    enabled: Boolean(selectedTemplate?.template_id),
  });

  const createTemplateMutation = useMutation({
    mutationFn: createReportTemplate,
    onSuccess: () => {
      message.success('模板已创建');
      setTemplateOpen(false);
      templateForm.resetFields();
      queryClient.invalidateQueries({ queryKey: ['report-templates'] });
    },
    onError: (error: Error) => message.error(error.message),
  });

  const createVersionMutation = useMutation({
    mutationFn: (values: Record<string, unknown>) => createReportTemplateVersion(selectedTemplate!.template_id, values),
    onSuccess: () => {
      message.success('模板版本已创建');
      setVersionOpen(false);
      versionForm.resetFields();
      queryClient.invalidateQueries({ queryKey: ['report-template-versions'] });
    },
    onError: (error: Error) => message.error(error.message),
  });

  const publishMutation = useMutation({
    mutationFn: publishReportTemplateVersion,
    onSuccess: () => {
      message.success('版本已发布');
      queryClient.invalidateQueries({ queryKey: ['report-template-versions'] });
    },
    onError: (error: Error) => message.error(error.message),
  });

  const templates = templatesQuery.data?.items ?? [];
  const versions = versionsQuery.data?.items ?? [];

  return (
    <div className="page-stack">
      <PageHeader
        title="报告模板"
        description="管理报告模板和版本，支持 JSON、Markdown、HTML、CSV 自定义模板。"
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setTemplateOpen(true)}>
            新建模板
          </Button>
        }
      />

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={9}>
          <Card className="section-card" title="模板列表">
            {templates.length ? (
              <List
                dataSource={templates}
                renderItem={(item) => (
                  <List.Item
                    style={{ cursor: 'pointer', borderRadius: 12, paddingInline: 12, background: selectedTemplate?.template_id === item.template_id ? '#f2f6ff' : undefined }}
                    onClick={() => setSelectedTemplate(item)}
                  >
                    <List.Item.Meta
                      title={item.name}
                      description={<Space><Tag color="blue">{item.code}</Tag><Tag color={item.status === 'active' ? 'success' : 'default'}>{item.status}</Tag></Space>}
                    />
                  </List.Item>
                )}
              />
            ) : (
              <EmptyPanel title="暂无报告模板" description="创建第一个自定义报告模板。" />
            )}
          </Card>
        </Col>
        <Col xs={24} xl={15}>
          <Card
            className="section-card"
            title={selectedTemplate ? `${selectedTemplate.name} · 版本列表` : '版本列表'}
            extra={
              selectedTemplate ? (
                <Button type="primary" icon={<PlusOutlined />} onClick={() => setVersionOpen(true)}>
                  新建版本
                </Button>
              ) : null
            }
          >
            {selectedTemplate ? (
              <List
                dataSource={versions}
                renderItem={(item: ReportTemplateVersion) => (
                  <List.Item
                    actions={[
                      item.status !== 'published' ? (
                        <Button
                          key="publish"
                          type="link"
                          icon={<CheckCircleOutlined />}
                          loading={publishMutation.isPending}
                          onClick={() => publishMutation.mutate(item.template_version_id)}
                        >
                          发布
                        </Button>
                      ) : (
                        <Tag key="published" color="success">已发布</Tag>
                      ),
                    ]}
                  >
                    <List.Item.Meta
                      title={<Space><Tag color="purple">{item.version}</Tag><Tag color="blue">{item.format}</Tag></Space>}
                      description={<div className="code-block" style={{ marginTop: 8, maxHeight: 120, overflow: 'auto' }}>{item.content}</div>}
                    />
                  </List.Item>
                )}
              />
            ) : (
              <EmptyPanel title="请选择模板" description="从左侧选择一个报告模板，查看或创建版本。" />
            )}
          </Card>
        </Col>
      </Row>

      <Modal title="新建报告模板" open={templateOpen} onCancel={() => setTemplateOpen(false)} onOk={() => templateForm.submit()} confirmLoading={createTemplateMutation.isPending}>
        <Form form={templateForm} layout="vertical" onFinish={(values) => createTemplateMutation.mutate(values)}>
          <Form.Item name="code" label="模板编码" rules={[{ required: true }]}>
            <Input placeholder="例如：security-report-v2" />
          </Form.Item>
          <Form.Item name="name" label="模板名称" rules={[{ required: true }]}>
            <Input placeholder="例如：安全评测标准报告" />
          </Form.Item>
          <Form.Item name="description" label="说明">
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal title="新建模板版本" open={versionOpen} onCancel={() => setVersionOpen(false)} onOk={() => versionForm.submit()} confirmLoading={createVersionMutation.isPending} width={720}>
        <Form form={versionForm} layout="vertical" initialValues={{ format: 'json', status: 'draft' }} onFinish={(values) => createVersionMutation.mutate(values)}>
          <Form.Item name="version" label="版本号" rules={[{ required: true }]}>
            <Input placeholder="v1" />
          </Form.Item>
          <Form.Item name="format" label="格式" rules={[{ required: true }]}>
            <Select options={[{ value: 'json' }, { value: 'md' }, { value: 'html' }, { value: 'csv' }]} />
          </Form.Item>
          <Form.Item name="content" label="模板内容" rules={[{ required: true }]}>
            <Input.TextArea rows={10} placeholder={'例如：{"task": {{ task.task_id }}, "total": {{ statistics.total_results }}}'} />
          </Form.Item>
          <Form.Item name="status" label="状态">
            <Select options={[{ value: 'draft' }, { value: 'published' }]} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
