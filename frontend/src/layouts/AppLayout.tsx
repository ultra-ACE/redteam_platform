import { useMemo, useState } from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import {
  ApiOutlined,
  BarChartOutlined,
  FileDoneOutlined,
  FileSearchOutlined,
  FileTextOutlined,
  FundProjectionScreenOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  RobotOutlined,
  SafetyCertificateOutlined,
  TeamOutlined,
} from '@ant-design/icons';
import { Avatar, Badge, Button, Flex, Layout, Menu, Space, Tag, Tooltip, Typography } from 'antd';
import { useQuery } from '@tanstack/react-query';
import { getHealth } from '../api';

const { Sider, Header, Content } = Layout;
const { Text } = Typography;

const menuItems = [
  {
    type: 'group' as const,
    label: '总览',
    children: [
      { key: '/statistics', icon: <BarChartOutlined />, label: '统计分析' },
    ],
  },
  {
    type: 'group' as const,
    label: '评测资产',
    children: [
      { key: '/models', icon: <RobotOutlined />, label: '模型管理' },
      { key: '/benchmarks', icon: <FileSearchOutlined />, label: '评测资产' },
    ],
  },
  {
    type: 'group' as const,
    label: '评测执行',
    children: [
      { key: '/tasks', icon: <FundProjectionScreenOutlined />, label: '评测任务' },
      { key: '/results', icon: <FileDoneOutlined />, label: '结果查询' },
      { key: '/reviews', icon: <TeamOutlined />, label: '人工复核' },
      { key: '/judge', icon: <ApiOutlined />, label: 'Judge 配置' },
    ],
  },
  {
    type: 'group' as const,
    label: '报告',
    children: [
      { key: '/reports', icon: <FileTextOutlined />, label: '报告中心' },
    ],
  },
];

const pageTitles: Record<string, { title: string; subtitle: string }> = {
  '/': { title: '评测任务', subtitle: '创建、执行和监控越狱安全评测任务' },
  '/statistics': { title: '统计分析', subtitle: '查看攻击成功率、Judge 判定和数据集类型分布' },
  '/models': { title: '模型管理', subtitle: '配置被测模型和 Judge 模型适配器' },
  '/benchmarks': { title: '评测资产', subtitle: '管理种子问题、数据集和官方攻击模板' },
  '/tasks': { title: '评测任务', subtitle: '创建、执行和监控越狱安全评测任务' },
  '/results': { title: '结果查询', subtitle: '查看逐条评测结果、Judge 判断和规则命中' },
  '/reviews': { title: '人工复核', subtitle: '处理低可信度、规则冲突和边界结果' },
  '/judge': { title: 'Judge 配置', subtitle: '配置 Judge 模型、规则策略和可信度计算' },
  '/reports': { title: '报告中心', subtitle: '生成、查询和下载报告，并查看系统文件台账' },
};

export function AppLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const healthQuery = useQuery({ queryKey: ['health'], queryFn: getHealth, retry: false });
  const serviceDegraded = healthQuery.data?.status === 'degraded';

  const selectedKey = useMemo(() => {
    const path = location.pathname;
    if (path.startsWith('/tasks/')) return '/tasks';
    if (path.startsWith('/results/')) return '/results';
    return path === '/' ? '/' : `/${path.split('/')[1]}`;
  }, [location.pathname]);

  const current = pageTitles[selectedKey] ?? pageTitles['/'];

  return (
    <Layout className="app-shell">
      <Sider
        className="app-sider"
        width={258}
        collapsedWidth={76}
        collapsible
        collapsed={collapsed}
        trigger={null}
        theme="dark"
        breakpoint="lg"
        onBreakpoint={(broken) => setCollapsed(broken)}
      >
        <div className="brand">
          <div className="brand-mark">
            <SafetyCertificateOutlined />
          </div>
          {!collapsed ? (
            <div>
              <div className="brand-title">LLM Guard</div>
              <div className="brand-subtitle">越狱攻击安全评测平台</div>
            </div>
          ) : null}
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selectedKey]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>

      <Layout>
        <Header className="app-header">
          <Flex align="center" gap={14}>
            <Tooltip title={collapsed ? '展开侧边栏' : '收起侧边栏'}>
              <Button
                type="text"
                icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
                onClick={() => setCollapsed((value) => !value)}
              />
            </Tooltip>
            <div>
              <div className="header-title">{current.title}</div>
              <div className="header-subtitle">{current.subtitle}</div>
            </div>
          </Flex>

          <Space size={14}>
            <Tooltip
              title={
                healthQuery.isError
                  ? '后端未连接'
                  : serviceDegraded
                    ? '数据库或 Redis 不可用，任务可能无法执行'
                    : '后端服务正常'
              }
            >
              <Tag className="soft-tag" color={healthQuery.isError ? 'error' : serviceDegraded ? 'warning' : 'success'}>
                <Badge status={healthQuery.isError ? 'error' : serviceDegraded ? 'warning' : 'processing'} />
                {healthQuery.isError ? '后端离线' : serviceDegraded ? '服务降级' : '本地服务'}
              </Tag>
            </Tooltip>
            <Tag className="soft-tag" color="blue">
              无登录模式
            </Tag>
            <Avatar style={{ background: 'linear-gradient(135deg, #4f6ef7, #7c4dff)' }}>安</Avatar>
            {!collapsed ? <Text type="secondary">安全评测员</Text> : null}
          </Space>
        </Header>

        <Content className="app-content">
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}

