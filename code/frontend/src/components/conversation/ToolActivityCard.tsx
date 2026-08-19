import { CaretRightOutlined, LoadingOutlined, ToolOutlined } from '@ant-design/icons';
import { Collapse, Spin } from 'antd';
import type { ProcessSummary } from '../../api/contracts';

export function ToolActivityCard({ summary, processing }: { summary: ProcessSummary | null; processing: boolean }) {
  const steps = summary?.steps ?? [];
  if (!steps.length && !processing) return null;
  return (
    <div className="activity-card">
      <Collapse
        ghost
        expandIcon={({ isActive }) => <CaretRightOutlined rotate={isActive ? 90 : 0} />}
        items={[{
          key: 'activity',
          label: <span className="activity-label"><ToolOutlined /> {processing ? '正在处理当前评估' : '查看本次处理过程'} <em>{processing ? <Spin indicator={<LoadingOutlined spin />} size="small" /> : `${steps.length} 步`}</em></span>,
          children: (
            <div className="activity-steps">
              {steps.map((step, index) => <div className={`activity-step activity-${step.status}`} key={`${step.label}-${index}`}><span className="step-dot" />{step.label}</div>)}
              <small>{summary?.notice ?? '仅展示可解释的处理摘要，不包含模型私有思维链。'}</small>
            </div>
          ),
        }]}
      />
    </div>
  );
}
