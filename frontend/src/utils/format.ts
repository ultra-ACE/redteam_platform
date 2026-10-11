import dayjs from 'dayjs';

export const formatDateTime = (value?: string | null) => {
  if (!value) return '-';
  return dayjs(value).format('YYYY-MM-DD HH:mm:ss');
};

export const formatPercent = (value?: number | null) => {
  if (value === undefined || value === null) return '-';
  return `${(value * 100).toFixed(1)}%`;
};

export const formatScore = (value?: number | null) => {
  if (value === undefined || value === null) return '-';
  return Number(value).toFixed(1);
};

export const riskColor = (level?: string | null) => {
  switch (level) {
    case 'critical':
      return '#ef4444';
    case 'high':
      return '#f97316';
    case 'medium':
      return '#eab308';
    case 'low':
      return '#22c55e';
    case 'info':
      return '#38bdf8';
    default:
      return '#94a3b8';
  }
};

export const taskStatusColor = (status?: string | null) => {
  switch (status) {
    case 'succeeded':
      return 'success';
    case 'running':
      return 'processing';
    case 'queued':
      return 'warning';
    case 'failed':
      return 'error';
    case 'partially_failed':
      return 'volcano';
    case 'cancelled':
      return 'default';
    default:
      return 'default';
  }
};

export const verdictColor = (verdict?: string | null) => {
  switch (verdict) {
    case 'unsafe':
      return 'error';
    case 'safe':
      return 'success';
    case 'uncertain':
      return 'warning';
    default:
      return 'default';
  }
};

/**
 * 来源编号来自数据集自身，个别数据集会把整段文本当成编号，
 * 展示时统一截断，完整值通过 title 提示给出。
 */
export const shortenId = (value?: string | null, max = 24) => {
  if (!value) return '-';
  return value.length <= max ? value : `${value.slice(0, max)}…`;
};
