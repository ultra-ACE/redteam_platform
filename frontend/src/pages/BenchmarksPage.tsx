import { useMemo, useState } from 'react';
import { DeleteOutlined, InboxOutlined, PlusOutlined, ReloadOutlined, SearchOutlined } from '@ant-design/icons';
import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Form,
  Input,
  List,
  Modal,
  Popconfirm,
  Row,
  Segmented,
  Select,
  Space,
  Table,
  Tabs,
  Tag,
  Upload,
  message,
} from 'antd';
import type { UploadFile } from 'antd';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  deleteBenchmark,
  importBenchmark,
  listBenchmarkAdapters,
  listBenchmarks,
  listTestCases,
} from '../api';
import { EmptyPanel, PageHeader } from '../components/ui';
import { AttackTemplatesPage as AttackTemplatesTab } from './AttackTemplatesPage';
import type { Benchmark, BenchmarkImportResult } from '../types/api';
import { formatDateTime } from '../utils/format';
import {
  TEMPLATE_IMPORT_ACCEPT,
  getErrorMessage,
  importTemplateFiles,
} from '../utils/templateImport';
import type { TemplateImportSummary } from '../utils/templateImport';

const { Dragger } = Upload;

export function BenchmarksPage() {
  const queryClient = useQueryClient();
  const [selectedBenchmark, setSelectedBenchmark] = useState<Benchmark | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const [importTarget, setImportTarget] = useState<'seed' | 'template'>('seed');
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [importResults, setImportResults] = useState<Array<BenchmarkImportResult & { file_name: string }>>([]);
  const [templateImportResult, setTemplateImportResult] = useState<TemplateImportSummary | null>(null);
  const [templateLibraryName, setTemplateLibraryName] = useState('默认模板库');
  const [testCaseKeyword, setTestCaseKeyword] = useState('');
  const [form] = Form.useForm();

  const benchmarksQuery = useQuery({ queryKey: ['benchmarks'], queryFn: () => listBenchmarks({ page_size: 200 }) });
  const testCasesQuery = useQuery({
    queryKey: ['test-cases', selectedBenchmark?.benchmark_id],
    queryFn: () => listTestCases({ benchmark_id: selectedBenchmark!.benchmark_id, page_size: 200 }),
    enabled: Boolean(selectedBenchmark?.benchmark_id),
  });
  const adaptersQuery = useQuery({
    queryKey: ['benchmark-adapters'],
    queryFn: listBenchmarkAdapters,
    staleTime: 5 * 60 * 1000,
  });

  const importMutation = useMutation({
    mutationFn: async (payloads: Array<{ formData: FormData; file_name: string }>) => {
      const results: Array<BenchmarkImportResult & { file_name: string }> = [];
      for (const payload of payloads) {
        try {
          const result = await importBenchmark(payload.formData);
          results.push({ ...result, file_name: payload.file_name });
        } catch (error) {
          const text = error instanceof Error ? error.message : '导入失败';
          results.push({
            benchmark_id: 0,
            imported_count: 0,
            failed_count: 1,
            errors: [{ row_number: 0, message: text }],
            file_name: payload.file_name,
          });
        }
      }
      return results;
    },
    onSuccess: (results) => {
      setImportResults(results);
      const succeeded = results.filter((item) => item.imported_count > 0).length;
      const totalImported = results.reduce((sum, item) => sum + item.imported_count, 0);
      if (succeeded === results.length) {
        message.success(`${results.length} 个文件导入完成，共 ${totalImported} 条种子`);
      } else {
        message.warning(`${results.length} 个文件中成功 ${succeeded} 个，请查看导入结果`);
      }
      queryClient.invalidateQueries({ queryKey: ['benchmarks'] });
      queryClient.invalidateQueries({ queryKey: ['test-cases'] });
    },
  });

  const templateImportMutation = useMutation({
    mutationFn: (files: File[]) => importTemplateFiles(files, templateLibraryName),
    onSuccess: (result) => {
      setTemplateImportResult(result);
      if (result.imported) {
        message.success(`已导入 ${result.imported} 条模板`);
      }
      if (result.errors.length) {
        message.warning(`${result.errors.length} 条模板导入失败，请查看导入结果`);
      }
      queryClient.invalidateQueries({ queryKey: ['attack-templates'] });
    },
    onError: (error: unknown) => message.error(getErrorMessage(error)),
  });

  const deleteBenchmarkMutation = useMutation({
    mutationFn: deleteBenchmark,
    onSuccess: (summary) => {
      message.success(
        `已删除 ${summary.deleted_test_cases} 条测试用例`,
      );
      setSelectedBenchmark(null);
      queryClient.invalidateQueries({ queryKey: ['benchmarks'] });
      queryClient.invalidateQueries({ queryKey: ['test-cases'] });
    },
    onError: (error: Error) => message.error(error.message),
  });

  const benchmarks = benchmarksQuery.data?.items ?? [];
  const testCases = testCasesQuery.data?.items ?? [];

  const selectedBenchmarkName = useMemo(() => selectedBenchmark?.name ?? '未选择种子库', [selectedBenchmark]);

  /** 用例表格的本地筛选：支持按来源编号、提示词正文、原始标签和数字 ID 查找。 */
  const filteredTestCases = useMemo(() => {
    const normalized = testCaseKeyword.trim().toLowerCase();
    if (!normalized) return testCases;
    return testCases.filter((item) =>
      [item.external_id, item.prompt, item.source_label, String(item.test_case_id)].some((value) =>
        (value ?? '').toLowerCase().includes(normalized),
      ),
    );
  }, [testCaseKeyword, testCases]);

  const resetImport = () => {
    setImportResults([]);
    setTemplateImportResult(null);
    setTemplateLibraryName('默认模板库');
    setFileList([]);
    form.resetFields();
  };

  const handleImport = () => {
    const files = fileList
      .map((item) => item.originFileObj)
      .filter((item): item is NonNullable<UploadFile['originFileObj']> => Boolean(item));
    if (!files.length) {
      message.warning(importTarget === 'seed' ? '请选择种子数据文件' : '请选择模板文件');
      return;
    }
    if (importTarget === 'template') {
      templateImportMutation.mutate(files);
      return;
    }
    form
      .validateFields()
      .then((values) => {
        const benchmarkName = String(values.name ?? '').trim();
        if (!benchmarkName || benchmarkName === 'undefined') {
          message.error('请填写有效的种子库名称');
          return;
        }
        const payloads = files.map((file) => {
          const formData = new FormData();
          formData.append('name', benchmarkName);
          // 留空则由后端按表头签名自动识别数据集结构
          if (values.source_type) {
            formData.append('source_type', String(values.source_type));
          }
          formData.append('file', file);
          return { formData, file_name: file.name };
        });
        importMutation.mutate(payloads);
      })
      .catch(() => undefined);
  };

  const hasImportResult =
    importTarget === 'seed'
      ? importResults.length > 0
      : templateImportResult !== null;

  // --- 种子管理原本的核心内容 ---
  const seedContent = (
    <>
      <Row gutter={[16, 16]}>
        <Col xs={24} xl={8}>
          <Card className="section-card" title="种子库列表">
            {benchmarks.length ? (
              <List
                dataSource={benchmarks}
                renderItem={(item) => (
                  <List.Item
                    style={{
                      cursor: 'pointer',
                      borderRadius: 12,
                      paddingInline: 12,
                      background: selectedBenchmark?.benchmark_id === item.benchmark_id ? '#f2f6ff' : undefined,
                    }}
                    onClick={() => {
                      setSelectedBenchmark(item);
                    }}
                  >
                    <List.Item.Meta
                      title={item.name}
                      description={
                        <Space>
                          <Tag color="blue">{item.slug}</Tag>
                          <Tag>{item.case_count} 条种子</Tag>
                          <Tag color={item.status === 'active' ? 'success' : 'default'}>{item.status}</Tag>
                        </Space>
                      }
                    />
                    <Popconfirm
                      title="删除该种子库？"
                      description="将同时删除其中的全部种子问题，无法恢复。"
                      okText="删除"
                      cancelText="取消"
                      okButtonProps={{ danger: true, loading: deleteBenchmarkMutation.isPending }}
                      onConfirm={() => deleteBenchmarkMutation.mutate(item.benchmark_id)}
                    >
                      <Button
                        type="text"
                        danger
                        size="small"
                        icon={<DeleteOutlined />}
                        onClick={(event) => event.stopPropagation()}
                      />
                    </Popconfirm>
                  </List.Item>
                )}
              />
            ) : (
              <EmptyPanel
                title="暂无种子库"
                description="导入一份种子数据集，创建第一个种子库。"
                action={<Button type="primary" icon={<PlusOutlined />} onClick={() => setImportOpen(true)}>导入数据</Button>}
              />
            )}
          </Card>
        </Col>

        <Col xs={24} xl={16}>
          <Card className="section-card" title={`${selectedBenchmarkName} · 种子库信息`}>
            {selectedBenchmark ? (
              <Descriptions column={2} size="small" bordered>
                <Descriptions.Item label="种子数量">{selectedBenchmark.case_count}</Descriptions.Item>
                <Descriptions.Item label="状态">
                  <Tag color={selectedBenchmark.status === 'active' ? 'success' : 'default'}>
                    {selectedBenchmark.status}
                  </Tag>
                </Descriptions.Item>
                <Descriptions.Item label="校验和">
                  <code>{String(selectedBenchmark.checksum ?? '').slice(0, 24)}</code>
                </Descriptions.Item>
                <Descriptions.Item label="导入时间">
                  {formatDateTime(selectedBenchmark.imported_at)}
                </Descriptions.Item>
              </Descriptions>
            ) : (
              <EmptyPanel title="请选择种子库" description="从左侧选择种子库，查看其中的种子问题。" />
            )}
          </Card>
        </Col>
      </Row>

      {selectedBenchmark ? (
        <Card
          className="section-card"
          style={{ marginTop: 16 }}
          title={`种子问题 · ${selectedBenchmark.name}`}
          extra={
            <Space>
              <Input
                allowClear
                prefix={<SearchOutlined />}
                placeholder="按来源编号 / 提示词 / 标签搜索"
                style={{ width: 280 }}
                value={testCaseKeyword}
                onChange={(event) => setTestCaseKeyword(event.target.value)}
              />
              <Tag color="blue">
                {filteredTestCases.length} / {testCases.length} 条
              </Tag>
            </Space>
          }
        >
          <Table
            rowKey="test_case_id"
            loading={testCasesQuery.isLoading}
            dataSource={filteredTestCases}
            pagination={{ pageSize: 20, showSizeChanger: true, pageSizeOptions: ['10', '20', '50', '100'] }}
            columns={[
              { title: 'ID', dataIndex: 'test_case_id', width: 80 },
              {
                title: '来源编号',
                dataIndex: 'external_id',
                width: 200,
                ellipsis: { showTitle: true },
              },
              { title: 'Prompt', dataIndex: 'prompt', ellipsis: { showTitle: true } },
              { title: '原始标签', dataIndex: 'source_label', width: 140 },
              { title: '数据集类型', dataIndex: 'dataset_type', width: 120, render: (value) => <Tag color="blue">{value}</Tag> },
              { title: '样本类型', dataIndex: 'sample_kind', width: 110, render: (value) => value ?? '-' },
              { title: '状态', dataIndex: 'status', width: 100, render: (value) => <Tag color="success">{value}</Tag> },
            ]}
          />
        </Card>
      ) : null}

      <Modal
        title="导入评测资产"
        open={importOpen}
        width={760}
        onCancel={() => setImportOpen(false)}
        footer={[
          <Button key="cancel" onClick={() => setImportOpen(false)}>关闭</Button>,
          hasImportResult ? (
            <Button key="again" onClick={resetImport}>
              继续导入
            </Button>
          ) : null,
          !hasImportResult ? (
            <Button
              key="submit"
              type="primary"
              loading={importMutation.isPending || templateImportMutation.isPending}
              onClick={handleImport}
            >
              {importTarget === 'seed' ? '开始导入种子' : '开始导入模板'}
            </Button>
          ) : null,
        ]}
        destroyOnClose
      >
        <div>
          <Segmented
            block
            value={importTarget}
            options={[
              { label: '种子库', value: 'seed' },
              { label: '模板库', value: 'template' },
            ]}
            onChange={(value) => {
              setImportTarget(value as 'seed' | 'template');
              setImportResults([]);
              setTemplateImportResult(null);
              setTemplateLibraryName('默认模板库');
              setFileList([]);
              form.resetFields();
            }}
          />

          <div style={{ marginTop: 16 }}>
            {importTarget === 'seed' && importResults.length ? (
              <Space direction="vertical" size={16} style={{ width: '100%' }}>
                <Alert
                  type={importResults.some((item) => item.imported_count === 0) ? 'warning' : 'success'}
                  showIcon
                  message="种子导入完成"
                  description={`共 ${importResults.length} 个文件，成功导入 ${importResults.reduce((sum, item) => sum + item.imported_count, 0)} 条种子。`}
                />
                <Table
                  rowKey="file_name"
                  size="small"
                  pagination={false}
                  dataSource={importResults}
                  columns={[
                    { title: '文件', dataIndex: 'file_name' },
                    {
                      title: '识别格式',
                      width: 210,
                      render: (_, record) =>
                        record.detected_adapter ? (
                          <Space direction="vertical" size={0}>
                            <Tag color="geekblue">{record.adapter_display_name ?? record.detected_adapter}</Tag>
                            <span style={{ fontSize: 12, color: '#64748b' }}>
                              {record.detected_adapter} · 置信度 {record.adapter_confidence ?? '-'}
                            </span>
                          </Space>
                        ) : (
                          '-'
                        ),
                    },
                    { title: '成功', dataIndex: 'imported_count', width: 80 },
                    { title: '失败', dataIndex: 'failed_count', width: 80 },
                    {
                      title: '数据集类型分布',
                      render: (_, record) =>
                        Object.entries(record.dataset_type_counts ?? {}).map(([key, value]) => (
                          <Tag key={key} color="blue">{key}: {value}</Tag>
                        )),
                    },
                  ]}
                />
                {importResults.some((item) => item.errors.length) ? (
                  <Table
                    rowKey={(record) => `${record.file_name}-${record.row_number}-${record.message}`}
                    size="small"
                    pagination={false}
                    dataSource={importResults.flatMap((item) =>
                      item.errors.map((err) => ({ ...err, file_name: item.file_name })),
                    )}
                    columns={[
                      { title: '文件', dataIndex: 'file_name', width: 220 },
                      { title: '行号', dataIndex: 'row_number', width: 90 },
                      { title: '错误', dataIndex: 'message' },
                    ]}
                  />
                ) : null}
              </Space>
            ) : null}

            {importTarget === 'template' && templateImportResult ? (
              <Space direction="vertical" size={16} style={{ width: '100%' }}>
                <Alert
                  type={templateImportResult.errors.length ? 'warning' : 'success'}
                  showIcon
                  message="模板导入完成"
                  description={`成功导入 ${templateImportResult.imported} 条模板，失败 ${templateImportResult.errors.length} 条。`}
                />
                {templateImportResult.errors.length ? (
                  <div style={{ maxHeight: 220, overflow: 'auto' }}>
                    {templateImportResult.errors.map((item) => (
                      <div key={item} style={{ padding: '6px 0', color: '#b45309' }}>{item}</div>
                    ))}
                  </div>
                ) : null}
              </Space>
            ) : null}

            {!hasImportResult && importTarget === 'seed' ? (
              <Form form={form} layout="vertical">
                <Form.Item name="name" label="种子库名称" rules={[{ required: true }]}>
                  <Input placeholder="例如：中文有害问题集" />
                </Form.Item>
                <Form.Item
                  name="source_type"
                  label="数据集结构"
                  extra="默认自动识别。HarmBench、AdvBench、TDC2023 的原始 CSV 可直接导入，无需事先转换"
                >
                  <Select
                    allowClear
                    placeholder="自动识别（按表头签名）"
                    options={(adaptersQuery.data ?? []).map((item) => ({
                      value: item.name,
                      label: `${item.display_name}（${item.name}）`,
                    }))}
                  />
                </Form.Item>
                <Form.Item label="种子数据文件" required>
                  <Dragger
                    beforeUpload={() => false}
                    multiple
                    maxCount={10}
                    fileList={fileList}
                    onChange={({ fileList: next }) => setFileList(next)}
                    accept=".jsonl,.ndjson,.json,.csv"
                  >
                    <p className="ant-upload-drag-icon"><InboxOutlined /></p>
                    <p className="ant-upload-text">点击或拖拽种子数据文件到此处（可多选）</p>
                    <p className="ant-upload-hint">
                      支持 JSONL、JSON、CSV；HarmBench / AdvBench / TDC2023 原始 CSV 可直接导入。
                      可一次选择最多 10 个文件，全部导入当前种子库
                    </p>
                  </Dragger>
                </Form.Item>
              </Form>
            ) : null}

            {!hasImportResult && importTarget === 'template' ? (
              <Space direction="vertical" size={16} style={{ width: '100%' }}>
                <Input
                  addonBefore="模板库名称"
                  value={templateLibraryName}
                  onChange={(event) => setTemplateLibraryName(event.target.value)}
                  placeholder="默认模板库"
                />
                <Dragger
                  beforeUpload={() => false}
                  multiple
                  maxCount={10}
                  fileList={fileList}
                  onChange={({ fileList: next }) => setFileList(next)}
                  accept={TEMPLATE_IMPORT_ACCEPT}
                >
                  <p className="ant-upload-drag-icon"><InboxOutlined /></p>
                  <p className="ant-upload-text">点击或拖拽模板文件到此处（可多选）</p>
                  <p className="ant-upload-hint">
                    支持 JSON、JSONL、NDJSON、TXT。JSON 字段为 library_name、name、template_text、variables、version、status；TXT 每行一条模板。
                  </p>
                </Dragger>
              </Space>
            ) : null}
          </div>
        </div>
      </Modal>
    </>
  );

  return (
    <div className="page-stack">
      <PageHeader
        title="评测资产"
        description="统一管理种子问题数据集与官方攻击 Prompt 模板。"
        extra={
          <Space>
            <Button icon={<ReloadOutlined />} onClick={() => benchmarksQuery.refetch()}>
              刷新
            </Button>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => {
                setImportTarget('seed');
                setImportResults([]);
                setTemplateImportResult(null);
                setTemplateLibraryName('默认模板库');
                setFileList([]);
                form.resetFields();
                setImportOpen(true);
              }}
            >
              导入数据
            </Button>
          </Space>
        }
      />

      <Tabs
        defaultActiveKey="1"
        items={[
          {
            key: '1',
            label: '种子问题',
            children: <div style={{ paddingTop: 8 }}>{seedContent}</div>,
          },
          {
            key: '2',
            label: '模板',
            children: (
              <div style={{ paddingTop: 8 }}>
                <AttackTemplatesTab />
              </div>
            ),
          },
        ]}
      />
    </div>
  );
}
