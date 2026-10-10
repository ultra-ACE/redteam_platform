import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AlertOutlined,
  ArrowRightOutlined,
  CheckCircleOutlined,
  FileTextOutlined,
  RobotOutlined,
  SafetyCertificateOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { Button, Card, Col, Flex, Row, Spin, Table, Tag, Typography } from 'antd';
import { useQuery } from '@tanstack/react-query';
import {
  Area,
  AreaChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { getTaskStatistics, listModels, listTasks } from '../api';
import { InnovationCard } from '../components/InnovationCard';
import { MetricCard, RiskLevelTag, TaskStatusTag } from '../components/ui';
import { formatPercent, formatScore, riskColor } from '../utils/format';

const { Text } = Typography;

const trendDemo = [
  { name: '08-01', risk: 42 },
  { name: '08-05', risk: 48 },
  { name: '08-10', risk: 45 },
  { name: '08-15', risk: 57 },
  { name: '08-20', risk: 61 },
  { name: '08-25', risk: 58 },
  { name: '08-30', risk: 66 },
];

export function DashboardPage() {
  const navigate = useNavigate();
  const modelsQuery = useQuery({ queryKey: ['models', 'dashboard'], queryFn: () => listModels({ page_size: 200 }) });
  const tasksQuery = useQuery({ queryKey: ['tasks', 'dashboard'], queryFn: () => listTasks({ page_size: 200 }) });

  const tasks = tasksQuery.data?.items ?? [];
  const latestTask = useMemo(() => tasks[0], [tasks]);

  const statsQuery = useQuery({
    queryKey: ['statistics', latestTask?.task_id],
    queryFn: () => getTaskStatistics(latestTask!.task_id),
    enabled: Boolean(latestTask?.task_id),
    retry: false,
  });

  const stats = statsQuery.data;
  const riskDistribution = Object.entries(stats?.risk_level_distribution ?? {}).map(([name, value]) => ({
    name,
    value,
    color: riskColor(name),
  }));

  return (
    <div className="page-stack">
      <Card className="hero-card">
        <div className="hero-eyebrow">LLM SECURITY EVALUATION</div>
        <h1 className="hero-title">大模型越狱攻击安全评测平台</h1>
        <p className="hero-desc">
          统一管理异构 Benchmark、越狱攻击模板、Judge 评价、规则校验和细粒度风险量化，让每一次评测都可量化、可解释、可复核。
        </p>
        <div className="hero-actions">
          <Button size="large" type="primary" icon={<ThunderboltOutlined />} onClick={() => navigate('/tasks')}>
            开始评测
          </Button>
          <Button size="large" ghost icon={<ArrowRightOutlined />} onClick={() => navigate('/statistics')}>
            查看统计分析
          </Button>
          <Button size="large" ghost icon={<FileTextOutlined />} onClick={() => navigate('/reports')}>
            报告中心
          </Button>
        </div>
      </Card>

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} xl={6}>
          <MetricCard
            label="已接入模型"
            value={modelsQuery.data?.total ?? 0}
            hint="被测模型 / Judge 模型"
            icon={<RobotOutlined />}
            color="#4f6ef7"
          />
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <MetricCard
            label="评测任务"
            value={tasksQuery.data?.total ?? 0}
            hint="已完成 / 运行中 / 排队"
            icon={<ThunderboltOutlined />}
            color="#7c4dff"
          />
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <MetricCard
            label="平均风险分"
            value={formatScore(stats?.average_risk_score)}
            hint="基于最新任务统计"
            icon={<AlertOutlined />}
            color="#f97316"
          />
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <MetricCard
            label="Judge 平均可信度"
            value={formatPercent(stats?.judge_average_trust)}
            hint="规则一致性 + 多 Judge 一致性"
            icon={<CheckCircleOutlined />}
            color="#22c55e"
          />
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={15}>
          <Card className="section-card chart-card" title="风险趋势概览" extra={<Tag color="blue">演示数据</Tag>}>
            <ResponsiveContainer width="100%" height={260}>
              <AreaChart data={trendDemo} margin={{ top: 10, right: 10, left: -18, bottom: 0 }}>
                <defs>
                  <linearGradient id="riskGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#4f6ef7" stopOpacity={0.35} />
                    <stop offset="95%" stopColor="#4f6ef7" stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" />
                <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 12 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#94a3b8', fontSize: 12 }} axisLine={false} tickLine={false} />
                <RechartsTooltip />
                <Area
                  type="monotone"
                  dataKey="risk"
                  stroke="#4f6ef7"
                  strokeWidth={3}
                  fill="url(#riskGradient)"
                  name="风险分"
                />
              </AreaChart>
            </ResponsiveContainer>
          </Card>
        </Col>
        <Col xs={24} xl={9}>
          <Card className="section-card chart-card" title="风险等级分布" extra={<Tag color="purple">实时统计</Tag>}>
            {statsQuery.isLoading ? (
              <Flex justify="center" align="center" style={{ height: 260 }}>
                <Spin />
              </Flex>
            ) : riskDistribution.length ? (
              <ResponsiveContainer width="100%" height={260}>
                <PieChart>
                  <Pie data={riskDistribution} dataKey="value" nameKey="name" innerRadius={62} outerRadius={94} paddingAngle={4}>
                    {riskDistribution.map((item) => (
                      <Cell key={item.name} fill={item.color} />
                    ))}
                  </Pie>
                  <RechartsTooltip />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <Flex vertical align="center" justify="center" style={{ height: 260 }}>
                <SafetyCertificateOutlined style={{ fontSize: 38, color: '#cbd5e1' }} />
                <Text type="secondary" style={{ marginTop: 12 }}>
                  暂无风险数据，先创建一个评测任务
                </Text>
              </Flex>
            )}
          </Card>
        </Col>
      </Row>

      <Card
        className="section-card"
        title="最近评测任务"
        extra={<Button type="link" onClick={() => navigate('/tasks')}>查看全部</Button>}
      >
        <Table
          rowKey="task_id"
          loading={tasksQuery.isLoading}
          dataSource={tasks.slice(0, 5)}
          pagination={false}
          columns={[
            { title: '任务 ID', dataIndex: 'task_id', width: 100 },
            { title: '任务名称', dataIndex: 'name' },
            { title: '状态', dataIndex: 'status', width: 120, render: (value) => <TaskStatusTag status={value} /> },
            { title: '进度', dataIndex: 'progress', width: 140, render: (value) => formatPercent(value) },
            { title: '风险等级', dataIndex: 'risk_level', width: 120, render: () => <RiskLevelTag level="medium" /> },
          ]}
        />
      </Card>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={8}>
          <InnovationCard
            index={1}
            title="统一风险分类"
            description="把不同 Benchmark 的原始标签映射到统一风险编码，消除异构评测口径差异。"
            tags={['Benchmark 适配', '风险映射', '标准化评测']}
            icon={<SafetyCertificateOutlined style={{ color: '#4f6ef7' }} />}
          />
        </Col>
        <Col xs={24} xl={8}>
          <InnovationCard
            index={2}
            title="细粒度风险量化"
            description="从危害严重度、攻击成功率、意图配合度、规则命中、稳定性和跨模板一致性六个维度量化风险。"
            tags={['六维评分', '风险等级', '置信度']}
            icon={<AlertOutlined style={{ color: '#f97316' }} />}
          />
        </Col>
        <Col xs={24} xl={8}>
          <InnovationCard
            index={3}
            title="Judge 可信度"
            description="结合规则校验、多 Judge 一致性、证据完整性和人工复核历史，判断 Judge 评价是否可信。"
            tags={['规则校验', '可信度', '人工复核']}
            icon={<CheckCircleOutlined style={{ color: '#22c55e' }} />}
          />
        </Col>
      </Row>
    </div>
  );
}
