import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { AssessmentPipeline } from './AssessmentPipeline';

describe('AssessmentPipeline', () => {
  it('保留碳核算和授信的真实未就绪状态', () => {
    render(<AssessmentPipeline stages={[
      { key: 'carbon', label: '碳排放测算', status: 'not_calculable', detail: '缺少正式依据' },
      { key: 'credit', label: '信贷支持建议', status: 'not_implemented', detail: '尚未实现' },
    ]} />);
    expect(screen.getByText('碳排放测算')).toBeInTheDocument();
    expect(screen.getByText('暂不可计算')).toBeInTheDocument();
    expect(screen.getByText('信贷支持建议')).toBeInTheDocument();
    expect(screen.getByText('待建设')).toBeInTheDocument();
  });
});
