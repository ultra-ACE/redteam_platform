import { useState } from 'react';
import { SearchOutlined } from '@ant-design/icons';
import { Button, Card, Input, InputNumber, Space, Table, Tag } from 'antd';
import { useQuery } from '@tanstack/react-query';
import { getTaskResults } from '../api';
import { AttemptDetailDrawer } from '../components/AttemptDetailDrawer';
import { JudgeVerdictTag, PageHeader, RiskLevelTag } from '../components/ui';
import { formatScore } from '../utils/format';

export function ResultsPage() {
  const [taskId, setTaskId] = useState<number>(1);
  const [keyword, setKeyword] = useState('');
  const [detailAttemptId, setDetailAttemptId] = useState<number | null>(null);
  const resultsQuery = useQuery({
    queryKey: ['results-page', taskId],
    queryFn: () => getTaskResults(taskId, { page_size: 100 }),
    enabled: false,
  });

  const items = resultsQuery.data?.items ?? [];
  const normalized = keyword.trim().toLowerCase();
  const filtered = normalized
    ? items.filter((item) =>
        [item.external_id, item.prompt_excerpt, String(item.attempt_id)].some((value) =>
          (value ?? '').toLowerCase().includes(normalized),
        ),
      )
    : items;

  return (
    <div className="page-stack">
      <PageHeader title="结果查询" description="输入任务 ID，查看逐条模型输出、Judge 判断、规则命中和风险量化结果。" />
      <Card className="section-card">
        <Space>
          <InputNumber min={1} value={taskId} onChange={(value) => setTaskId(Number(value ?? 1))} addonBefore="任务 ID" />
          <Button type="primary" icon={<SearchOutlined />} loading={resultsQuery.isFetching} onClick={() => resultsQuery.refetch()}>
            查询结果
          </Button>
        </Space>
      </Card>
      <Card
        className="section-card"
        title="逐条结果"
        extra={
          <Space>
            <Input
              allowClear
              prefix={<SearchOutlined />}
              placeholder="按用例 ID / 尝试 ID / 提示词筛选"
              style={{ width: 280 }}
              value={keyword}
              onChange={(event) => setKeyword(event.target.value)}
            />
            <Tag color="blue">{filtered.length} / {resultsQuery.data?.total ?? 0} 条</Tag>
            <Tag color="purple">点击行查看完整证据链</Tag>
          </Space>
        }
      >
        <Table
          rowKey="attempt_id"
          loading={resultsQuery.isLoading}
          dataSource={filtered}
          pagination={{ pageSize: 10 }}
          onRow={(record) => ({
            onClick: () => setDetailAttemptId(record.attempt_id),
            style: { cursor: 'pointer' },
          })}
          columns={[
            { title: '尝试 ID', dataIndex: 'attempt_id', width: 100 },
            { title: '用例 ID', dataIndex: 'external_id' },
            {
              title: '测试 Prompt',
              dataIndex: 'prompt_excerpt',
              ellipsis: { showTitle: true },
              render: (value: string | null | undefined) => value || '-',
            },
            { title: '模型 ID', dataIndex: 'model_id', width: 90 },
            { title: 'Judge', width: 110, render: (_, record) => <JudgeVerdictTag verdict={record.judge?.verdict} /> },
            { title: '规则命中', width: 100, render: (_, record) => record.rule_validation?.hit_count ?? 0 },
            { title: '风险分', width: 100, render: (_, record) => formatScore(record.risk?.overall_score) },
            { title: '风险等级', width: 110, render: (_, record) => <RiskLevelTag level={record.risk?.risk_level} /> },
            { title: '复核状态', dataIndex: 'manual_review_status', width: 110 },
          ]}
        />
      </Card>

      <AttemptDetailDrawer attemptId={detailAttemptId} onClose={() => setDetailAttemptId(null)} />
    </div>
  );
}
