import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { WorkflowControlCard } from './WorkflowControlCard';
import type { WorkflowCheckpoint, WorkflowDefinition } from '../../api/contracts';

const definition: WorkflowDefinition = {
  workflow_name: 'baseline_review',
  label: '基础评估审查',
  description: '测试流程',
  nodes: ['follow_up', 'human_review'],
  pause_points: ['follow_up', 'human_review'],
};

function checkpoint(status: WorkflowCheckpoint['status']): WorkflowCheckpoint {
  return {
    checkpoint_id: 'ckpt-test',
    assessment_run_id: 'run-test',
    enterprise_id: 'enterprise-test',
    enterprise_code: 'TFTEST01',
    workflow_name: 'baseline_review',
    thread_id: 'run-test:baseline_review',
    status,
    current_node: status === 'waiting_for_input' ? 'human_review' : null,
    version: 3,
    state: {
      follow_up_questions: status === 'waiting_for_input' ? ['请补充材料'] : [],
      completed_nodes: ['follow_up'],
    },
  };
}

describe('WorkflowControlCard', () => {
  afterEach(() => cleanup());

  it('将待补充状态区分为提交回答和明确暂不补充', async () => {
    const user = userEvent.setup();
    const onResume = vi.fn();
    render(
      <WorkflowControlCard
        definitions={[definition]}
        workflows={[checkpoint('waiting_for_input')]}
        busy={null}
        onStart={vi.fn()}
        onPause={vi.fn()}
        onResume={onResume}
        onReview={vi.fn()}
      />,
    );

    expect(screen.getByRole('button', { name: /提交补充回答/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '确认暂不补充' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '确认暂不补充' }));
    expect(onResume).toHaveBeenCalledWith(expect.objectContaining({ status: 'waiting_for_input' }), true);
  });

  it('只在待人工确认状态显示人工决策按钮', () => {
    render(
      <WorkflowControlCard
        definitions={[definition]}
        workflows={[checkpoint('waiting_human_review')]}
        busy={null}
        onStart={vi.fn()}
        onPause={vi.fn()}
        onResume={vi.fn()}
        onReview={vi.fn()}
      />,
    );

    expect(screen.getByRole('button', { name: /人工通过/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /要求补充/ })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '确认暂不补充' })).not.toBeInTheDocument();
  });
});
