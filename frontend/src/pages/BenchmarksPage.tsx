import { useMemo, useState } from 'react';
import { InboxOutlined, PlusOutlined, ReloadOutlined } from '@ant-design/icons';
import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Form,
  Input,
  InputNumber,
  List,
  Modal,
  Row,
  Space,
  Table,
  Tag,
  Upload,
  message,
} from 'antd';
import type { UploadFile } from 'antd';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { importBenchmark, listBenchmarks, listBenchmarkVersions, listTestCases } from '../api';
import { EmptyPanel, PageHeader } from '../components/ui';
import type { Benchmark, BenchmarkImportResult, BenchmarkVersion } from '../types/api';
import { formatDateTime } from '../utils/format';

const { Dragger } = Upload;

export function BenchmarksPage() {
  const queryClient = useQueryClient();
  const [selectedBenchmark, setSelectedBenchmark] = useState<Benchmark | null>(null);
  const [selectedVersion, setSelectedVersion] = useState<BenchmarkVersion | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [importResult, setImportResult] = useState<BenchmarkImportResult | null>(null);
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
    mutationFn: importBenchmark,
    onSuccess: (result) => {
      setImportResult(result);
      message.success(`成功导入 ${result.imported_count} 条测试用例`);
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

  const handleImport = () => {
    form
      .validateFields()
      .then((values) => {
        const file = fileList[0]?.originFileObj;
        if (!file) {
          message.warning('请选择数据集文件');
          return;
        }
        const formData = new FormData();
        formData.append('name', values.name);
        formData.append('version', values.version);
        if (values.risk_taxonomy_id) {
          formData.append('risk_taxonomy_id', String(values.risk_taxonomy_id));
        }
        formData.append('file', file);
        importMutation.mutate(formData);
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
                setImportResult(null);
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
                ]}
              />
            ) : (
              <EmptyPanel title="请选择 Benchmark" description="从左侧选择 Benchmark，查看版本和测试用例。" />
            )}
          </Card>
        </Col>
      </Row>

      {selectedVersion ? (
        <Card className="section-card" title={`测试用例 · 版本 ${selectedVersion.version}`} extra={<Tag color="blue">{testCases.length} 条</Tag>}>
          <Table
            rowKey="test_case_id"
            loading={testCasesQuery.isLoading}
            dataSource={testCases}
            pagination={{ pageSize: 10 }}
            columns={[
              { title: 'ID', dataIndex: 'test_case_id', width: 80 },
              { title: '外部 ID', dataIndex: 'external_id', width: 140 },
              { title: 'Prompt', dataIndex: 'prompt', ellipsis: true },
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
          <Button key="submit" type="primary" loading={importMutation.isPending} onClick={handleImport}>
            开始导入
          </Button>,
        ]}
        destroyOnClose
      >
        {importResult ? (
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <Alert
              type={importResult.failed_count ? 'warning' : 'success'}
              showIcon
              message="导入完成"
              description={`成功 ${importResult.imported_count} 条，失败 ${importResult.failed_count} 条，未映射标签 ${importResult.unresolved_labels.length} 个。`}
            />
            <Descriptions column={2} size="small">
              <Descriptions.Item label="Benchmark ID">{importResult.benchmark_id}</Descriptions.Item>
              <Descriptions.Item label="版本 ID">{importResult.benchmark_version_id}</Descriptions.Item>
              <Descriptions.Item label="未映射标签" span={2}>
                {importResult.unresolved_labels.length ? importResult.unresolved_labels.join(', ') : '无'}
              </Descriptions.Item>
            </Descriptions>
            {importResult.errors.length ? (
              <Table
                rowKey={(record) => `${record.row_number}-${record.message}`}
                size="small"
                dataSource={importResult.errors}
                pagination={false}
                columns={[
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
                <Form.Item name="version" label="版本" rules={[{ required: true }]}>
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
                maxCount={1}
                fileList={fileList}
                onChange={({ fileList: next }) => setFileList(next)}
                accept=".jsonl,.ndjson,.json,.csv"
              >
                <p className="ant-upload-drag-icon"><InboxOutlined /></p>
                <p className="ant-upload-text">点击或拖拽数据集文件到此处</p>
                <p className="ant-upload-hint">支持 JSONL、JSON、CSV，默认单文件不超过 100 MB</p>
              </Dragger>
            </Form.Item>
          </Form>
        )}
      </Modal>
    </div>
  );
}
