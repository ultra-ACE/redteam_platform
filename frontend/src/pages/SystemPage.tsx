import { useQuery } from '@tanstack/react-query';
import { Table, Tag } from 'antd';
import { listSystemConfigs } from '../api';
import { PageHeader } from '../components/ui';

export function SystemPage() {
  const query = useQuery({ queryKey: ['system-configs'], queryFn: () => listSystemConfigs({ page_size: 200 }) });
  return (
    <div className="page-stack">
      <PageHeader title="系统配置" description="查看系统超时、并发、文件限制和评分参数。" />
      <Table
        rowKey="config_key"
        loading={query.isLoading}
        dataSource={query.data?.items ?? []}
        columns={[
          { title: '配置项', dataIndex: 'config_key' },
          { title: '配置值', dataIndex: 'config_value', render: (value) => <code>{JSON.stringify(value)}</code> },
          { title: '说明', dataIndex: 'description' },
          { title: '敏感', dataIndex: 'is_secret', render: (value) => <Tag color={value ? 'red' : 'default'}>{value ? '是' : '否'}</Tag> },
        ]}
      />
    </div>
  );
}
