import { useEffect, useState } from 'react';
import {
  EyeOutlined,
  PlusOutlined,
  SaveOutlined,
  ThunderboltOutlined,
  UploadOutlined,
} from '@ant-design/icons';
import {
  Alert,
  Button,
  Col,
  Descriptions,
  Form,
  Input,
  List,
  Modal,
  Popconfirm,
  Row,
  Select,
  Space,
  Table,
  Tag,
  Upload,
  message,
} from 'antd';
import type { UploadFile } from 'antd';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createAttackTemplate,
  createAttackTemplateVersion,
  disableAttackTemplate,
  listAttackTemplates,
  listAttackTemplateVersions,
  previewAttackTemplate,
  publishAttackTemplateVersion,
  updateAttackTemplate,
} from '../api';
import { EmptyPanel } from '../components/ui';
import type { AttackTemplate, AttackTemplatePreviewResult } from '../types/api';

const { Dragger } = Upload;

type TemplateImportDraft = {
  name: string;
  template_text: string;
  variables: string[];
  version: string;
  status: string;
};

const TEMPLATE_IMPORT_ACCEPT = '.json,.jsonl,.ndjson,.txt';
const TEMPLATE_IMPORT_LIMIT = 500;

function errorMessage(error: unknown): string {
  if (typeof error === 'object' && error !== null && 'response' in error) {
    const response = (
      error as { response?: { data?: { detail?: unknown } } }
    ).response;
    if (typeof response?.data?.detail === 'string') return response.data.detail;
  }
  return error instanceof Error ? error.message : '未知错误';
}

function detectVariables(templateText: string): string[] {
  const names = new Set<string>();
  const pattern =
    /\{\{\s*([A-Za-z_][A-Za-z0-9_.]*)\s*\}\}|\{([A-Za-z_][A-Za-z0-9_.]*)\}/g;
  for (const match of templateText.matchAll(pattern)) {
    const name = match[1] ?? match[2];
    if (!name) continue;
    names.add(['seed', 'behavior'].includes(name) ? 'prompt' : name);
  }
  if (/\{\s*0\s*\}/.test(templateText)) names.add('prompt');
  return Array.from(names);
}

function normalizeVariables(value: unknown, templateText: string): string[] {
  const detected = detectVariables(templateText);
  if (Array.isArray(value)) {
    return Array.from(
      new Set([
        ...value
          .map((item) => String(item).trim())
          .filter(Boolean)
          .map((item) =>
            ['0', 'seed', 'behavior'].includes(item) ? 'prompt' : item,
          ),
        ...detected,
      ]),
    );
  }
  if (typeof value === 'string') {
    return Array.from(
      new Set([
        ...value
          .split(/[,;，；\s]+/)
          .map((item) => item.trim())
          .filter(Boolean)
          .map((item) =>
            ['0', 'seed', 'behavior'].includes(item) ? 'prompt' : item,
          ),
        ...detected,
      ]),
    );
  }
  return detected;
}

function draftFromRecord(
  record: unknown,
  baseName: string,
  index: number,
): TemplateImportDraft {
  if (typeof record === 'string') {
    const templateText = record.trim();
    if (!templateText) throw new Error('模板内容为空');
    return {
      name: `${baseName}-${index}`,
      template_text: templateText,
      variables: detectVariables(templateText),
      version: 'v1',
      status: 'active',
    };
  }

  if (typeof record !== 'object' || record === null || Array.isArray(record)) {
    throw new Error('模板记录必须是对象或字符串');
  }

  const row = record as Record<string, unknown>;
  const templateText = row.template_text ?? row.template ?? row.text ?? row.prompt;
  if (typeof templateText !== 'string' || !templateText.trim()) {
    throw new Error('缺少 template_text 字段');
  }

  const name = String(row.name ?? `${baseName}-${index}`).trim();
  const version = String(row.version ?? 'v1').trim() || 'v1';
  const status = ['active', 'draft', 'disabled'].includes(String(row.status))
    ? String(row.status)
    : 'active';

  return {
    name,
    template_text: templateText.trim(),
    variables: normalizeVariables(row.variables, templateText),
    version,
    status,
  };
}

