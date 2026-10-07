import type { ReactNode } from 'react';
import { Card, Empty, Flex, Tag, Typography } from 'antd';
import type { CardProps } from 'antd';
import { riskColor, taskStatusColor, verdictColor } from '../utils/format';

const { Text, Title, Paragraph } = Typography;

export function PageHeader(props: {
  title: string;
  description?: string;
  extra?: ReactNode;
}) {
  return (
    <div className="page-header">
      <div>
        <Title level={2}>{props.title}</Title>
        {props.description ? <Paragraph>{props.description}</Paragraph> : null}
      </div>
      {props.extra ? <div>{props.extra}</div> : null}
    </div>
  );
}

export function SectionCard(props: CardProps & { title?: ReactNode; extra?: ReactNode }) {
  return (
    <Card className="section-card" {...props}>
      {props.children}
    </Card>
  );
}

export function MetricCard(props: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  icon?: ReactNode;
  color?: string;
}) {
  return (
    <Card className="metric-card">
      <div
        className="metric-icon"
        style={{
          background: `${props.color ?? '#4f6ef7'}18`,
          color: props.color ?? '#4f6ef7',
        }}
      >
        {props.icon}
      </div>
      <div className="metric-label">{props.label}</div>
      <div className="metric-value">{props.value}</div>
      {props.hint ? <div className="metric-hint">{props.hint}</div> : null}
    </Card>
  );
}

export function TaskStatusTag({ status }: { status?: string | null }) {
  return (
    <Tag className="soft-tag" color={taskStatusColor(status)}>
      {status ?? 'unknown'}
    </Tag>
  );
}

export function JudgeVerdictTag({ verdict }: { verdict?: string | null }) {
  return (
    <Tag className="soft-tag" color={verdictColor(verdict)}>
      {verdict ?? 'unknown'}
    </Tag>
  );
}

export function RiskLevelTag({ level }: { level?: string | null }) {
  return (
    <Tag
      className="soft-tag"
      style={{
        color: riskColor(level),
        background: `${riskColor(level)}18`,
      }}
    >
      {level ?? 'unknown'}
    </Tag>
  );
}

export function EmptyPanel(props: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty-panel">
      <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} />
      <h3>{props.title}</h3>
      <p>{props.description}</p>
      {props.action ? <div style={{ marginTop: 18 }}>{props.action}</div> : null}
    </div>
  );
}

export function KeyValue(props: { label: string; value: ReactNode }) {
  return (
    <Flex vertical gap={4}>
      <Text type="secondary" style={{ fontSize: 12 }}>
        {props.label}
      </Text>
      <Text strong>{props.value}</Text>
    </Flex>
  );
}
