import { useState } from 'react';
import { SearchOutlined } from '@ant-design/icons';
import { Button, Card, Col, InputNumber, Row, Space, Table, Tag } from 'antd';
import { useQuery } from '@tanstack/react-query';
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip as RechartsTooltip, XAxis, YAxis } from 'recharts';
import { getTaskStatistics } from '../api';
import { MetricCard, PageHeader, RiskLevelTag } from '../components/ui';
import { formatPercent, formatScore, riskColor } from '../utils/format';

export function StatisticsPage() {
  const [taskId, setTaskId] = useState<number>(1);
  const statsQuery = useQuery({
    queryKey: ['statistics-page', taskId],
    queryFn: () => getTaskStatistics(taskId),
    enabled: false,
    retry: false,
  });
  const stats = statsQuery.data;
  const riskBars = Object.entries(stats?.risk_level_distribution ?? {}).map(([name, value]) => ({ name, value }));

  return (
    <div className="page-stack">
      <PageHeader title="统计分析" description="按任务查看攻击成功率、风险分布、模型对比、模板对比和高风险案例。" />
      <Card className="section-card">
        <Space>
          <InputNumber min={1} value={taskId} onChange={(value) => setTaskId(Number(value ?? 1))} addonBefore="任务 ID" />
          <Button type="primary" icon={<SearchOutlined />} loading={statsQuery.isFetching} onClick={() => statsQuery.refetch()}>
            查询统计
          </Button>
        </Space>
      </Card>

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} xl={6}>
          <MetricCard label="结果总数" value={stats?.total_results ?? 0} icon={<SearchOutlined />} />
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <MetricCard label="攻击成功率" value={formatPercent(stats?.attack_success_rate)} color="#ef4444" />
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <MetricCard label="平均风险分" value={formatScore(stats?.average_risk_score)} color="#f97316" />
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <MetricCard label="Judge 可信度" value={formatPercent(stats?.judge_average_trust)} color="#22c55e" />
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={12}>
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
        <Col xs={24} xl={12}>
          <Card className="section-card" title="风险类别分布">
            <Table
              rowKey="code"
              dataSource={stats?.risk_category_distribution ?? []}
              pagination={false}
              columns={[
                { title: '风险类别', dataIndex: 'code' },
                { title: '数量', dataIndex: 'count' },
                { title: '平均风险分', dataIndex: 'average_score', render: formatScore },
              ]}
            />
          </Card>
        </Col>
      </Row>

      <Card className="section-card" title="模型对比">
        <Table
          rowKey={(record) => String(record.model_id)}
          dataSource={stats?.model_breakdown ?? []}
          pagination={false}
          columns={[
            { title: '模型 ID', dataIndex: 'model_id' },
            { title: '样本数', dataIndex: 'count' },
            { title: '不安全数', dataIndex: 'unsafe_count' },
            { title: '攻击成功率', dataIndex: 'attack_success_rate', render: formatPercent },
            { title: '平均风险分', dataIndex: 'average_risk_score', render: formatScore },
          ]}
        />
      </Card>

      <Card className="section-card" title="高风险案例 Top 10" extra={<Tag color="red">优先复核</Tag>}>
        <Table
          rowKey={(record) => String(record.attempt_id)}
          dataSource={stats?.top_risky_cases ?? []}
          pagination={false}
          columns={[
            { title: '尝试 ID', dataIndex: 'attempt_id' },
            { title: '用例 ID', dataIndex: 'external_id' },
            { title: '模型 ID', dataIndex: 'model_id' },
            { title: '风险分', dataIndex: 'overall_score', render: formatScore },
            { title: '风险等级', dataIndex: 'risk_level', render: (value) => <RiskLevelTag level={value} /> },
          ]}
        />
      </Card>
    </div>
  );
}
