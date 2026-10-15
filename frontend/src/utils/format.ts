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

export const taskStatusColor = (status?: string | null) => {
  switch (status) {
    case 'succeeded':
      return 'success';
    case 'running':
      return 'processing';
    case 'queued':
      return 'warning';
    case 'paused':
      return 'default';
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
