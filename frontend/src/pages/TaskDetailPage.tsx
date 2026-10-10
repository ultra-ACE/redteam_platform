import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeftOutlined, FileTextOutlined, RedoOutlined, ReloadOutlined } from '@ant-design/icons';
import { Button, Card, Col, Descriptions, Flex, Progress, Row, Space, Spin, Table, Tag, message } from 'antd';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip as RechartsTooltip, XAxis, YAxis } from 'recharts';
import { getTaskEventsUrl, getTaskResults, getTaskStatistics, getTaskStatus, retryFailedTask } from '../api';
import type { TaskStatusData } from '../types/api';
import { AttemptDetailDrawer } from '../components/AttemptDetailDrawer';
import { JudgeVerdictTag, PageHeader, RiskLevelTag, TaskStatusTag } from '../components/ui';
import { formatDateTime, formatPercent, formatScore, riskColor } from '../utils/format';

const TERMINAL_TASK_STATUSES = new Set(['succeeded', 'partially_failed', 'failed', 'cancelled']);

export function TaskDetailPage() {
  const { taskId } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [liveConnected, setLiveConnected] = useState(false);
  const [streamVersion, setStreamVersion] = useState(0);
  const [detailAttemptId, setDetailAttemptId] = useState<number | null>(null);
  const id = Number(taskId);

  const statusQuery = useQuery({ queryKey: ['task-status', id], queryFn: () => getTaskStatus(id), enabled: Boolean(id) });
  const resultsQuery = useQuery({ queryKey: ['task-results', id], queryFn: () => getTaskResults(id, { page_size: 100 }), enabled: Boolean(id) });
  const statsQuery = useQuery({ queryKey: ['task-statistics', id], queryFn: () => getTaskStatistics(id), enabled: Boolean(id), retry: false });

  const retryMutation = useMutation({
    mutationFn: () => retryFailedTask(id),
    onSuccess: (data) => {
      message.success(`已提交 ${data.retry_count} 个失败用例重试`);
      setStreamVersion((value) => value + 1);
      queryClient.invalidateQueries({ queryKey: ['task-status', id] });
      queryClient.invalidateQueries({ queryKey: ['task-results', id] });
      queryClient.invalidateQueries({ queryKey: ['task-statistics', id] });
    },
    onError: (error: Error) => message.error(error.message),
  });

  useEffect(() => {
    if (!id) return undefined;

    const source = new EventSource(getTaskEventsUrl(id));
    source.onopen = () => setLiveConnected(true);
    source.onerror = () => setLiveConnected(false);

    const applySnapshot = (event: Event) => {
      try {
        const payload = JSON.parse((event as MessageEvent<string>).data) as TaskStatusData;
        queryClient.setQueryData(['task-status', id], payload);
        if (TERMINAL_TASK_STATUSES.has(payload.status)) {
          source.close();
          setLiveConnected(false);
          queryClient.invalidateQueries({ queryKey: ['task-results', id] });
          queryClient.invalidateQueries({ queryKey: ['task-statistics', id] });
        }
      } catch {
        // Ignore malformed event data; manual refresh remains available.
      }
    };

    const handleTaskError = () => {
      setLiveConnected(false);
      source.close();
    };

    source.addEventListener('progress', applySnapshot);
    source.addEventListener('done', applySnapshot);
    source.addEventListener('task_error', handleTaskError);

    return () => {
      source.removeEventListener('progress', applySnapshot);
      source.removeEventListener('done', applySnapshot);
      source.removeEventListener('task_error', handleTaskError);
      source.close();
      setLiveConnected(false);
    };
  }, [id, queryClient, streamVersion]);


  const status = statusQuery.data;
  const stats = statsQuery.data;
  const riskBars = Object.entries(stats?.risk_level_distribution ?? {}).map(([name, value]) => ({ name, value }));

  return (
    <div className="page-stack">
      <PageHeader
        title={`任务详情 #${taskId}`}
        description="查看任务进度、逐条结果、Judge 可信度、规则命中和风险分布。"
        extra={
          <Space>
            <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/tasks')}>
              返回任务列表
            </Button>
            {status?.status === 'failed' || status?.status === 'partially_failed' ? (
              <Button icon={<RedoOutlined />} loading={retryMutation.isPending} onClick={() => retryMutation.mutate()}>
                重试失败用例
              </Button>
            ) : null}
            <Button icon={<ReloadOutlined />} onClick={() => { statusQuery.refetch(); resultsQuery.refetch(); statsQuery.refetch(); }}>
              刷新
            </Button>
            <Tag color={liveConnected ? 'success' : 'default'}>
              {liveConnected ? '实时连接' : '实时重连中'}
            </Tag>
            <Button type="primary" icon={<FileTextOutlined />} onClick={() => navigate('/reports')}>
              生成报告
            </Button>
          </Space>
        }
      />

      <Card className="section-card">
        {statusQuery.isLoading ? (
          <Flex justify="center" style={{ padding: 36 }}>
            <Spin />
          </Flex>
        ) : (
          <Row gutter={[24, 20]} align="middle">
            <Col xs={24} lg={10}>
              <Space direction="vertical" size={12} style={{ width: '100%' }}>
                <Space>
                  <TaskStatusTag status={status?.status} />
                  <Tag color="blue">任务 #{id}</Tag>
                </Space>
                <Progress percent={Math.round((status?.progress ?? 0) * 100)} strokeColor={{ from: '#4f6ef7', to: '#7c4dff' }} />
                <div style={{ color: '#64748b' }}>
                  总用例 {status?.total_cases ?? 0} · 已完成 {status?.completed_cases ?? 0} · 失败 {status?.failed_cases ?? 0}
                </div>
              </Space>
            </Col>
            <Col xs={24} lg={14}>
              <Descriptions column={{ xs: 1, sm: 2 }} size="small">
                <Descriptions.Item label="开始时间">{formatDateTime(status?.started_at)}</Descriptions.Item>
                <Descriptions.Item label="结束时间">{formatDateTime(status?.finished_at)}</Descriptions.Item>
                <Descriptions.Item label="当前阶段">{status?.current_stage ?? '-'}</Descriptions.Item>
                <Descriptions.Item label="取消请求">{status?.cancel_requested ? '是' : '否'}</Descriptions.Item>
              </Descriptions>
            </Col>
          </Row>
        )}
      </Card>

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} xl={6}>
          <Card className="metric-card">
            <div className="metric-label">攻击成功率</div>
            <div className="metric-value">{formatPercent(stats?.attack_success_rate)}</div>
          </Card>
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <Card className="metric-card">
            <div className="metric-label">平均风险分</div>
            <div className="metric-value">{formatScore(stats?.average_risk_score)}</div>
          </Card>
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <Card className="metric-card">
            <div className="metric-label">规则命中率</div>
            <div className="metric-value">{formatPercent(stats?.rule_hit_rate)}</div>
          </Card>
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <Card className="metric-card">
            <div className="metric-label">人工复核率</div>
            <div className="metric-value">{formatPercent(stats?.manual_review_rate)}</div>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={10}>
          <Card className="section-card chart-card" title="风险等级分布">
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={riskBars} margin={{ top: 10, right: 10, left: -18, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" />
                <XAxis dataKey="name" axisLine={false} tickLine={false} />
                <YAxis axisLine={false} tickLine={false} />
                <RechartsTooltip />
                <Bar dataKey="value" radius={[8, 8, 0, 0]}>
                  {riskBars.map((item) => (
                    <Cell key={item.name} fill={riskColor(item.name)} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </Card>
        </Col>
        <Col xs={24} xl={14}>
          <Card className="section-card" title="模型对比">
            <Table
              rowKey={(record) => String(record.model_id)}
              dataSource={stats?.model_breakdown ?? []}
              pagination={false}
              columns={[
                { title: '模型', dataIndex: 'model_name', render: (value, record) => value ?? `模型 #${record.model_id}` },
                { title: '模型 ID', dataIndex: 'model_id', width: 100 },
                { title: '样本数', dataIndex: 'count' },
                { title: '不安全数', dataIndex: 'unsafe_count' },
                { title: '攻击成功率', dataIndex: 'attack_success_rate', render: formatPercent },
                { title: '平均风险分', dataIndex: 'average_risk_score', render: formatScore },
              ]}
            />
          </Card>
        </Col>
      </Row>

      <Card
        className="section-card"
        title="逐条评测结果"
        extra={
          <Space>
            <Tag color="blue">最多展示 100 条</Tag>
            <Tag color="purple">点击任意行查看完整证据链</Tag>
          </Space>
        }
      >
        <Table
          rowKey="attempt_id"
          loading={resultsQuery.isLoading}
          dataSource={resultsQuery.data?.items ?? []}
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
            {
              title: 'Judge',
              width: 110,
              render: (_, record) => <JudgeVerdictTag verdict={record.judge?.verdict} />,
            },
            {
              title: '规则命中',
              width: 110,
              render: (_, record) => record.rule_validation?.hit_count ?? 0,
            },
            {
              title: '风险分',
              width: 110,
              render: (_, record) => formatScore(record.risk?.overall_score),
            },
            {
              title: '风险等级',
              width: 120,
              render: (_, record) => <RiskLevelTag level={record.risk?.risk_level} />,
            },
            { title: '复核状态', dataIndex: 'manual_review_status', width: 120 },
          ]}
        />
      </Card>

      <AttemptDetailDrawer attemptId={detailAttemptId} onClose={() => setDetailAttemptId(null)} />
    </div>
  );
}
