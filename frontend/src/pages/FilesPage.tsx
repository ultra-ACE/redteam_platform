import { useState } from 'react';
import { DownloadOutlined, FileOutlined, ReloadOutlined } from '@ant-design/icons';
import { Button, Empty, InputNumber, Select, Space, Table, Tag, Typography, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useQuery } from '@tanstack/react-query';
import { downloadFile, listFiles } from '../api';
import { PageHeader, SectionCard } from '../components/ui';
import type { StoredFile } from '../types/api';
import { formatDateTime } from '../utils/format';

const { Text } = Typography;

/** 文件来源的展示名：台账里的文件都由系统内部产生，用户不需要手动上传。 */
const OWNER_LABELS: Record<string, string> = {
  benchmark_import: '数据集导入',
  report: '报告生成',
  model_response: '模型响应',
};

const OWNER_OPTIONS = [
  { value: 'benchmark_import', label: '数据集导入' },
  { value: 'report', label: '报告生成' },
  { value: 'model_response', label: '模型响应' },
];

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  if (value < 1024 * 1024 * 1024) return `${(value / 1024 / 1024).toFixed(1)} MB`;
  return `${(value / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

export function FilesPage({ embedded = false }: { embedded?: boolean }) {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [filterOwnerType, setFilterOwnerType] = useState<string | undefined>(undefined);
  const [filterOwnerId, setFilterOwnerId] = useState<number | null>(null);

  const filesQuery = useQuery({
    queryKey: ['files', page, pageSize, filterOwnerType, filterOwnerId],
    queryFn: () =>
      listFiles({
        page,
        page_size: pageSize,
        owner_type: filterOwnerType || undefined,
        owner_id: filterOwnerId ?? undefined,
      }),
  });

  const handleDownload = async (file: StoredFile) => {
    try {
      const response = await downloadFile(file.file_id);
      const blob = new Blob([response.data], { type: file.mime_type || 'application/octet-stream' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = file.original_name;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (error) {
      message.error(error instanceof Error ? error.message : '文件下载失败');
    }
  };

  const columns: ColumnsType<StoredFile> = [
    {
      title: '文件',
      dataIndex: 'original_name',
      ellipsis: true,
      render: (value: string, record) => (
        <Space>
          <FileOutlined style={{ color: '#4f6ef7' }} />
          <div>
            <Text strong>{value}</Text>
            <div style={{ color: '#94a3b8', fontSize: 12 }}>
              {record.mime_type || 'application/octet-stream'}
            </div>
          </div>
        </Space>
      ),
    },
    {
      title: '大小',
      dataIndex: 'size_bytes',
      width: 110,
      render: (value: number) => formatBytes(value),
    },
    {
      title: 'SHA256',
      dataIndex: 'sha256',
      width: 190,
      render: (value: string) => <Text code>{(value ?? '').slice(0, 12)}…</Text>,
    },
    {
      title: '来源',
      width: 170,
      render: (_, record) =>
        record.owner_type ? (
          <Tag color={record.owner_type === 'report' ? 'purple' : 'blue'}>
            {OWNER_LABELS[record.owner_type] ?? record.owner_type}
            {record.owner_id ? ` #${record.owner_id}` : ''}
          </Tag>
        ) : (
          <Text type="secondary">未关联</Text>
        ),
    },
    {
      title: '产生时间',
      dataIndex: 'created_at',
      width: 180,
      render: formatDateTime,
    },
    {
      title: '操作',
      width: 110,
      fixed: 'right',
      render: (_, record) => (
        <Button type="link" icon={<DownloadOutlined />} onClick={() => handleDownload(record)}>
          下载
        </Button>
      ),
    },
  ];

  const items = filesQuery.data?.items ?? [];
  const total = filesQuery.data?.total ?? 0;

  return (
    <div className={embedded ? undefined : 'page-stack'}>
      {!embedded ? (
        <PageHeader
          title="文件台账"
          description="系统统一记录所有落盘文件：导入的数据集原文与生成的报告产物。"
        />
      ) : null}

      <SectionCard
        title="文件索引"
        extra={
          <Space>
            <Button icon={<ReloadOutlined />} onClick={() => filesQuery.refetch()}>
              刷新
            </Button>
            <Tag color="blue">共 {total} 个文件</Tag>
          </Space>
        }
      >
        <Space direction="vertical" size={14} style={{ width: '100%' }}>
          <Space wrap>
            <Select
              allowClear
              placeholder="按来源筛选"
              style={{ width: 200 }}
              value={filterOwnerType}
              options={OWNER_OPTIONS}
              onChange={(value) => {
                setFilterOwnerType(value);
                setPage(1);
              }}
            />
            <InputNumber
              min={1}
              placeholder="按来源 ID 筛选"
              style={{ width: 200 }}
              value={filterOwnerId ?? undefined}
              onChange={(value) => {
                setFilterOwnerId(value ? Number(value) : null);
                setPage(1);
              }}
            />
          </Space>
          <Table<StoredFile>
            rowKey="file_id"
            loading={filesQuery.isLoading}
            dataSource={items}
            columns={columns}
            scroll={{ x: 980 }}
            locale={{ emptyText: <Empty description="暂无文件记录" /> }}
            pagination={{
              current: page,
              pageSize,
              total,
              showSizeChanger: true,
              pageSizeOptions: [10, 20, 50, 100],
              showTotal: (value) => `共 ${value} 条`,
              onChange: (nextPage, nextPageSize) => {
                setPage(nextPage);
                setPageSize(nextPageSize);
              },
            }}
          />
        </Space>
      </SectionCard>
    </div>
  );
}
