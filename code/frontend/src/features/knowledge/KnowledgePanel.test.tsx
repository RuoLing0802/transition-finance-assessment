import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { KnowledgePanel } from './KnowledgePanel';

describe('KnowledgePanel', () => {
  it('shows the frozen version and every warning while refusing unsafe URLs', () => {
    render(<KnowledgePanel
      index={{ available: true, fts5_available: true, index_version_id: 'm5-index-frozen', allowlist_version: 'M5-ALLOWLIST-v1' }}
      response={{
        retrieval_id: 'ret-1', assessment_run_id: 'run-a', workspace_id: 'ws-a', enterprise_id: 'ent-a', enterprise_code: 'TF0001',
        index_version_id: 'm5-index-frozen', allowlist_version: 'M5-ALLOWLIST-v1', knowledge_as_of: '2026-08-22', industry_scope: ['冶金行业铜'], query: '铜行业 节能',
        warnings: ['证据不足', '需要人工复核'], degraded_mode: null, data_notice: '模拟数据', results: [{
          result_type: 'source_metadata', source_id: 'STD-META', title: '待定位标准', publisher: '测试', version: '2025', locator: null, excerpt: null,
          source_role: 'official_standard', verification_status: '部分核验', visibility: 'metadata_only', use_boundary: '不得生成伪正文', official_url: 'javascript:alert(1)', industry_scope: ['global'], match_tier: 0,
        }],
      }}
      query="铜行业 节能" sourceRoles={[]} loading={false} error="" onQueryChange={vi.fn()} onSourceRolesChange={vi.fn()} onSearch={vi.fn()}
    />);
    expect(screen.getByText(/冻结版本/)).toBeInTheDocument();
    expect(screen.getByText('证据不足')).toBeInTheDocument();
    expect(screen.getByText('需要人工复核')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /官方来源/ })).not.toBeInTheDocument();
  });
});
