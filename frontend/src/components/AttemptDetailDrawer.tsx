import { Alert, Card, Descriptions, Drawer, Flex, Space, Spin, Table, Tag, Typography } from 'antd';
import { useQuery } from '@tanstack/react-query';
import { getTaskAttemptDetail } from '../api';
import type { RuleValidationDetail } from '../types/api';
import { JudgeVerdictTag } from './ui';
import { formatDateTime, formatPercent, shortenId } from '../utils/format';

const { Text } = Typography;

const TRUST_LABELS: Record<string, string> = {
  rule_consistency: '规则一致性',
  evidence_completeness: '证据完整度',
  calibration_score: '校准得分',
};

function decodeBase64Payload(renderedPrompt?: string | null): string | null {
  if (!renderedPrompt) return null;
  const matches = renderedPrompt.match(/[A-Za-z0-9+/]{40,}={0,2}/g) ?? [];
  const payload = matches.sort((left, right) => right.length - left.length)[0];
  if (!payload) return null;
  try {
    const binary = atob(payload);
    const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0));
    return new TextDecoder().decode(bytes);
  } catch {
    return null;
  }
}

export function AttemptDetailDrawer(props: { attemptId: number | null; onClose: () => void }) {
  const { attemptId, onClose } = props;
  const query = useQuery({
    queryKey: ['attempt-detail', attemptId],
    queryFn: () => getTaskAttemptDetail(attemptId as number),
    enabled: Boolean(attemptId),
  });
  const detail = query.data;
  const decodedBase64 = decodeBase64Payload(detail?.rendered_prompt);

  return (
    <Drawer
      title={
        detail?.round_no
          ? `尝试详情 · #${attemptId ?? ''} · 第 ${detail.round_no} 轮`
          : `尝试详情 · #${attemptId ?? ''}`
      }
      placement="right"
      width={880}
      open={Boolean(attemptId)}
      onClose={onClose}
      destroyOnClose
    >
      {query.isLoading ? (
        <Flex justify="center" style={{ padding: 60 }}>
          <Spin />
        </Flex>
      ) : query.isError ? (
        <Alert type="error" showIcon message="加载失败" description={(query.error as Error).message} />
      ) : detail ? (
        <Space direction="vertical" size={18} style={{ width: '100%' }}>
          {detail.error_message ? (
            <Alert
              type="error"
              showIcon
              message={`执行错误：${detail.error_code ?? 'unknown'}`}
              description={detail.error_message}
            />
          ) : null}

          <Descriptions column={2} size="small" bordered>
            <Descriptions.Item label="来源编号">
              <span title={detail.external_id ?? ''}>{shortenId(detail.external_id)}</span>
            </Descriptions.Item>
            <Descriptions.Item label="用例序号">
              {detail.case_no ? `#${detail.case_no}` : '-'}
            </Descriptions.Item>
            <Descriptions.Item label="任务 ID">{detail.task_id ?? '-'}</Descriptions.Item>
            <Descriptions.Item label="数据集类型">{detail.dataset_type ?? '-'}</Descriptions.Item>
            <Descriptions.Item label="样本类型">{detail.sample_kind ?? '-'}</Descriptions.Item>
            <Descriptions.Item label="被测模型">{detail.model_name ?? `模型 #${detail.model_id}`}</Descriptions.Item>
            <Descriptions.Item label="攻击模板">
              {detail.attack_template_name ?? (detail.attack_template_id ? `模板 #${detail.attack_template_id}` : '未使用')}
            </Descriptions.Item>
            <Descriptions.Item label="迭代轮次">
              {detail.round_no ? <Tag color="purple">第 {detail.round_no} 轮</Tag> : '-'}
            </Descriptions.Item>
            <Descriptions.Item label="攻击方式">{detail.attack_strategy ?? '-'}</Descriptions.Item>
            <Descriptions.Item label="本次尝试">第 {detail.attempt_no} 次</Descriptions.Item>
            <Descriptions.Item label="执行状态"><Tag>{detail.status}</Tag></Descriptions.Item>
            <Descriptions.Item label="耗时">
              {detail.latency_ms === null || detail.latency_ms === undefined ? '-' : `${detail.latency_ms} ms`}
            </Descriptions.Item>
            <Descriptions.Item label="开始时间">{formatDateTime(detail.started_at)}</Descriptions.Item>
            <Descriptions.Item label="结束时间">{formatDateTime(detail.finished_at)}</Descriptions.Item>
          </Descriptions>

          <Card size="small" title="原始种子 / 行为">
            <pre className="code-block">{detail.prompt ?? '-'}</pre>
          </Card>

          {detail.attack_prompt ? (
            <Card size="small" title="攻击模型本轮生成的 Prompt">
              <pre className="code-block" style={{ maxHeight: 320, overflow: 'auto' }}>
                {detail.attack_prompt}
              </pre>
            </Card>
          ) : null}

          {detail.attack_strategy === 'base64' ? (
            <Card size="small" title="Base64 解码内容（用于核查）">
              <pre className="code-block" style={{ maxHeight: 320, overflow: 'auto' }}>
                {decodedBase64 ?? '无法解析 Base64 内容'}
              </pre>
            </Card>
          ) : null}

          <Card size="small" title="实际发送给模型的 Prompt">
            <pre className="code-block">
  {(detail as any).input_snapshot?.prompt ?? (detail as any).rendered_prompt ?? detail.prompt ?? '-'}
            </pre>
          </Card>

          <Card size="small" title="模型输出">
            <pre className="code-block" style={{ maxHeight: 320, overflow: 'auto' }}>
              {detail.model_output ?? '-'}
            </pre>
          </Card>

          <Card
            size="small"
            title="Judge 判断与可信度"
            extra={detail.judge ? <JudgeVerdictTag verdict={detail.judge.verdict} /> : null}
          >
            {detail.judge ? (
              <Space direction="vertical" size={12} style={{ width: '100%' }}>
                <Descriptions column={2} size="small">
                  <Descriptions.Item label="Judge">
                    {detail.judge.judge_profile_name ?? `#${detail.judge.judge_profile_id}`}
                  </Descriptions.Item>
                  <Descriptions.Item label="类型 / 策略">
                    {detail.judge.judge_type ?? '-'} / {detail.judge.strategy ?? '-'}
                  </Descriptions.Item>
                  <Descriptions.Item label="置信度">{formatPercent(detail.judge.confidence)}</Descriptions.Item>
                  <Descriptions.Item label="可信度">{formatPercent(detail.judge.trust_score)}</Descriptions.Item>
                </Descriptions>

                {detail.judge.trust_breakdown ? (
                  <Table
                    size="small"
                    rowKey="key"
                    pagination={false}
                    dataSource={Object.entries(detail.judge.trust_breakdown).map(([key, value]) => ({
                      key,
                      label: TRUST_LABELS[key] ?? key,
                      value: Number(value),
                    }))}
                    columns={[
                      { title: '可信度维度', dataIndex: 'label' },
                      { title: '得分', dataIndex: 'value', width: 120, render: formatPercent },
                    ]}
                  />
                ) : null}

                {detail.judge.reasoning ? (
                  <div>
                    <Text type="secondary">Judge 说明</Text>
                    <pre className="code-block" style={{ maxHeight: 200, overflow: 'auto', marginTop: 6 }}>
                      {detail.judge.reasoning}
                    </pre>
                  </div>
                ) : null}
              </Space>
            ) : (
              <Text type="secondary">该尝试暂无 Judge 结果。</Text>
            )}
          </Card>

          <Card size="small" title="规则校验命中">
            <Table<RuleValidationDetail>
              size="small"
              rowKey="rule_definition_id"
              pagination={false}
              dataSource={detail.rule_validations}
              locale={{ emptyText: '该尝试暂无规则校验结果' }}
              columns={[
                {
                  title: '规则',
                  dataIndex: 'rule_code',
                  render: (value, record) => value ?? `#${record.rule_definition_id}`,
                },
                {
                  title: '结果',
                  dataIndex: 'passed',
                  width: 110,
                  render: (passed: boolean) => <Tag color={passed ? 'success' : 'error'}>{passed ? '通过' : '命中'}</Tag>,
                },
                { title: '严重度', dataIndex: 'severity', width: 110, render: (value) => value ?? '-' },
                { title: '命中次数', dataIndex: 'hit_count', width: 110 },
              ]}
            />
          </Card>

          <Card size="small" title="人工复核">
            {detail.manual_review ? (
              <Descriptions column={2} size="small">
                <Descriptions.Item label="对应用例">
                  {detail.case_no ? `#${detail.case_no}` : '-'}
                </Descriptions.Item>
                <Descriptions.Item label="对应轮次">
                  {detail.round_no ? `第 ${detail.round_no} 轮` : '-'}
                </Descriptions.Item>
                <Descriptions.Item label="触发原因">{detail.manual_review.trigger_reason}</Descriptions.Item>
                <Descriptions.Item label="状态">{detail.manual_review.status}</Descriptions.Item>
                <Descriptions.Item label="结论">{detail.manual_review.decision ?? '-'}</Descriptions.Item>
                <Descriptions.Item label="修正判定">{detail.manual_review.corrected_verdict ?? '-'}</Descriptions.Item>
                <Descriptions.Item label="复核人">{detail.manual_review.reviewer ?? '-'}</Descriptions.Item>
              </Descriptions>
            ) : (
              <Text type="secondary">该尝试未触发人工复核。</Text>
            )}
          </Card>
        </Space>
      ) : null}
    </Drawer>
  );
}
