import { useState } from 'react';
import { CheckCircleOutlined, EyeOutlined, ReloadOutlined } from '@ant-design/icons';
import { Alert, Button, Card, Descriptions, Form, Input, InputNumber, Modal, Select, Space, Table, Tabs, Tag, message } from 'antd';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { createManualReview, getManualReview, listManualReviews, listRiskCategories, listRiskTaxonomies } from '../api';
import { EmptyPanel, PageHeader } from '../components/ui';
import type { ManualReview, ManualReviewDetail, RiskCategory } from '../types/api';
import { formatDateTime, formatPercent, formatScore } from '../utils/format';

function flattenCategories(nodes: RiskCategory[], prefix = ''): Array<{ label: string; value: number }> {
  const options: Array<{ label: string; value: number }> = [];
  for (const node of nodes) {
    options.push({ label: `${prefix}${node.code} · ${node.name}`, value: node.risk_category_id });
    if (node.children?.length) options.push(...flattenCategories(node.children, `${prefix}— `));
  }
  return options;
}

export function ReviewsPage() {
  const queryClient = useQueryClient();
  const [detailOpen, setDetailOpen] = useState(false);
  const [detail, setDetail] = useState<ManualReviewDetail | null>(null);
  const [form] = Form.useForm();

  const reviewsQuery = useQuery({ queryKey: ['manual-reviews'], queryFn: () => listManualReviews({ page_size: 200 }) });
  const categoriesQuery = useQuery({
    queryKey: ['manual-review-category-options'],
    queryFn: async () => {
      const taxonomies = await listRiskTaxonomies({ page_size: 200 });
      const nested = await Promise.all(taxonomies.items.map((item) => listRiskCategories(item.risk_taxonomy_id)));
      return nested.flat().flatMap((item) => flattenCategories([item]));
    },
  });

  const detailMutation = useMutation({
    mutationFn: getManualReview,
    onSuccess: (data) => {
      setDetail(data);
      setDetailOpen(true);
      form.setFieldsValue({
        decision: 'confirmed',
        corrected_category_id: data.corrected_category_id,
        corrected_score: data.corrected_score,
        comment: data.comment,
      });
    },
    onError: (error: Error) => message.error(error.message),
  });

  const submitMutation = useMutation({
    mutationFn: (values: Record<string, unknown>) =>
      createManualReview({
        task_attempt_id: detail!.task_attempt_id,
        trigger_reason: detail!.trigger_reason,
        decision: values.decision,
        corrected_category_id: values.corrected_category_id ?? null,
        corrected_score: values.corrected_score ?? null,
        comment: values.comment,
      }),
    onSuccess: () => {
      message.success('复核结果已保存');
      setDetailOpen(false);
      setDetail(null);
      form.resetFields();
      queryClient.invalidateQueries({ queryKey: ['manual-reviews'] });
    },
    onError: (error: Error) => message.error(error.message),
  });

  const reviews = reviewsQuery.data?.items ?? [];
  const pendingReviews = reviews.filter((item) => item.status === 'pending' || item.status === 'in_review');
  const historyReviews = reviews.filter((item) => item.status === 'resolved' || item.status === 'rejected');
  const categoryOptions = categoriesQuery.data ?? [];

  const renderTable = (data: ManualReview[], showDecision = false) => (
    <Table<ManualReview>
      rowKey="review_id"
      loading={reviewsQuery.isLoading}
      dataSource={data}
      pagination={{ pageSize: 10 }}
      columns={[
        { title: '复核 ID', dataIndex: 'review_id', width: 100 },
        { title: '尝试 ID', dataIndex: 'task_attempt_id', width: 100 },
        { title: '触发原因', dataIndex: 'trigger_reason', render: (value) => <Tag color="orange">{value}</Tag> },
        { title: '状态', dataIndex: 'status', width: 120, render: (value) => <Tag color={value === 'pending' ? 'warning' : 'success'}>{value}</Tag> },
        ...(showDecision
          ? [
              { title: '复核结论', dataIndex: 'decision', width: 120 },
              { title: '修正分', dataIndex: 'corrected_score', width: 100, render: formatScore },
              { title: '复核人', dataIndex: 'reviewer', width: 120 },
              { title: '复核时间', dataIndex: 'reviewed_at', width: 180, render: formatDateTime },
            ]
          : []),
        {
          title: '操作',
          width: 120,
          render: (_, record) => (
            <Button type="link" icon={<EyeOutlined />} loading={detailMutation.isPending} onClick={() => detailMutation.mutate(record.review_id)}>
              详情
            </Button>
          ),
        },
      ]}
    />
  );

  return (
    <div className="page-stack">
      <PageHeader
        title="人工复核"
        description="处理低可信度、规则冲突、边界分数和多 Judge 分歧结果，并修正风险类别与风险分。"
        extra={<Button icon={<ReloadOutlined />} onClick={() => reviewsQuery.refetch()}>刷新</Button>}
      />

      <Tabs
        items={[
          {
            key: 'queue',
            label: `待复核队列（${pendingReviews.length}）`,
            children: pendingReviews.length ? renderTable(pendingReviews) : <EmptyPanel title="暂无待复核结果" description="当 Judge 可信度不足或规则冲突时，系统会自动创建复核记录。" />,
          },
          {
            key: 'history',
            label: `复核历史（${historyReviews.length}）`,
            children: historyReviews.length ? renderTable(historyReviews, true) : <EmptyPanel title="暂无复核历史" description="完成复核后，记录会显示在这里。" />,
          },
        ]}
      />

      <Modal
        title={`复核详情 · #${detail?.review_id ?? ''}`}
        open={detailOpen}
        width={880}
        onCancel={() => setDetailOpen(false)}
        footer={null}
        destroyOnClose
      >
        {detail ? (
          <Space direction="vertical" size={18} style={{ width: '100%' }}>
            <Alert
              type="warning"
              showIcon
              message={`触发原因：${detail.trigger_reason}`}
              description="请结合模型输出、Judge 判断、规则命中和风险量化结果给出复核结论。"
            />
            <Descriptions column={2} size="small" bordered>
              <Descriptions.Item label="任务 ID">{detail.task_id ?? '-'}</Descriptions.Item>
              <Descriptions.Item label="尝试 ID">{detail.task_attempt_id}</Descriptions.Item>
              <Descriptions.Item label="用例 ID">{detail.external_id ?? detail.test_case_id ?? '-'}</Descriptions.Item>
              <Descriptions.Item label="Judge 判断">
                {detail.judge_verdict ?? '-'} / 置信度 {formatPercent(detail.judge_confidence)} / 可信度 {formatPercent(detail.judge_trust_score)}
              </Descriptions.Item>
              <Descriptions.Item label="规则命中">{detail.rule_hits}，最高严重度 {detail.rule_highest_severity ?? '-'}</Descriptions.Item>
              <Descriptions.Item label="原始风险">
                {formatScore(detail.original_risk_score)} / {detail.original_risk_level ?? '-'}
              </Descriptions.Item>
            </Descriptions>

            <Card size="small" title="测试 Prompt">
              <pre className="code-block">{detail.prompt ?? '-'}</pre>
            </Card>
            <Card size="small" title="模型输出">
              <pre className="code-block" style={{ maxHeight: 220, overflow: 'auto' }}>{detail.model_output ?? '-'}</pre>
            </Card>

            <Form form={form} layout="vertical" onFinish={(values) => submitMutation.mutate(values)}>
              <Form.Item name="decision" label="复核结论" rules={[{ required: true }]}>
                <Select
                  options={[
                    { value: 'confirmed', label: '确认原结果' },
                    { value: 'override', label: '修正原结果' },
                    { value: 'rejected', label: '驳回复核' },
                    { value: 'unresolved', label: '暂不处理' },
                  ]}
                />
              </Form.Item>
              <Form.Item name="corrected_category_id" label="修正风险类别">
                <Select allowClear showSearch options={categoryOptions} placeholder="选择统一风险类别" />
              </Form.Item>
              <Form.Item name="corrected_score" label="修正风险分" rules={[{ required: true, message: '修正风险分必填' }]}>
                <InputNumber min={0} max={100} style={{ width: '100%' }} />
              </Form.Item>
              <Form.Item name="comment" label="复核意见">
                <Input.TextArea rows={4} placeholder="说明复核依据和修正原因" />
              </Form.Item>
              <Space>
                <Button onClick={() => setDetailOpen(false)}>取消</Button>
                <Button type="primary" icon={<CheckCircleOutlined />} loading={submitMutation.isPending} onClick={() => form.submit()}>
                  提交复核
                </Button>
              </Space>
            </Form>
          </Space>
        ) : null}
      </Modal>
    </div>
  );
}
