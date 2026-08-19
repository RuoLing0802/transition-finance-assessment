import type { ReactNode } from 'react';
import { ArrowRightOutlined, CheckCircleFilled, ExclamationCircleFilled, MinusCircleOutlined, StopFilled } from '@ant-design/icons';
import type { AppStatus } from '../common/StatusBadge';
import { StatusBadge } from '../common/StatusBadge';

export type PipelineStage = {
  key: string;
  label: string;
  status: AppStatus;
  detail: string;
};

const ICONS: Record<AppStatus, ReactNode> = {
  done: <CheckCircleFilled />,
  warning: <ExclamationCircleFilled />,
  blocked: <StopFilled />,
  not_calculable: <MinusCircleOutlined />,
  not_implemented: <MinusCircleOutlined />,
  pending: <ArrowRightOutlined />,
  running: <ArrowRightOutlined />,
  error: <ExclamationCircleFilled />,
};

export function AssessmentPipeline({ stages }: { stages: PipelineStage[] }) {
  return (
    <div className="pipeline-list" aria-label="评估流程状态">
      {stages.map((stage, index) => (
        <div className="pipeline-row" key={stage.key}>
          <div className={`pipeline-icon pipeline-icon-${stage.status}`}>{ICONS[stage.status]}</div>
          <div className="pipeline-copy">
            <div className="pipeline-heading"><strong>{stage.label}</strong><StatusBadge status={stage.status} compact /></div>
            <p>{stage.detail}</p>
          </div>
          {index < stages.length - 1 && <span className="pipeline-line" aria-hidden="true" />}
        </div>
      ))}
    </div>
  );
}
