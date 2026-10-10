import { useMemo, useState } from 'react';
import { DeleteOutlined, InboxOutlined, PlusOutlined, ReloadOutlined, SearchOutlined } from '@ant-design/icons';
import {
  Alert,
  Button,
  Card,
  Col,
  Form,
  Input,
  InputNumber,
  List,
  Modal,
  Popconfirm,
  Row,
  Space,
  Table,
  Tag,
  Upload,
  message,
} from 'antd';
import type { UploadFile } from 'antd';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  deleteBenchmark,
  deleteBenchmarkVersion,
  importBenchmark,
  listBenchmarks,
  listBenchmarkVersions,
  listTestCases,
} from '../api';
import { EmptyPanel, PageHeader } from '../components/ui';
import type { Benchmark, BenchmarkImportResult, BenchmarkVersion } from '../types/api';
import { formatDateTime } from '../utils/format';

const { Dragger } = Upload;

/** 多文件导入时，用文件名生成版本号，例如 harmbench_text_test.jsonl -> harmbench_text_test */
const fileVersionName = (fileName: string) =>
  fileName.replace(/\.[^.]+$/, '').replace(/[^a-zA-Z0-9._-]+/g, '-').slice(0, 60) || 'v1';

export function BenchmarksPage() {
  const queryClient = useQueryClient();
  const [selectedBenchmark, setSelectedBenchmark] = useState<Benchmark | null>(null);
  const [selectedVersion, setSelectedVersion] = useState<BenchmarkVersion | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [importResults, setImportResults] = useState<Array<BenchmarkImportResult & { file_name: string }>>([]);
  const [testCaseKeyword, setTestCaseKeyword] = useState('');
  const [form] = Form.useForm();

  const benchmarksQuery = useQuery({ queryKey: ['benchmarks'], queryFn: () => listBenchmarks({ page_size: 200 }) });
  const versionsQuery = useQuery({
    queryKey: ['benchmark-versions', selectedBenchmark?.benchmark_id],
    queryFn: () => listBenchmarkVersions(selectedBenchmark!.benchmark_id),
    enabled: Boolean(selectedBenchmark?.benchmark_id),
  });
  const testCasesQuery = useQuery({
    queryKey: ['test-cases', selectedVersion?.benchmark_version_id],
    queryFn: () => listTestCases({ benchmark_version_id: selectedVersion!.benchmark_version_id, page_size: 200 }),
    enabled: Boolean(selectedVersion?.benchmark_version_id),
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
            benchmark_version_id: 0,
            imported_count: 0,
            failed_count: 1,
            unresolved_labels: [],
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
        message.success(`${results.length} 个文件导入完成，共 ${totalImported} 条测试用例`);
      } else {
        message.warning(`${results.length} 个文件中成功 ${succeeded} 个，请查看导入结果`);
      }
      queryClient.invalidateQueries({ queryKey: ['benchmarks'] });
      queryClient.invalidateQueries({ queryKey: ['benchmark-versions'] });
      queryClient.invalidateQueries({ queryKey: ['test-cases'] });
    },
  });

  const deleteBenchmarkMutation = useMutation({
    mutationFn: deleteBenchmark,
    onSuccess: (summary) => {
      message.success(
        `已删除 ${summary.deleted_versions} 个版本、${summary.deleted_test_cases} 条测试用例`,
      );
      setSelectedBenchmark(null);
      setSelectedVersion(null);
      queryClient.invalidateQueries({ queryKey: ['benchmarks'] });
      queryClient.invalidateQueries({ queryKey: ['benchmark-versions'] });
      queryClient.invalidateQueries({ queryKey: ['test-cases'] });
    },
    onError: (error: Error) => message.error(error.message),
  });

  const deleteVersionMutation = useMutation({
    mutationFn: deleteBenchmarkVersion,
    onSuccess: (summary) => {
      message.success(
        `已删除 ${summary.deleted_test_cases} 条测试用例、${summary.deleted_mappings} 条风险映射`,
      );
      setSelectedVersion(null);
      queryClient.invalidateQueries({ queryKey: ['benchmarks'] });
      queryClient.invalidateQueries({ queryKey: ['benchmark-versions'] });
      queryClient.invalidateQueries({ queryKey: ['test-cases'] });
    },
    onError: (error: Error) => message.error(error.message),
  });

  const benchmarks = benchmarksQuery.data?.items ?? [];
  const versions = versionsQuery.data?.items ?? [];
  const testCases = testCasesQuery.data?.items ?? [];

  const selectedBenchmarkName = useMemo(() => selectedBenchmark?.name ?? '未选择 Benchmark', [selectedBenchmark]);

  /** 用例表格的本地筛选：支持按外部 ID、提示词正文、原始标签和数字 ID 查找。 */
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
    setFileList([]);
    form.resetFields();
  };

  const handleImport = () => {
    const files = fileList
      .map((item) => item.originFileObj)
      .filter((item): item is NonNullable<UploadFile['originFileObj']> => Boolean(item));
    if (!files.length) {
      message.warning('请选择数据集文件');
      return;
    }
    form
      .validateFields()
      .then((values) => {
        const benchmarkName = String(values.name ?? '').trim();
        if (!benchmarkName || benchmarkName === 'undefined') {
          message.error('请填写有效的 Benchmark 名称');
          return;
        }
        const payloads = files.map((file) => {
          const formData = new FormData();
          formData.append('name', benchmarkName);
          // 单文件使用表单里的版本号；多文件按文件名自动生成版本号
          formData.append('version', files.length === 1 ? values.version : fileVersionName(file.name));
          if (values.risk_taxonomy_id) {
            formData.append('risk_taxonomy_id', String(values.risk_taxonomy_id));
          }
          formData.append('file', file);
          return { formData, file_name: file.name };
        });
        importMutation.mutate(payloads);
      })
      .catch(() => undefined);
  };

  return (
    <div className="page-stack">
      <PageHeader
        title="Benchmark 管理"
        description="导入 JSONL、JSON、CSV 数据集，自动写入 Benchmark 版本、测试用例和风险映射。"
        extra={
          <Space>
            <Button icon={<ReloadOutlined />} onClick={() => benchmarksQuery.refetch()}>
              刷新
            </Button>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => {
                setImportResults([]);
                setFileList([]);
                form.resetFields();
                setImportOpen(true);
              }}
            >
              导入 Benchmark
            </Button>
          </Space>
        }
      />

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={8}>
          <Card className="section-card" title="Benchmark 列表">
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
                      setSelectedVersion(null);
                    }}
                  >
                    <List.Item.Meta
                      title={item.name}
                      description={
                        <Space>
                          <Tag color="blue">{item.slug}</Tag>
                          <Tag color={item.status === 'active' ? 'success' : 'default'}>{item.status}</Tag>
                        </Space>
                      }
                    />
                    <Popconfirm
                      title="删除该 Benchmark？"
                      description="将同时删除它的全部版本、测试用例和风险映射，无法恢复。"
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
                title="暂无 Benchmark"
                description="导入第一个 Benchmark 数据集，系统会自动创建版本和标准测试用例。"
                action={<Button type="primary" icon={<PlusOutlined />} onClick={() => setImportOpen(true)}>导入 Benchmark</Button>}
              />
            )}
          </Card>
        </Col>

        <Col xs={24} xl={16}>
          <Card className="section-card" title={`${selectedBenchmarkName} · 版本列表`}>
            {selectedBenchmark ? (
              <Table<BenchmarkVersion>
                rowKey="benchmark_version_id"
                loading={versionsQuery.isLoading}
                dataSource={versions}
                pagination={false}
                onRow={(record) => ({ onClick: () => setSelectedVersion(record) })}
                columns={[
                  { title: '版本 ID', dataIndex: 'benchmark_version_id', width: 100 },
                  { title: '版本', dataIndex: 'version' },
                  { title: '用例数', dataIndex: 'case_count' },
                  { title: '校验和', dataIndex: 'checksum', render: (value) => <code>{String(value ?? '').slice(0, 16)}…</code> },
                  { title: '状态', dataIndex: 'status', render: (value) => <Tag color={value === 'ready' ? 'success' : 'processing'}>{value}</Tag> },
                  { title: '导入时间', dataIndex: 'imported_at', render: formatDateTime },
                  {
                    title: '操作',
                    width: 80,
                    render: (_, record) => (
                      <Popconfirm
                        title="删除该版本？"
                        description="将删除该版本的全部测试用例和风险映射，无法恢复。"
                        okText="删除"
                        cancelText="取消"
                        okButtonProps={{ danger: true, loading: deleteVersionMutation.isPending }}
                        onConfirm={() => deleteVersionMutation.mutate(record.benchmark_version_id)}
                      >
                        <Button
                          type="text"
                          danger
                          size="small"
                          icon={<DeleteOutlined />}
                          onClick={(event) => event.stopPropagation()}
                        />
                      </Popconfirm>
                    ),
                  },
                ]}
              />
            ) : (
              <EmptyPanel title="请选择 Benchmark" description="从左侧选择 Benchmark，查看版本和测试用例。" />
            )}
          </Card>
        </Col>
      </Row>

      {selectedVersion ? (
        <Card
          className="section-card"
          title={`测试用例 · 版本 ${selectedVersion.version}`}
          extra={
            <Space>
              <Input
                allowClear
                prefix={<SearchOutlined />}
                placeholder="按外部 ID / 提示词 / 标签搜索"
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
              { title: '外部 ID', dataIndex: 'external_id', width: 140 },
              { title: 'Prompt', dataIndex: 'prompt', ellipsis: { showTitle: true } },
              { title: '原始标签', dataIndex: 'source_label', width: 140 },
              {
                title: '风险类别',
                width: 180,
                render: (_, record) => (
                  <Space wrap>
                    {(record.risk_categories ?? []).map((item) => (
                      <Tag key={item.code} color="purple">{item.code}</Tag>
                    ))}
                  </Space>
                ),
              },
              { title: '状态', dataIndex: 'status', width: 100, render: (value) => <Tag color="success">{value}</Tag> },
            ]}
          />
        </Card>
      ) : null}

      <Modal
        title="导入 Benchmark"
        open={importOpen}
        width={760}
        onCancel={() => setImportOpen(false)}
        footer={[
          <Button key="cancel" onClick={() => setImportOpen(false)}>关闭</Button>,
          importResults.length ? (
            <Button key="again" onClick={resetImport}>
              继续导入
            </Button>
          ) : null,
          <Button key="submit" type="primary" loading={importMutation.isPending} onClick={handleImport}>
            开始导入
          </Button>,
        ]}
        destroyOnClose
      >
        {importResults.length ? (
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <Alert
              type={importResults.some((item) => item.imported_count === 0) ? 'warning' : 'success'}
              showIcon
              message="导入完成"
              description={`共 ${importResults.length} 个文件，成功导入 ${importResults.reduce((sum, item) => sum + item.imported_count, 0)} 条用例。`}
            />
            <Table
              rowKey="file_name"
              size="small"
              pagination={false}
              dataSource={importResults}
              columns={[
                { title: '文件', dataIndex: 'file_name' },
                { title: '版本 ID', dataIndex: 'benchmark_version_id', width: 90 },
                { title: '成功', dataIndex: 'imported_count', width: 80 },
                { title: '失败', dataIndex: 'failed_count', width: 80 },
                {
                  title: '未映射标签',
                  render: (_, record) =>
                    record.unresolved_labels.length ? (
                      <Space wrap>
                        {record.unresolved_labels.map((label) => (
                          <Tag key={label} color="warning">{label}</Tag>
                        ))}
                      </Space>
                    ) : (
                      <Tag color="success">无</Tag>
                    ),
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
        ) : (
          <Form form={form} layout="vertical" initialValues={{ risk_taxonomy_id: 1 }}>
            <Row gutter={16}>
              <Col span={12}>
                <Form.Item name="name" label="Benchmark 名称" rules={[{ required: true }]}>
                  <Input placeholder="例如：AdvBench" />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item
                  name="version"
                  label="版本"
                  rules={fileList.length > 1 ? [] : [{ required: true }]}
                  extra={fileList.length > 1 ? '已选择多个文件，将按各自文件名自动生成版本号' : undefined}
                >
                  <Input placeholder="v1" />
                </Form.Item>
              </Col>
            </Row>
            <Form.Item name="risk_taxonomy_id" label="风险体系 ID">
              <InputNumber min={1} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item label="数据集文件" required>
              <Dragger
                beforeUpload={() => false}
                multiple
                maxCount={10}
                fileList={fileList}
                onChange={({ fileList: next }) => setFileList(next)}
                accept=".jsonl,.ndjson,.json,.csv"
              >
                <p className="ant-upload-drag-icon"><InboxOutlined /></p>
                <p className="ant-upload-text">点击或拖拽数据集文件到此处（可多选）</p>
                <p className="ant-upload-hint">支持 JSONL、JSON、CSV，可一次选择最多 10 个文件，每个文件导入为一个独立版本</p>
              </Dragger>
            </Form.Item>
          </Form>
        )}
      </Modal>
    </div>
  );
}