async function parseTemplateFile(file: File): Promise<TemplateImportDraft[]> {
  const content = await file.text();
  const suffix = file.name.split('.').pop()?.toLowerCase() ?? '';
  const baseName = file.name.replace(/\.[^.]+$/, '');
  let records: unknown[];

  if (suffix === 'json') {
    const payload: unknown = JSON.parse(content);
    if (Array.isArray(payload)) {
      records = payload;
    } else if (typeof payload === 'object' && payload !== null) {
      const object = payload as Record<string, unknown>;
      const nested = object.items ?? object.templates ?? object.data;
      records = Array.isArray(nested) ? nested : [payload];
    } else {
      records = [payload];
    }
  } else if (suffix === 'jsonl' || suffix === 'ndjson') {
    records = content
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => {
        try {
          return JSON.parse(line) as unknown;
        } catch {
          return line;
        }
      });
  } else if (suffix === 'txt') {
    records = content
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);
  } else {
    throw new Error('只支持 JSON、JSONL、NDJSON、TXT 文件');
  }

  if (!records.length) throw new Error('文件中没有模板');
  if (records.length > TEMPLATE_IMPORT_LIMIT) {
    throw new Error(`单个文件最多导入 ${TEMPLATE_IMPORT_LIMIT} 条模板`);
  }

  return records.map((record, index) => draftFromRecord(record, baseName, index + 1));
}

