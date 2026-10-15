import { useState } from 'react';
import { DownloadOutlined, FileTextOutlined, SearchOutlined } from '@ant-design/icons';
import { Button, Col, InputNumber, Row, Space, Tag, message } from 'antd';
import { useMutation, useQuery } from '@tanstack/react-query';
import { createReport, downloadReport, getReport } from '../api';
import { PageHeader, SectionCard } from '../components/ui';
import type { Report } from '../types/api';
import { formatDateTime } from '../utils/format';

export function ReportsPage() {
  const [taskId, setTaskId] = useState(1);
  const [reportId, setReportId] = useState<number | null>(null);

  const createMutation = useMutation({
    mutationFn: () =>
      createReport({
        task_id: taskId,
        report_type: 'full',
        format: 'html',
        include: ['summary', 'judge_distribution', 'dataset_types', 'case_details', 'judge_trust', 'rule_hits', 'manual_reviews'],
        filters: {},
      }),
    onSuccess: (report: Report) => {
      setReportId(report.report_id);
      message.success(`报告 #${report.report_id} 已创建`);
    },
    onError: (error: Error) => message.error(error.message),
  });

  const reportQuery = useQuery({
    queryKey: ['report', reportId],
    queryFn: () => getReport(reportId!),
    enabled: Boolean(reportId),
    retry: false,
  });

  const handleDownload = async () => {
    if (!reportId) return;
    const response = await downloadReport(reportId);
    const blob = new Blob([response.data]);
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `report-${reportId}.${reportQuery.data?.format ?? 'html'}`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="page-stack">
      <PageHeader
        title="报告中心"
        description="为指定评测任务生成可直接打开和下载的 HTML 报告。"
      />
      <Row gutter={[16, 16]}>
        <Col xs={24} xl={10}>
          <SectionCard title="创建报告">
            <Space direction="vertical" size={16} style={{ width: '100%' }}>
              <InputNumber min={1} value={taskId} onChange={(value) => setTaskId(Number(value ?? 1))} addonBefore="任务 ID" style={{ width: '100%' }} />
              <Button type="primary" block icon={<FileTextOutlined />} loading={createMutation.isPending} onClick={() => createMutation.mutate()}>
                生成报告
              </Button>
            </Space>
          </SectionCard>
        </Col>
        <Col xs={24} xl={14}>
          <SectionCard title="报告状态" extra={reportId ? <Tag color="blue">报告 #{reportId}</Tag> : null}>
            <Space direction="vertical" size={16} style={{ width: '100%' }}>
              <Space>
                <InputNumber
                  min={1}
                  value={reportId ?? undefined}
                  onChange={(value) => setReportId(value ? Number(value) : null)}
                  addonBefore="报告 ID"
                />
                <Button icon={<SearchOutlined />} disabled={!reportId} onClick={() => reportQuery.refetch()}>
                  查询
                </Button>
                <Button
                  type="primary"
                  icon={<DownloadOutlined />}
                  disabled={!reportQuery.data || reportQuery.data.status !== 'ready'}
                  onClick={handleDownload}
                >
                  下载
                </Button>
              </Space>
              {reportQuery.data ? (
                <div className="code-block">
                  {JSON.stringify(
                    {
                      report_id: reportQuery.data.report_id,
                      task_id: reportQuery.data.task_id,
                      status: reportQuery.data.status,
                      format: reportQuery.data.format,
                      file_id: reportQuery.data.file_id,
                      created_at: formatDateTime(reportQuery.data.created_at),
                      finished_at: formatDateTime(reportQuery.data.finished_at),
                    },
                    null,
                    2,
                  )}
                </div>
              ) : (
                <div style={{ color: '#94a3b8' }}>创建或输入报告 ID 后查看状态。</div>
              )}
            </Space>
          </SectionCard>
        </Col>
      </Row>
    </div>
  );
}
