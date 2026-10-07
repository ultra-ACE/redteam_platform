import { Card, Flex, Tag } from 'antd';
import type { ReactNode } from 'react';

export function InnovationCard(props: {
  index: number;
  title: string;
  description: string;
  tags: string[];
  icon?: ReactNode;
}) {
  return (
    <Card className="innovation-card">
      <Flex align="flex-start" gap={14}>
        <div className="innovation-index">{props.index}</div>
        <div style={{ flex: 1 }}>
          <Flex align="center" gap={8}>
            {props.icon}
            <span style={{ fontWeight: 800, fontSize: 16 }}>{props.title}</span>
          </Flex>
          <p style={{ color: '#64748b', margin: '10px 0 14px', lineHeight: 1.7 }}>{props.description}</p>
          <Flex gap={8} wrap="wrap">
            {props.tags.map((tag) => (
              <Tag key={tag} className="soft-tag" color="blue">
                {tag}
              </Tag>
            ))}
          </Flex>
        </div>
      </Flex>
    </Card>
  );
}