export function AttackTemplatesPage() {
  const queryClient = useQueryClient();
  const [templateOpen, setTemplateOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [importFiles, setImportFiles] = useState<UploadFile[]>([]);
  const [importErrors, setImportErrors] = useState<string[]>([]);
  const [editingTemplate, setEditingTemplate] = useState<AttackTemplate | null>(null);
  const [previewTemplate, setPreviewTemplate] = useState<AttackTemplate | null>(null);
  const [previewResult, setPreviewResult] = useState<AttackTemplatePreviewResult | null>(null);
  const [previewVariables, setPreviewVariables] = useState<Record<string, string>>({});
  const [versionTemplate, setVersionTemplate] = useState<AttackTemplate | null>(null);
  const [templateForm] = Form.useForm();
  const [versionForm] = Form.useForm();

  const templatesQuery = useQuery({
    queryKey: ['attack-templates'],
    queryFn: () => listAttackTemplates({ page_size: 200 }),
  });
  const versionsQuery = useQuery({
    queryKey: ['attack-template-versions', versionTemplate?.attack_template_id],
    queryFn: () => listAttackTemplateVersions(versionTemplate!.attack_template_id),
    enabled: Boolean(versionTemplate?.attack_template_id),
  });

  useEffect(() => {
    if (editingTemplate) {
      templateForm.setFieldsValue(editingTemplate);
      return;
    }
    templateForm.resetFields();
    templateForm.setFieldsValue({
      version: 'v1',
      status: 'active',
      template_text: '{prompt}',
      variables: ['prompt'],
    });
  }, [editingTemplate, templateForm]);

  const templateMutation = useMutation({
    mutationFn: (values: Record<string, unknown>) =>
      editingTemplate
        ? updateAttackTemplate(editingTemplate.attack_template_id, values)
        : createAttackTemplate({ ...values, method_code: 'custom' }),
    onSuccess: () => {
      message.success(editingTemplate ? '模板已更新' : '模板已创建');
      setTemplateOpen(false);
      setEditingTemplate(null);
      queryClient.invalidateQueries({ queryKey: ['attack-templates'] });
    },
    onError: (error: unknown) => {
      const detail = errorMessage(error);
      if (detail.includes('already exists')) {
        message.error('创建失败：该模板名称和版本已经存在，请修改名称或版本号。');
      } else {
        message.error(`操作失败：${detail}`);
      }
    },
  });

  const importMutation = useMutation({
    mutationFn: async () => {
      const files = importFiles
        .map((item) => item.originFileObj)
        .filter((item): item is NonNullable<typeof item> => Boolean(item));
      if (!files.length) throw new Error('请选择模板文件');

      const drafts = (
        await Promise.all(files.map((file) => parseTemplateFile(file)))
      ).flat();
      if (!drafts.length) throw new Error('没有可导入的模板');

      const errors: string[] = [];
      let imported = 0;
      for (const draft of drafts) {
        try {
          await createAttackTemplate({ ...draft, method_code: 'custom' });
          imported += 1;
        } catch (error) {
          errors.push(`${draft.name}: ${errorMessage(error)}`);
        }
      }
      return { imported, errors };
    },
    onSuccess: ({ imported, errors }) => {
      queryClient.invalidateQueries({ queryKey: ['attack-templates'] });
      if (imported) message.success(`已导入 ${imported} 条模板`);
      setImportErrors(errors);
      if (!errors.length) {
        setImportOpen(false);
        setImportFiles([]);
      }
    },
    onError: (error: unknown) => message.error(errorMessage(error)),
  });

  const previewMutation = useMutation({
    mutationFn: () => previewAttackTemplate(previewTemplate!.attack_template_id, previewVariables),
    onSuccess: (result) => setPreviewResult(result),
    onError: (error: unknown) => message.error(errorMessage(error)),
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
    onError: (error: unknown) => message.error(errorMessage(error)),
  });

  const publishMutation = useMutation({
    mutationFn: publishAttackTemplateVersion,
    onSuccess: () => {
      message.success('模板版本已发布');
      queryClient.invalidateQueries({ queryKey: ['attack-template-versions'] });
      queryClient.invalidateQueries({ queryKey: ['attack-templates'] });
    },
    onError: (error: unknown) => message.error(errorMessage(error)),
  });

  const templates = (templatesQuery.data?.items ?? []).filter(
    (item) => item.status !== 'disabled',
  );
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
    <div>
      <div
        style={{
          display: 'flex',
          justifyContent: 'flex-end',
          gap: 12,
          marginBottom: 16,
        }}
      >
        <Button icon={<UploadOutlined />} onClick={() => setImportOpen(true)}>
          导入模板
        </Button>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => {
            setEditingTemplate(null);
            setTemplateOpen(true);
          }}
        >
          新建模板
        </Button>
      </div>

      {templates.length ? (
        <Table<AttackTemplate>
          rowKey="attack_template_id"
          loading={templatesQuery.isLoading}
          dataSource={templates}
          pagination={{ pageSize: 10 }}
          columns={[
            { title: 'ID', dataIndex: 'attack_template_id', width: 80 },
            { title: '名称', dataIndex: 'name' },
            { title: '版本', dataIndex: 'version', width: 90, render: (value) => <Tag color="blue">{value}</Tag> },
            {
              title: '变量',
              dataIndex: 'variables',
              render: (value: string[]) => (
                <Space wrap>
                  {(value ?? []).map((item) => (
                    <Tag key={item}>{item}</Tag>
                  ))}
                </Space>
              ),
            },
            { title: '状态', dataIndex: 'status', width: 100, render: (value) => <Tag color={value === 'active' ? 'success' : 'default'}>{value}</Tag> },
            {
              title: '操作',
              width: 280,
              render: (_, record) => (
                <Space>
                  <Button type="link" icon={<EyeOutlined />} onClick={() => openPreview(record)}>
                    预览
                  </Button>
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
                  <Button
                    type="link"
                    onClick={() => {
                      setEditingTemplate(record);
                      setTemplateOpen(true);
                    }}
                  >
                    编辑
                  </Button>
                  <Popconfirm
                    title="确认删除"
                    description="确定要删除这个模板吗？"
                    onConfirm={() => {
                      disableAttackTemplate(record.attack_template_id).then(() => {
                        message.success('删除成功');
                        queryClient.invalidateQueries({ queryKey: ['attack-templates'] });
                      });
                    }}
                    okText="确定"
                    cancelText="取消"
                  >
                    <Button type="link" danger>
                      删除
                    </Button>
                  </Popconfirm>
                </Space>
              ),
            },
          ]}
        />
      ) : (
        <EmptyPanel title="暂无模板" description="导入官方模板，或新建自己的模板。" />
      )}

      <Modal
        title={editingTemplate ? '编辑模板' : '新建模板'}
        open={templateOpen}
        width={760}
        onCancel={() => setTemplateOpen(false)}
        onOk={() => templateForm.submit()}
        confirmLoading={templateMutation.isPending}
      >
        <Form
          form={templateForm}
          layout="vertical"
          onFinish={(values) => templateMutation.mutate(values)}
        >
          <Form.Item name="name" label="模板名称" rules={[{ required: true }]}>
            <Input placeholder="例如：DAN 官方模板" />
          </Form.Item>
          <Form.Item name="version" label="版本" rules={[{ required: true }]}>
            <Input disabled={Boolean(editingTemplate)} />
          </Form.Item>
          <Form.Item
            name="template_text"
            label="模板内容"
            rules={[{ required: true, message: '请输入模板内容' }]}
          >
            <Input.TextArea rows={8} placeholder="支持 {prompt}、{0}、{seed}、{behavior}" />
          </Form.Item>
          <Form.Item name="variables" label="变量列表">
            <Select mode="tags" placeholder="输入变量名按回车" />
          </Form.Item>
          <Form.Item name="status" label="状态">
            <Select options={[{ value: 'active' }, { value: 'draft' }, { value: 'disabled' }]} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="导入模板"
        open={importOpen}
        width={760}
        onCancel={() => {
          setImportOpen(false);
          setImportErrors([]);
        }}
        onOk={() => importMutation.mutate()}
        okText="开始导入"
        confirmLoading={importMutation.isPending}
      >
        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          <Dragger
            multiple
            accept={TEMPLATE_IMPORT_ACCEPT}
            beforeUpload={() => false}
            fileList={importFiles}
            onChange={({ fileList }) => setImportFiles(fileList)}
          >
            <p className="ant-upload-drag-icon">
              <UploadOutlined />
            </p>
            <p className="ant-upload-text">点击或拖拽模板文件到这里</p>
            <p className="ant-upload-hint">
              支持 JSON、JSONL、NDJSON、TXT。JSON 字段为 name、template_text、variables、version、status；TXT 每行一条模板。
            </p>
          </Dragger>
          {importErrors.length ? (
            <Alert
              type="warning"
              showIcon
              message={`${importErrors.length} 条模板导入失败`}
              description={
                <div style={{ maxHeight: 180, overflow: 'auto' }}>
                  {importErrors.map((item) => (
                    <div key={item}>{item}</div>
                  ))}
                </div>
              }
            />
          ) : null}
        </Space>
      </Modal>

      <Modal
        title={`模板预览 · ${previewTemplate?.name ?? ''}`}
        open={Boolean(previewTemplate)}
        width={760}
        onCancel={() => setPreviewTemplate(null)}
        footer={[
          <Button key="close" onClick={() => setPreviewTemplate(null)}>
            关闭
          </Button>,
          <Button
            key="refresh"
            type="primary"
            icon={<EyeOutlined />}
            loading={previewMutation.isPending}
            onClick={() => previewMutation.mutate()}
          >
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
              <Descriptions.Item label="检测到的变量">
                {previewResult.detected_variables.join(', ') || '无'}
              </Descriptions.Item>
            </Descriptions>
            {previewResult.detected_variables.map((name) => (
              <Input
                key={name}
                addonBefore={name}
                value={previewVariables[name] ?? ''}
                onChange={(event) =>
                  setPreviewVariables((current) => ({
                    ...current,
                    [name]: event.target.value,
                  }))
                }
                placeholder={`请输入 ${name}`}
              />
            ))}
            <pre className="code-block">{previewResult.rendered_prompt}</pre>
          </Space>
        ) : null}
      </Modal>

      <Modal
        title={`版本管理 · ${versionTemplate?.name ?? ''}`}
        open={Boolean(versionTemplate)}
        width={760}
        onCancel={() => setVersionTemplate(null)}
        footer={null}
      >
        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          <List
            dataSource={versions}
            renderItem={(item) => (
              <List.Item
                actions={[
                  item.status !== 'active' ? (
                    <Button
                      key="publish"
                      type="link"
                      onClick={() => publishMutation.mutate(item.attack_template_id)}
                    >
                      发布
                    </Button>
                  ) : (
                    <Tag key="active" color="success">
                      当前版本
                    </Tag>
                  ),
                ]}
              >
                <List.Item.Meta
                  title={
                    <Space>
                      <Tag color="blue">{item.version}</Tag>
                      <Tag color={item.status === 'active' ? 'success' : 'default'}>
                        {item.status}
                      </Tag>
                    </Space>
                  }
                  description={
                    <pre
                      className="code-block"
                      style={{ marginTop: 8, maxHeight: 120, overflow: 'auto' }}
                    >
                      {item.template_text}
                    </pre>
                  }
                />
              </List.Item>
            )}
          />
          <Form
            form={versionForm}
            layout="vertical"
            initialValues={{ status: 'draft' }}
            onFinish={(values) => versionMutation.mutate(values)}
          >
            <Row gutter={16}>
              <Col span={12}>
                <Form.Item name="version" label="新版本号" rules={[{ required: true }]}>
                  <Input placeholder="v2" />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item name="status" label="状态">
                  <Select
                    options={[
                      { value: 'draft' },
                      { value: 'active' },
                      { value: 'disabled' },
                    ]}
                  />
                </Form.Item>
              </Col>
            </Row>
            <Form.Item name="template_text" label="模板内容（留空则复制当前版本）">
              <Input.TextArea rows={5} />
            </Form.Item>
            <Button
              type="primary"
              icon={<SaveOutlined />}
              loading={versionMutation.isPending}
              onClick={() => versionForm.submit()}
            >
              创建新版本
            </Button>
          </Form>
        </Space>
      </Modal>
    </div>
  );
}
