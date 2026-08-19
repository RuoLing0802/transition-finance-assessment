import type { ReactNode } from 'react';
import { CheckCircleFilled, ClockCircleOutlined, ExclamationCircleFilled, MinusCircleOutlined, StopFilled } from '@ant-design/icons';
import { Tag } from 'antd';

export type AppStatus = 'done' | 'warning' | 'blocked' | 'not_calculable' | 'not_implemented' | 'pending' | 'running' | 'error';

const STATUS_META: Record<AppStatus, { label: string; color: string; icon: ReactNode }> = {
  done: { label: '已完成', color: 'success', icon: <CheckCircleFilled /> },
  warning: { label: '有提示', color: 'warning', icon: <ExclamationCircleFilled /> },
  blocked: { label: '已阻断', color: 'error', icon: <StopFilled /> },
  not_calculable: { label: '暂不可计算', color: 'default', icon: <MinusCircleOutlined /> },
  not_implemented: { label: '待建设', color: 'default', icon: <MinusCircleOutlined /> },
  pending: { label: '待处理', color: 'processing', icon: <ClockCircleOutlined /> },
  running: { label: '处理中', color: 'processing', icon: <ClockCircleOutlined /> },
  error: { label: '失败', color: 'error', icon: <ExclamationCircleFilled /> },
};

export function StatusBadge({ status, compact = false }: { status: AppStatus; compact?: boolean }) {
  const meta = STATUS_META[status] ?? STATUS_META.pending;
  return <Tag className={`status-tag status-${status}`} bordered={false} icon={meta.icon}>{compact ? meta.label : meta.label}</Tag>;
}

export function statusLabel(status: string): string {
  return STATUS_META[status as AppStatus]?.label ?? status;
}
