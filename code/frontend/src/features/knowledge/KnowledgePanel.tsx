import { useState } from 'react';
import {
  CheckCircleOutlined,
  FileSearchOutlined,
  InfoCircleOutlined,
  LinkOutlined,
  SearchOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import { Button, Empty, Input, Select, Spin, Tag, Tooltip } from 'antd';
import type { KnowledgeIndexStatus, KnowledgeSearchResponse, KnowledgeSearchResult } from '../../api/contracts';

const ROLE_LABELS: Record<string, string> = {
  official_standard: '官方标准',
  official_policy: '官方政策',
  regulatory_guidance: '监管指引',
  official_methodology: '官方方法学',
  research_literature: '研究证据',
  other: '其他来源',
};

function visibilityLabel(value: string): string {
  return value === 'metadata_only' ? '仅元数据' : value === 'searchable_candidate' ? '候选正文' : value;
}

function compactVersion(value?: string): string {
  if (!value) return '未冻结';
  return value.length > 24 ? `${value.slice(0, 12)}…${value.slice(-8)}` : value;
}

function safeHttpUrl(value?: string | null): string | null {
  if (!value) return null;
  try {
    const parsed = new URL(value);
    return parsed.protocol === 'http:' || parsed.protocol === 'https:' ? value : null;
  } catch {
    return null;
  }
}

function EvidenceCard({ result }: { result: KnowledgeSearchResult }) {
  const [expanded, setExpanded] = useState(false);
  const metadataOnly = result.visibility === 'metadata_only' || result.result_type === 'source_metadata';
  return (
    <article className={`knowledge-evidence-card ${metadataOnly ? 'metadata-only' : ''}`}>
      <button className="knowledge-evidence-toggle" onClick={() => setExpanded((value) => !value)} aria-expanded={expanded}>
        <span className="knowledge-evidence-icon">{metadataOnly ? <InfoCircleOutlined /> : <FileSearchOutlined />}</span>
        <span className="knowledge-evidence-main"><strong>{result.title || result.source_id}</strong><small>{result.source_id} · {ROLE_LABELS[result.source_role] ?? result.source_role}</small></span>
        <span className="knowledge-evidence-chevron">{expanded ? '收起' : '展开'}</span>
      </button>
      <div className="knowledge-evidence-meta"><Tag bordered={false}>{visibilityLabel(result.visibility)}</Tag><span>{result.verification_status}</span>{result.date_uncertain && <Tag bordered={false} color="warning">年份不确定</Tag>}</div>
      {expanded && <div className="knowledge-evidence-detail">
        <div className="knowledge-detail-row"><span>版本</span><strong>{result.version || '未记录'}</strong></div>
        <div className="knowledge-detail-row"><span>定位</span><strong>{result.locator || '未提供可复核定位'}</strong></div>
        {metadataOnly ? <div className="knowledge-boundary metadata"><InfoCircleOutlined /> 正文不可用/待定位，不生成伪摘要。</div> : <p className="knowledge-excerpt">{result.excerpt || '当前切片没有可展示正文。'}</p>}
        <div className="knowledge-boundary"><WarningOutlined /> {result.use_boundary}</div>
        {safeHttpUrl(result.official_url) && <a className="knowledge-source-link" href={safeHttpUrl(result.official_url) ?? undefined} target="_blank" rel="noreferrer"><LinkOutlined /> 打开官方来源</a>}
      </div>}
    </article>
  );
}

export function KnowledgePanel({
  index,
  response,
  query,
  sourceRoles,
  loading,
  error,
  onQueryChange,
  onSourceRolesChange,
  onSearch,
}: {
  index: KnowledgeIndexStatus | null;
  response: KnowledgeSearchResponse | null;
  query: string;
  sourceRoles: string[];
  loading: boolean;
  error: string;
  onQueryChange: (value: string) => void;
  onSourceRolesChange: (value: string[]) => void;
  onSearch: () => void;
}) {
  return <div className="knowledge-panel" aria-label="知识依据面板">
    <div className="knowledge-panel-intro"><div className="knowledge-panel-title"><span className="knowledge-spark"><CheckCircleOutlined /></span><div><strong>知识依据</strong><small>只读 · 可追溯 · 运行隔离</small></div></div><Tooltip title="普通检索不包含候选治理记录、转型规划结论和具体排放因子值"><InfoCircleOutlined className="knowledge-info" /></Tooltip></div>
    <p className="knowledge-panel-note">按当前企业行业筛选本地准入知识。结果是候选证据，不会自动改变事实、评分或授信结论。</p>
    <div className="knowledge-search-box"><Input value={query} onChange={(event) => onQueryChange(event.target.value)} onPressEnter={onSearch} placeholder="检索标准、条款或证据…" aria-label="知识依据检索" maxLength={1000} /><Button type="primary" icon={loading ? <Spin size="small" /> : <SearchOutlined />} onClick={onSearch} disabled={!query.trim() || loading} aria-label="检索知识依据" /></div>
    <Select mode="multiple" allowClear value={sourceRoles} onChange={onSourceRolesChange} className="knowledge-role-filter" placeholder="来源角色：全部" options={Object.entries(ROLE_LABELS).map(([value, label]) => ({ value, label }))} aria-label="知识来源角色筛选" />
    <div className="knowledge-index-line"><span><span className={`knowledge-status-dot ${index?.available ? 'ready' : ''}`} />{index?.available ? '本地索引已就绪' : '索引尚未构建'}</span><span title={index?.index_version_id}>M5 · {compactVersion(index?.index_version_id)}</span></div>
    {error && <div className="knowledge-error"><WarningOutlined /> {error}</div>}
    {response && <>
      <div className="knowledge-result-head"><span>检索结果 <strong>{response.results.length}</strong></span><span>{response.industry_scope.join(' · ')}</span></div>
      <div className="knowledge-frozen-meta">冻结版本 {compactVersion(response.index_version_id)} · 准入 {response.allowlist_version} · 截止 {response.knowledge_as_of}</div>
      {response.warnings.length > 0 && <div className="knowledge-warning-list">{response.warnings.map((warning) => <div className="knowledge-warning" key={warning}><WarningOutlined /><span>{warning}</span></div>)}</div>}
      {response.results.length ? <div className="knowledge-result-list">{response.results.map((result) => <EvidenceCard key={`${result.source_id}-${result.chunk_id ?? result.document_id}`} result={result} />)}</div> : <div className="knowledge-empty"><Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前准入范围内没有可追溯结果" /><small>可补充来源、版本或精确定位后再检索。</small></div>}
    </>}
    {!response && !loading && <div className="knowledge-placeholder"><FileSearchOutlined /><span>输入一个问题，查看当前运行冻结的来源与定位。</span></div>}
  </div>;
}
