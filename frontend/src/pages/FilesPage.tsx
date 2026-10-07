import { useState } from 'react';
import {
  CloudUploadOutlined,
  DownloadOutlined,
  FileOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import {
  Button,
  Col,
  Empty,
  Input,
  InputNumber,
  Row,
  Space,
  Table,
  Tag,
  Typography,
  Upload,
  message,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { UploadFile } from 'antd';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { downloadFile, listFiles, uploadFile } from '../api';
import { PageHeader, SectionCard } from '../components/ui';
import type { StoredFile } from '../types/api';
import { formatDateTime } from '../utils/format';

const { Dragger } = Upload;
const { Text } = Typography;

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  if (value < 1024 * 1024 * 1024) return `${(value / 1024 / 1024).toFixed(1)} MB`;
  return `${(value / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

export function FilesPage() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [uploadOwnerType, setUploadOwnerType] = useState('');
  const [uploadOwnerId, setUploadOwnerId] = useState<number | null>(null);
  const [filterOwnerType, setFilterOwnerType] = useState('');
  const [filterOwnerId, setFilterOwnerId] = useState<number | null>(null);
  const [fileList, setFileList] = useState<UploadFile[]>([]);

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

  const uploadMutation = useMutation({
    mutationFn: async () => {
      const file = fileList[0]?.originFileObj;
      if (!file) {
        throw new Error('请选择要上传的文件');
      }
      const formData = new FormData();
      formData.append('file', file);
      if (uploadOwnerType.trim()) formData.append('owner_type', uploadOwnerType.trim());
      if (uploadOwnerId) formData.append('owner_id', String(uploadOwnerId));
      return uploadFile(formData);
    },
    onSuccess: (file) => {
      message.success(`文件「${file.original_name}」已保存到本地存储`);
      setFileList([]);
      queryClient.invalidateQueries({ queryKey: ['files'] });
    },
    onError: (error: Error) => message.error(error.message),
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
            <div style={{ color: '#94a3b8', fontSize: 12 }}>{record.mime_type || 'application/octet-stream'}</div>
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
      width: 210,
      render: (value: string) => <Text code>{value.slice(0, 12)}…</Text>,
    },
    {
      title: '关联对象',
      width: 170,
      render: (_, record) =>
        record.owner_type ? (
          <Tag color="blue">
            {record.owner_type}
            {record.owner_id ? ` #${record.owner_id}` : ''}
          </Tag>
        ) : (
          <Text type="secondary">未关联</Text>
        ),
    },
    {
      title: '上传时间',
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
    <div className="page-stack">
      <PageHeader
        title="文件管理"
        description="本地上传、索引和下载评测过程中的数据集、原始响应与报告文件。"
        extra={
          <Button icon={<ReloadOutlined />} onClick={() => filesQuery.refetch()}>
            刷新
          </Button>
        }
      />

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={9}>
          <SectionCard title="上传文件">
            <Space direction="vertical" size={16} style={{ width: '100%' }}>
              <Dragger
                fileList={fileList}
                multiple={false}
                maxCount={1}
                beforeUpload={() => false}
                onChange={({ fileList: next }) => setFileList(next.slice(-1))}
                onRemove={() => {
                  setFileList([]);
                  return true;
                }}
              >
                <p className="ant-upload-drag-icon">
                  <CloudUploadOutlined />
                </p>
                <p className="ant-upload-text">点击或拖拽文件到这里</p>
                <p className="ant-upload-hint">文件写入本地 data/uploads 目录，并记录 SHA256 校验值。</p>
              </Dragger>
              <Row gutter={12}>
                <Col span={14}>
                  <Input
                    value={uploadOwnerType}
                    onChange={(event) => setUploadOwnerType(event.target.value)}
                    placeholder="关联类型，如 benchmark / report"
                  />
                </Col>
                <Col span={10}>
                  <InputNumber
                    min={1}
                    value={uploadOwnerId ?? undefined}
                    onChange={(value) => setUploadOwnerId(value ? Number(value) : null)}
                    placeholder="关联 ID"
                    style={{ width: '100%' }}
                  />
                </Col>
              </Row>
              <Button
                type="primary"
                block
                icon={<CloudUploadOutlined />}
                loading={uploadMutation.isPending}
                disabled={!fileList.length}
                onClick={() => uploadMutation.mutate()}
              >
                上传并登记
              </Button>
            </Space>
          </SectionCard>
        </Col>

        <Col xs={24} xl={15}>
          <SectionCard
            title="文件索引"
            extra={<Tag color="blue">共 {total} 个文件</Tag>}
          >
            <Space direction="vertical" size={14} style={{ width: '100%' }}>
              <Row gutter={12}>
                <Col xs={24} sm={14}>
                  <Input
                    allowClear
                    value={filterOwnerType}
                    onChange={(event) => {
                      setFilterOwnerType(event.target.value);
                      setPage(1);
                    }}
                    placeholder="按关联类型筛选"
                    prefix={<FileOutlined />}
                  />
                </Col>
                <Col xs={24} sm={10}>
                  <InputNumber
                    min={1}
                    value={filterOwnerId ?? undefined}
                    onChange={(value) => {
                      setFilterOwnerId(value ? Number(value) : null);
                      setPage(1);
                    }}
                    placeholder="按关联 ID 筛选"
                    style={{ width: '100%' }}
                  />
                </Col>
              </Row>
              <Table<StoredFile>
                rowKey="file_id"
                loading={filesQuery.isLoading}
                dataSource={items}
                columns={columns}
                scroll={{ x: 980 }}
                locale={{ emptyText: <Empty description="暂无文件，先上传一个文件吧" /> }}
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
        </Col>
      </Row>
    </div>
  );
}

