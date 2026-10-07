import { useQuery } from '@tanstack/react-query';
import { ReloadOutlined } from '@ant-design/icons';
import { Button, Table, Tag, Typography } from 'antd';
import { listAuditLogs } from '../api';
import { PageHeader, SectionCard } from '../components/ui';
import type { AuditLog } from '../types/api';
import { formatDateTime } from '../utils/format';

const { Text } = Typography;

export function AuditPage() {
  const query = useQuery({ queryKey: ['audit-logs'], queryFn: () => listAuditLogs({ page_size: 200 }) });

  return (
    <div className="page-stack">
      <PageHeader
        title="审计日志"
        description="自动记录关键写操作，包括操作者、资源、请求链路和变更结果。"
        extra={<Button icon={<ReloadOutlined />} onClick={() => query.refetch()}>刷新</Button>}
      />
      <SectionCard title="关键操作记录" extra={<Tag color="blue">最近 {query.data?.total ?? 0} 条</Tag>}>
        <Table<AuditLog>
          rowKey="audit_id"
          loading={query.isLoading}
          dataSource={query.data?.items ?? []}
          scroll={{ x: 1180 }}
          pagination={{ pageSize: 20, showSizeChanger: true, pageSizeOptions: [10, 20, 50, 100] }}
          columns={[
            { title: 'ID', dataIndex: 'audit_id', width: 80 },
            { title: '操作者', dataIndex: 'actor', width: 110 },
            {
              title: '动作',
              dataIndex: 'action',
              width: 220,
              render: (value: string) => <Tag color="purple">{value}</Tag>,
            },
            { title: '资源类型', dataIndex: 'resource_type', width: 150 },
            { title: '资源 ID', dataIndex: 'resource_id', width: 100, render: (value) => value ?? '-' },
            {
              title: '请求 ID',
              dataIndex: 'request_id',
              width: 250,
              render: (value: string | null) => value ? <Text code>{value}</Text> : '-',
            },
            { title: 'IP', dataIndex: 'ip', width: 130, render: (value: string | null) => value ?? '-' },
            {
              title: '变更摘要',
              dataIndex: 'after_data',
              width: 260,
              render: (value: Record<string, unknown> | null) => value ? (
                <Text style={{ fontSize: 12 }}>{JSON.stringify(value)}</Text>
              ) : '-',
            },
            { title: '时间', dataIndex: 'created_at', width: 180, render: formatDateTime },
          ]}
        />
      </SectionCard>
    </div>
  );
}
