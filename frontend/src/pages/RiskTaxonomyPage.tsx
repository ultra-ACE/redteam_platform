import { useEffect, useMemo, useState } from 'react';
import { BranchesOutlined, PlusOutlined, SaveOutlined } from '@ant-design/icons';
import { Button, Card, Col, Form, Input, InputNumber, Modal, Progress, Row, Select, Space, Switch, Table, Tag, Tree, message } from 'antd';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  batchUpsertRiskMappings,
  createRiskCategory,
  createRiskTaxonomy,
  getRiskMappingStatus,
  listBenchmarkVersions,
  listBenchmarks,
  listRiskCategories,
  listRiskTaxonomies,
} from '../api';
import { EmptyPanel, PageHeader } from '../components/ui';
import type { Benchmark, BenchmarkVersion, RiskCategory, RiskTaxonomy } from '../types/api';

function flattenCategories(nodes: RiskCategory[], prefix = ''): Array<{ label: string; value: number }> {
  const options: Array<{ label: string; value: number }> = [];
  for (const node of nodes) {
    const label = `${prefix}${node.code} · ${node.name}`;
    options.push({ label, value: node.risk_category_id });
    if (node.children?.length) {
      options.push(...flattenCategories(node.children, `${prefix}— `));
    }
  }
  return options;
}

function toTreeData(nodes: RiskCategory[]): Array<Record<string, unknown>> {
  return nodes.map((node) => ({
    key: node.risk_category_id,
    title: (
      <Space>
        <span style={{ fontWeight: 600 }}>{node.name}</span>
        <Tag color="blue">{node.code}</Tag>
        <Tag color="purple">严重度 {node.severity_weight}</Tag>
      </Space>
    ),
    children: toTreeData(node.children ?? []),
  }));
}

