import { Alert, Card, Descriptions, Drawer, Flex, Space, Spin, Table, Tag, Typography } from 'antd';
import { useQuery } from '@tanstack/react-query';
import { getTaskAttemptDetail } from '../api';
import type { RuleValidationDetail } from '../types/api';
import { JudgeVerdictTag, RiskLevelTag } from './ui';
import { formatDateTime, formatPercent, formatScore, riskColor } from '../utils/format';

const { Text } = Typography;

/** 六维风险量化的中文名，用于详情页展示。 */
const DIMENSION_LABELS: Record<string, string> = {
  harm_severity: '危害严重度',
  attack_success: '攻击成功信号',
  intent_compliance: '意图顺从度',
  rule_violation_severity: '规则违例严重度',
  multi_run_consistency: '多轮一致性',
  cross_template_consistency: '跨模板一致性',
};

const TRUST_LABELS: Record<string, string> = {
  rule_consistency: '规则一致性',
  ensemble_agreement: '多 Judge 一致度',
  evidence_completeness: '证据完整度',
  calibration_score: '校准得分',
};

export function AttemptDetailDrawer(props: { attemptId: number | null; onClose: () => void }) {
  const { attemptId, onClose } = props;
  const query = useQuery({
    queryKey: ['attempt-detail', attemptId],
    queryFn: () => getTaskAttemptDetail(attemptId as number),
    enabled: Boolean(attemptId),
  });

  const detail = query.data;

  return (
    <Drawer
      title={`尝试详情 · #${attemptId ?? ''}`}
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
            <Alert type="error" showIcon message={`执行错误：${detail.error_code ?? 'unknown'}`} description={detail.error_message} />
          ) : null}

          <Descriptions column={2} size="small" bordered>
            <Descriptions.Item label="用例 ID">{detail.external_id ?? detail.test_case_id ?? '-'}</Descriptions.Item>
            <Descriptions.Item label="任务 ID">{detail.task_id ?? '-'}</Descriptions.Item>
            <Descriptions.Item label="被测模型">{detail.model_name ?? `模型 #${detail.model_id}`}</Descriptions.Item>
            <Descriptions.Item label="攻击模板">
              {detail.attack_template_name ?? (detail.attack_template_id ? `模板 #${detail.attack_template_id}` : '未使用（原始用例）')}
            </Descriptions.Item>
            <Descriptions.Item label="尝试序号">第 {detail.attempt_no} 次</Descriptions.Item>
            <Descriptions.Item label="执行状态">
              <Tag>{detail.status}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="耗时">
              {detail.latency_ms === null || detail.latency_ms === undefined ? '-' : `${detail.latency_ms} ms`}
            </Descriptions.Item>
            <Descriptions.Item label="Token 用量">
              输入 {detail.prompt_tokens ?? '-'} / 输出 {detail.completion_tokens ?? '-'}
            </Descriptions.Item>
            <Descriptions.Item label="开始时间">{formatDateTime(detail.started_at)}</Descriptions.Item>
            <Descriptions.Item label="结束时间">{formatDateTime(detail.finished_at)}</Descriptions.Item>
          </Descriptions>

          <Card size="small" title="测试 Prompt">
            <pre className="code-block">{detail.prompt ?? '-'}</pre>
            {detail.system_prompt ? (
              <>
                <Text type="secondary" style={{ display: 'block', margin: '12px 0 6px' }}>
                  系统提示词
                </Text>
                <pre className="code-block">{detail.system_prompt}</pre>
              </>
            ) : null}
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
                  <Descriptions.Item label="Judge">{detail.judge.judge_profile_name ?? `#${detail.judge.judge_profile_id}`}</Descriptions.Item>
                  <Descriptions.Item label="类型 / 策略">
                    {detail.judge.judge_type ?? '-'} / {detail.judge.strategy ?? '-'}
                  </Descriptions.Item>
                  <Descriptions.Item label="置信度">{formatPercent(detail.judge.confidence)}</Descriptions.Item>
                  <Descriptions.Item label="可信度">{formatPercent(detail.judge.trust_score)}</Descriptions.Item>
                  <Descriptions.Item label="风险类别">
                    {detail.judge.risk_category ? `${detail.judge.risk_category.code} · ${detail.judge.risk_category.name}` : '-'}
                  </Descriptions.Item>
                  <Descriptions.Item label="综合风险">
                    <Space>
                      <RiskLevelTag level={detail.risk?.risk_level} />
                      <span>{formatScore(detail.risk?.overall_score)}</span>
                    </Space>
                  </Descriptions.Item>
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
                { title: '规则', dataIndex: 'rule_code', render: (value, record) => value ?? `#${record.rule_definition_id}` },
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

          <Card size="small" title="六维风险量化" extra={<Tag color={riskColor(detail.risk?.risk_level)}>{detail.risk?.risk_level ?? '未量化'}</Tag>}>
            {detail.risk ? (
              <Space direction="vertical" size={12} style={{ width: '100%' }}>
                <Descriptions column={2} size="small">
                  <Descriptions.Item label="综合风险分">{formatScore(detail.risk.overall_score)}</Descriptions.Item>
                  <Descriptions.Item label="评分版本">{detail.risk.score_version}</Descriptions.Item>
                  <Descriptions.Item label="量化置信度">{formatPercent(detail.risk.confidence)}</Descriptions.Item>
                  <Descriptions.Item label="不确定性">{formatPercent(detail.risk.uncertainty)}</Descriptions.Item>
                </Descriptions>
                <Table
                  size="small"
                  rowKey="dimension_code"
                  pagination={false}
                  dataSource={detail.risk.dimensions}
                  columns={[
                    {
                      title: '风险维度',
                      dataIndex: 'dimension_code',
                      render: (value: string) => DIMENSION_LABELS[value] ?? value,
                    },
                    { title: '得分', dataIndex: 'score', width: 110, render: formatScore },
                    { title: '权重', dataIndex: 'weight', width: 110, render: formatPercent },
                    { title: '来源', dataIndex: 'source', width: 110, render: (value) => value ?? '-' },
                  ]}
                />
              </Space>
            ) : (
              <Text type="secondary">该尝试尚未完成风险量化。</Text>
            )}
          </Card>

          <Card size="small" title="人工复核">
            {detail.manual_review ? (
              <Descriptions column={2} size="small">
                <Descriptions.Item label="复核 ID">#{detail.manual_review.review_id}</Descriptions.Item>
                <Descriptions.Item label="触发原因">{detail.manual_review.trigger_reason}</Descriptions.Item>
                <Descriptions.Item label="状态">{detail.manual_review.status}</Descriptions.Item>
                <Descriptions.Item label="结论">{detail.manual_review.decision ?? '-'}</Descriptions.Item>
                <Descriptions.Item label="修正分">{formatScore(detail.manual_review.corrected_score ?? null)}</Descriptions.Item>
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
