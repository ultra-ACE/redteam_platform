import { useState } from 'react';
import { SearchOutlined } from '@ant-design/icons';
import { Button, Card, Col, InputNumber, Row, Space, Table, Tag } from 'antd';
import { useQuery } from '@tanstack/react-query';
import { getTaskStatistics } from '../api';
import { MetricCard, PageHeader } from '../components/ui';
import { formatPercent } from '../utils/format';

export function StatisticsPage() {
  const [taskId, setTaskId] = useState<number>(1);
  const statsQuery = useQuery({
    queryKey: ['statistics-page', taskId],
    queryFn: () => getTaskStatistics(taskId),
    enabled: false,
    retry: false,
  });
  const stats = statsQuery.data;
  const verdictRows = Object.entries(stats?.judge_verdict_distribution ?? {}).map(([name, count]) => ({
    name,
    count,
  }));
  const datasetRows = Object.entries(stats?.dataset_type_distribution ?? {}).map(([name, count]) => ({
    name,
    count,
  }));

  return (
    <div className="page-stack">
      <PageHeader title="统计分析" description="按任务查看攻击成功率、Judge 判定、模型对比和数据集类型分布。" />
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
          <MetricCard label="不安全数" value={stats?.unsafe_count ?? 0} color="#f97316" />
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <MetricCard label="Judge 可信度" value={formatPercent(stats?.judge_average_trust)} color="#22c55e" />
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={12}>
          <Card className="section-card" title="Judge 判定分布">
            <Table
              rowKey="name"
              dataSource={verdictRows}
              pagination={false}
              columns={[
                { title: '判定', dataIndex: 'name' },
                { title: '数量', dataIndex: 'count' },
              ]}
            />
          </Card>
        </Col>
        <Col xs={24} xl={12}>
          <Card className="section-card" title="数据集类型分布">
            <Table
              rowKey="name"
              dataSource={datasetRows}
              pagination={false}
              columns={[
                { title: '数据集类型', dataIndex: 'name' },
                { title: '数量', dataIndex: 'count' },
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
          ]}
        />
      </Card>

      <Card className="section-card" title="不安全案例 Top 10" extra={<Tag color="red">优先复核</Tag>}>
        <Table
          rowKey={(record) => String(record.attempt_id)}
          dataSource={stats?.top_unsafe_cases ?? []}
          pagination={false}
          columns={[
            { title: '尝试 ID', dataIndex: 'attempt_id' },
            { title: '来源编号', dataIndex: 'external_id', ellipsis: { showTitle: true } },
            { title: '模型 ID', dataIndex: 'model_id' },
            { title: '数据集类型', dataIndex: 'dataset_type', render: (value) => value ?? '-' },
            { title: '样本类型', dataIndex: 'sample_kind', render: (value) => value ?? '-' },
          ]}
        />
      </Card>
    </div>
  );
}
