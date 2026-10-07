import type { ThemeConfig } from 'antd';

export const appTheme: ThemeConfig = {
  token: {
    colorPrimary: '#4f6ef7',
    colorInfo: '#4f6ef7',
    colorSuccess: '#22c55e',
    colorWarning: '#f59e0b',
    colorError: '#ef4444',
    borderRadius: 12,
    colorBgLayout: '#f5f7fb',
    fontFamily:
      'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif',
  },
  components: {
    Layout: {
      siderBg: '#0b1220',
      headerBg: 'rgba(255,255,255,0.88)',
      bodyBg: '#f5f7fb',
      headerHeight: 72,
    },
    Menu: {
      darkItemBg: '#0b1220',
      darkSubMenuItemBg: '#0b1220',
      darkItemSelectedBg: 'rgba(79,110,247,0.22)',
      darkItemSelectedColor: '#ffffff',
      darkItemColor: '#94a3b8',
      itemBorderRadius: 10,
    },
    Card: {
      borderRadiusLG: 16,
      boxShadowTertiary: '0 10px 30px rgba(15, 23, 42, 0.06)',
    },
    Table: {
      headerBg: '#f8fafc',
      headerColor: '#475569',
      rowHoverBg: '#f8faff',
    },
  },
};
