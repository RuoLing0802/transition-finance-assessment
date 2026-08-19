import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { StatusBadge } from './StatusBadge';

describe('StatusBadge', () => {
  it('用明确的中文状态表达未实现能力', () => {
    render(<StatusBadge status="not_calculable" />);
    expect(screen.getByText('暂不可计算')).toBeInTheDocument();
  });

  it('用成功状态表达已完成的数据阶段', () => {
    render(<StatusBadge status="done" />);
    expect(screen.getByText('已完成')).toBeInTheDocument();
  });
});