export function RiskTaxonomyPage() {
  const queryClient = useQueryClient();
  const [selectedTaxonomy, setSelectedTaxonomy] = useState<RiskTaxonomy | null>(null);
  const [selectedBenchmark, setSelectedBenchmark] = useState<Benchmark | null>(null);
  const [selectedVersion, setSelectedVersion] = useState<BenchmarkVersion | null>(null);
  const [mappingValues, setMappingValues] = useState<Record<string, number>>({});
  const [taxonomyOpen, setTaxonomyOpen] = useState(false);
  const [categoryOpen, setCategoryOpen] = useState(false);
  const [taxonomyForm] = Form.useForm();
  const [categoryForm] = Form.useForm();

  const taxonomiesQuery = useQuery({ queryKey: ['risk-taxonomies'], queryFn: () => listRiskTaxonomies({ page_size: 200 }) });
  const categoriesQuery = useQuery({
    queryKey: ['risk-categories', selectedTaxonomy?.risk_taxonomy_id],
    queryFn: () => listRiskCategories(selectedTaxonomy!.risk_taxonomy_id),
    enabled: Boolean(selectedTaxonomy?.risk_taxonomy_id),
  });
  const benchmarksQuery = useQuery({ queryKey: ['benchmarks', 'risk-mapping'], queryFn: () => listBenchmarks({ page_size: 200 }) });
  const versionsQuery = useQuery({
    queryKey: ['benchmark-versions', 'risk-mapping', selectedBenchmark?.benchmark_id],
    queryFn: () => listBenchmarkVersions(selectedBenchmark!.benchmark_id),
    enabled: Boolean(selectedBenchmark?.benchmark_id),
  });
  const mappingStatusQuery = useQuery({
    queryKey: ['risk-mapping-status', selectedVersion?.benchmark_version_id],
    queryFn: () => getRiskMappingStatus(selectedVersion!.benchmark_version_id),
    enabled: Boolean(selectedVersion?.benchmark_version_id),
  });

  useEffect(() => {
    const taxonomies = taxonomiesQuery.data?.items ?? [];
    if (!selectedTaxonomy && taxonomies.length) {
      setSelectedTaxonomy(taxonomies[0]);
    }
  }, [selectedTaxonomy, taxonomiesQuery.data]);

  useEffect(() => {
    if (mappingStatusQuery.data) {
      const next: Record<string, number> = {};
      for (const item of mappingStatusQuery.data.items) {
        if (item.mapped_category_id) next[item.raw_label] = item.mapped_category_id;
      }
      setMappingValues(next);
    }
  }, [mappingStatusQuery.data]);

  const createTaxonomyMutation = useMutation({
    mutationFn: createRiskTaxonomy,
    onSuccess: (taxonomy) => {
      message.success('风险体系已创建');
      setTaxonomyOpen(false);
      taxonomyForm.resetFields();
      setSelectedTaxonomy(taxonomy);
      queryClient.invalidateQueries({ queryKey: ['risk-taxonomies'] });
    },
    onError: (error: Error) => message.error(error.message),
  });

  const createCategoryMutation = useMutation({
    mutationFn: (values: Record<string, unknown>) => createRiskCategory(selectedTaxonomy!.risk_taxonomy_id, values),
    onSuccess: () => {
      message.success('风险分类已创建');
      setCategoryOpen(false);
      categoryForm.resetFields();
      queryClient.invalidateQueries({ queryKey: ['risk-categories'] });
    },
    onError: (error: Error) => message.error(error.message),
  });

  const saveMappingMutation = useMutation({
    mutationFn: () => {
      const mappings = (mappingStatusQuery.data?.items ?? [])
        .filter((item) => mappingValues[item.raw_label])
        .map((item) => ({
          raw_label: item.raw_label,
          risk_category_id: mappingValues[item.raw_label],
          mapping_type: 'manual',
          confidence: 1.0,
        }));
      return batchUpsertRiskMappings(selectedVersion!.benchmark_version_id, mappings);
    },
    onSuccess: (result) => {
      message.success(`映射已保存，剩余未映射 ${result.remaining_unresolved_count} 个`);
      queryClient.invalidateQueries({ queryKey: ['risk-mapping-status'] });
    },
    onError: (error: Error) => message.error(error.message),
  });

  const categoryOptions = useMemo(
    () => flattenCategories(categoriesQuery.data ?? []),
    [categoriesQuery.data],
  );

  const taxonomies = taxonomiesQuery.data?.items ?? [];
  const mappingStatus = mappingStatusQuery.data;

  return (
    <div className="page-stack">
      <PageHeader
        title="风险分类与映射"
        description="维护统一风险分类树，把异构 Benchmark 原始标签映射到统一风险类别。"
        extra={
          <Space>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setTaxonomyOpen(true)}>
              新建风险体系
            </Button>
          </Space>
        }
      />

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={7}>
          <Card className="section-card" title="风险体系">
            {taxonomies.length ? (
              <Space direction="vertical" style={{ width: '100%' }}>
                {taxonomies.map((item) => (
                  <Card
                    key={item.risk_taxonomy_id}
                    size="small"
                    hoverable
                    onClick={() => setSelectedTaxonomy(item)}
                    style={{ borderColor: selectedTaxonomy?.risk_taxonomy_id === item.risk_taxonomy_id ? '#4f6ef7' : undefined }}
                  >
                    <Space direction="vertical" size={4}>
                      <Space>
                        <span style={{ fontWeight: 700 }}>{item.name}</span>
                        <Tag color="blue">{item.version}</Tag>
                        {item.is_default ? <Tag color="purple">默认</Tag> : null}
                      </Space>
                      <span style={{ color: '#94a3b8', fontSize: 12 }}>{item.description || '暂无说明'}</span>
                    </Space>
                  </Card>
                ))}
              </Space>
            ) : (
              <EmptyPanel title="暂无风险体系" description="创建第一个统一风险分类体系。" />
            )}
          </Card>
        </Col>

        <Col xs={24} xl={9}>
          <Card
            className="section-card"
            title={selectedTaxonomy ? `${selectedTaxonomy.name} · 分类树` : '风险分类树'}
            extra={
              selectedTaxonomy ? (
                <Button type="primary" icon={<PlusOutlined />} onClick={() => setCategoryOpen(true)}>
                  新建分类
                </Button>
              ) : null
            }
          >
            {selectedTaxonomy ? (
              categoriesQuery.data?.length ? (
                <Tree showLine defaultExpandAll treeData={toTreeData(categoriesQuery.data)} />
              ) : (
                <EmptyPanel title="暂无风险分类" description="为当前风险体系创建分类节点。" action={<Button type="primary" icon={<BranchesOutlined />} onClick={() => setCategoryOpen(true)}>新建分类</Button>} />
              )
            ) : (
              <EmptyPanel title="请选择风险体系" description="从左侧选择风险体系，查看分类树。" />
            )}
          </Card>
        </Col>

        <Col xs={24} xl={8}>
          <Card className="section-card" title="映射进度">
            <Space direction="vertical" size={16} style={{ width: '100%' }}>
              <Select
                placeholder="选择 Benchmark"
                value={selectedBenchmark?.benchmark_id}
                onChange={(value) => {
                  const benchmark = benchmarksQuery.data?.items.find((item) => item.benchmark_id === value) ?? null;
                  setSelectedBenchmark(benchmark);
                  setSelectedVersion(null);
                }}
                options={(benchmarksQuery.data?.items ?? []).map((item) => ({ value: item.benchmark_id, label: item.name }))}
              />
              <Select
                placeholder="选择 Benchmark 版本"
                value={selectedVersion?.benchmark_version_id}
                disabled={!selectedBenchmark}
                onChange={(value) => {
                  const version = versionsQuery.data?.items.find((item) => item.benchmark_version_id === value) ?? null;
                  setSelectedVersion(version);
                }}
                options={(versionsQuery.data?.items ?? []).map((item) => ({ value: item.benchmark_version_id, label: `${item.version} · ${item.case_count} 条` }))}
              />
              {mappingStatus ? (
                <>
                  <Progress percent={Math.round(mappingStatus.mapping_rate * 100)} strokeColor={{ from: '#4f6ef7', to: '#22c55e' }} />
                  <Space size={20}>
                    <span>标签总数：{mappingStatus.total_labels}</span>
                    <span>已映射：{mappingStatus.mapped_labels}</span>
                    <span>未映射：{mappingStatus.unresolved_labels.length}</span>
                  </Space>
                  <Button type="primary" icon={<SaveOutlined />} loading={saveMappingMutation.isPending} onClick={() => saveMappingMutation.mutate()}>
                    保存映射
                  </Button>
                </>
              ) : (
                <div style={{ color: '#94a3b8' }}>选择 Benchmark 版本后查看映射进度。</div>
              )}
            </Space>
          </Card>
        </Col>
      </Row>

      <Card className="section-card" title="原始标签映射" extra={mappingStatus ? <Tag color={mappingStatus.unresolved_labels.length ? 'warning' : 'success'}>{mappingStatus.unresolved_labels.length ? '存在未映射标签' : '全部已映射'}</Tag> : null}>
        <Table
          rowKey="raw_label"
          loading={mappingStatusQuery.isLoading}
          dataSource={mappingStatus?.items ?? []}
          pagination={{ pageSize: 10 }}
          columns={[
            { title: '原始标签', dataIndex: 'raw_label' },
            { title: '用例数量', dataIndex: 'count', width: 110 },
            {
              title: '当前状态',
              width: 120,
              render: (_, record) => (
                <Tag color={record.status === 'mapped' ? 'success' : 'warning'}>
                  {record.status === 'mapped' ? '已映射' : '未映射'}
                </Tag>
              ),
            },
            {
              title: '统一风险类别',
              render: (_, record) => (
                <Select
                  showSearch
                  allowClear
                  placeholder="选择风险类别"
                  value={mappingValues[record.raw_label]}
                  onChange={(value) =>
                    setMappingValues((current) => ({
                      ...current,
                      [record.raw_label]: value,
                    }))
                  }
                  options={categoryOptions}
                  style={{ minWidth: 260 }}
                />
              ),
            },
          ]}
        />
      </Card>

      <Modal title="新建风险体系" open={taxonomyOpen} onCancel={() => setTaxonomyOpen(false)} onOk={() => taxonomyForm.submit()} confirmLoading={createTaxonomyMutation.isPending}>
        <Form form={taxonomyForm} layout="vertical" initialValues={{ version: 'v1', is_default: false }} onFinish={(values) => createTaxonomyMutation.mutate(values)}>
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input placeholder="统一安全风险体系" />
          </Form.Item>
          <Form.Item name="version" label="版本" rules={[{ required: true }]}>
            <Input placeholder="v1" />
          </Form.Item>
          <Form.Item name="description" label="说明">
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item name="is_default" label="设为默认" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>

      <Modal title="新建风险分类" open={categoryOpen} onCancel={() => setCategoryOpen(false)} onOk={() => categoryForm.submit()} confirmLoading={createCategoryMutation.isPending}>
        <Form form={categoryForm} layout="vertical" initialValues={{ severity_weight: 50, sort_order: 0 }} onFinish={(values) => createCategoryMutation.mutate(values)}>
          <Form.Item name="code" label="风险编码" rules={[{ required: true }]}>
            <Input placeholder="harmful.violence" />
          </Form.Item>
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input placeholder="暴力内容" />
          </Form.Item>
          <Form.Item name="parent_id" label="父分类">
            <Select allowClear options={categoryOptions} placeholder="不选表示一级分类" />
          </Form.Item>
          <Form.Item name="severity_weight" label="严重度权重">
            <InputNumber min={0} max={100} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="definition" label="定义">
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
