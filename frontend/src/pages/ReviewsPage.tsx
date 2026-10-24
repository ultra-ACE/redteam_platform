import { useState } from 'react';
import { CheckCircleOutlined, EyeOutlined, ReloadOutlined, SearchOutlined, ToolOutlined } from '@ant-design/icons';
import { Alert, Button, Card, Descriptions, Form, Input, Modal, Select, Space, Table, Tabs, Tag, message } from 'antd';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { backfillManualReviews, createManualReview, getManualReview, listManualReviews, listTasks } from '../api';
import { EmptyPanel, PageHeader } from '../components/ui';
import type { ManualReview, ManualReviewDetail } from '../types/api';
import { formatDateTime, formatPercent, shortenId } from '../utils/format';

export function ReviewsPage() {
  const queryClient = useQueryClient();
  const [detailOpen, setDetailOpen] = useState(false);
  const [detail, setDetail] = useState<ManualReviewDetail | null>(null);
  const [keyword, setKeyword] = useState('');
  const [selectedTaskId, setSelectedTaskId] = useState<number | null>(null);
  const [form] = Form.useForm();

  const tasksQuery = useQuery({
    queryKey: ['manual-review-tasks'],
    queryFn: () => listTasks({ page: 1, page_size: 200 }),
  });
  const reviewsQuery = useQuery({
    queryKey: ['manual-reviews', selectedTaskId ?? 'all'],
    queryFn: () =>
      listManualReviews({
        page_size: 2000,
        task_id: selectedTaskId ?? undefined,
      }),
  });
  const pendingSummaryQuery = useQuery({
    queryKey: ['manual-reviews', 'pending-summary', selectedTaskId ?? 'all'],
    queryFn: () =>
      listManualReviews({
        page: 1,
        page_size: 1,
        status: 'pending',
        task_id: selectedTaskId ?? undefined,
      }),
  });
  const backfillMutation = useMutation({
    mutationFn: (taskId?: number) => backfillManualReviews(taskId),
    onSuccess: (result) => {
      message.success(`已扫描 ${result.scanned} 个尝试，补建 ${result.created} 条复核记录`);
      queryClient.invalidateQueries({ queryKey: ['manual-reviews'] });
    },
    onError: (error: Error) => message.error(error.message),
  });
  const detailMutation = useMutation({
    mutationFn: getManualReview,
    onSuccess: (data) => {
      setDetail(data);
      setDetailOpen(true);
      form.setFieldsValue({
        decision: 'confirmed',
        corrected_verdict: data.corrected_verdict,
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
        corrected_verdict: values.corrected_verdict ?? null,
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
  const tasks = tasksQuery.data?.items ?? [];
  const tasksById = new Map(tasks.map((task) => [task.task_id, task]));
  const selectedTask = selectedTaskId ? tasksById.get(selectedTaskId) : undefined;
  const normalizedKeyword = keyword.trim().toLowerCase();
  const matchedReviews = normalizedKeyword
    ? reviews.filter((item) =>
        [
          String(item.case_no ?? ''),
          item.external_id,
          String(item.round_no ?? item.attempt_no ?? ''),
          String(item.task_id ?? ''),
          tasksById.get(item.task_id ?? -1)?.name,
          item.trigger_reason,
          item.status,
          item.reviewer,
        ].some((value) => (value ?? '').toLowerCase().includes(normalizedKeyword)),
      )
    : reviews;
  const pendingReviews = matchedReviews.filter((item) => item.status === 'pending' || item.status === 'in_review');
  const historyReviews = matchedReviews.filter((item) => item.status === 'resolved' || item.status === 'rejected');
  const pendingTotal = pendingSummaryQuery.data?.total ?? pendingReviews.length;
  const renderTable = (data: ManualReview[], showDecision = false) => (
    <Table<ManualReview>
      rowKey="review_id"
      loading={reviewsQuery.isLoading}
      dataSource={data}
      pagination={{ pageSize: 10 }}
      columns={[
        {
          title: '评测任务',
          dataIndex: 'task_id',
          width: 220,
          ellipsis: { showTitle: true },
          render: (value?: number | null) => {
            if (!value) return '-';
            const task = tasksById.get(value);
            return task ? `${task.name} · #${task.task_id}` : `任务 #${value}`;
          },
        },
        {
          title: '用例序号',
          dataIndex: 'case_no',
          width: 100,
          render: (value) => (value ? `#${value}` : '-'),
        },
        {
          title: '来源编号',
          dataIndex: 'external_id',
          width: 220,
          ellipsis: { showTitle: true },
          render: (value) => value || '-',
        },
        {
          title: '轮次',
          width: 100,
          render: (_, record) =>
            record.round_no
              ? `第 ${record.round_no} 轮`
              : record.attempt_no
                ? `第 ${record.attempt_no} 次`
                : '-',
        },
        { title: '触发原因', dataIndex: 'trigger_reason', render: (value) => <Tag color="orange">{value}</Tag> },
        { title: '状态', dataIndex: 'status', width: 120, render: (value) => <Tag color={value === 'pending' ? 'warning' : 'success'}>{value}</Tag> },
        ...(showDecision
          ? [
              { title: '复核结论', dataIndex: 'decision', width: 120 },
              { title: '修正判定', dataIndex: 'corrected_verdict', width: 110 },
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
        description="处理低可信度、规则冲突和多 Judge 分歧结果，并修正 Judge 判定。"
        extra={
          <Space>
            <Input
              allowClear
              prefix={<SearchOutlined />}
              placeholder="按用例序号 / 来源编号 / 轮次搜索"
              style={{ width: 320 }}
              value={keyword}
              onChange={(event) => setKeyword(event.target.value)}
            />
            <Button icon={<ReloadOutlined />} onClick={() => reviewsQuery.refetch()}>
              刷新
            </Button>
            <Button
              icon={<ToolOutlined />}
              loading={backfillMutation.isPending}
              onClick={() => backfillMutation.mutate(selectedTaskId ?? undefined)}
            >
              {selectedTaskId ? '补建当前任务复核' : '补建历史复核'}
            </Button>
          </Space>
        }
      />

      <Card className="section-card" size="small">
        <Space wrap>
          <Select
            showSearch
            allowClear
            loading={tasksQuery.isLoading}
            placeholder="全部评测任务"
            optionFilterProp="label"
            style={{ width: 420 }}
            value={selectedTaskId ?? undefined}
            onChange={(value) => setSelectedTaskId(value ?? null)}
            options={tasks.map((task) => ({
              value: task.task_id,
              label: `${task.name} · #${task.task_id} · ${task.status}`,
            }))}
          />
          {selectedTask ? (
            <Tag color="blue">
              当前任务：{selectedTask.name} · #{selectedTask.task_id}
            </Tag>
          ) : (
            <Tag>全部评测任务</Tag>
          )}
          <Tag color="orange">待复核 {pendingTotal} 条</Tag>
        </Space>
      </Card>

      <Tabs
        items={[
          {
            key: 'queue',
            label: `待复核队列（${pendingTotal}）`,
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
        title={`复核详情 · 用例 ${detail?.case_no ? `#${detail.case_no}` : '-'}`}
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
              description="请结合模型输出、Judge 判断和规则命中给出复核结论。"
            />
            <Descriptions column={2} size="small" bordered>
              <Descriptions.Item label="评测任务">
                {detail.task_id
                  ? tasksById.get(detail.task_id)?.name ??
                    `任务 #${detail.task_id}`
                  : '-'}
              </Descriptions.Item>
              <Descriptions.Item label="用例序号">
                {detail.case_no ? `#${detail.case_no}` : '-'}
              </Descriptions.Item>
              <Descriptions.Item label="来源编号">
                <span title={detail.external_id ?? ''}>{shortenId(detail.external_id)}</span>
              </Descriptions.Item>
              <Descriptions.Item label="轮次">
                {detail.round_no
                  ? `第 ${detail.round_no} 轮`
                  : detail.attempt_no
                    ? `第 ${detail.attempt_no} 次`
                    : '-'}
              </Descriptions.Item>
              <Descriptions.Item label="Judge 判断">
                {detail.judge_verdict ?? '-'} / 置信度 {formatPercent(detail.judge_confidence)} / 可信度 {formatPercent(detail.judge_trust_score)}
              </Descriptions.Item>
              <Descriptions.Item label="规则命中">{detail.rule_hits}，最高严重度 {detail.rule_highest_severity ?? '-'}</Descriptions.Item>
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
              <Form.Item name="corrected_verdict" label="修正 Judge 判定">
                <Select
                  allowClear
                  options={[
                    { value: 'safe', label: 'safe' },
                    { value: 'unsafe', label: 'unsafe' },
                    { value: 'uncertain', label: 'uncertain' },
                  ]}
                />
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
