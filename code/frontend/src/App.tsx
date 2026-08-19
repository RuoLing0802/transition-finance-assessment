import { useEffect, useMemo, useState } from 'react';
import ReactECharts from 'echarts-for-react';
import {
  App as AntdApp,
  Avatar,
  Button,
  Collapse,
  ConfigProvider,
  Empty,
  Input,
  Modal,
  Progress,
  Select,
  Spin,
  Tag,
  Tooltip,
  message,
} from 'antd';
import {
  AppstoreOutlined,
  ArrowDownOutlined,
  ArrowUpOutlined,
  BarChartOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  CloseOutlined,
  DatabaseOutlined,
  FileSearchOutlined,
  FileTextOutlined,
  FundOutlined,
  InfoCircleOutlined,
  LockOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  PaperClipOutlined,
  PauseCircleOutlined,
  PlusOutlined,
  ReloadOutlined,
  SendOutlined,
  SettingOutlined,
  SlidersOutlined,
  SafetyCertificateOutlined,
  SearchOutlined,
  ThunderboltOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { api } from './api/client';
import type {
  AssessmentRun,
  Attachment,
  CompanyDetail,
  Message,
  ModelOption,
  ProcessSummary,
  SourceBatch,
  Workspace,
  WorkflowCheckpoint,
  WorkflowDefinition,
} from './api/contracts';
import { AssessmentPipeline, type PipelineStage } from './components/inspector/AssessmentPipeline';
import { StatusBadge, type AppStatus } from './components/common/StatusBadge';
import { ToolActivityCard } from './components/conversation/ToolActivityCard';
import { WorkflowControlCard } from './components/workflow/WorkflowControlCard';
import './styles.css';

const DEFAULT_WORKSPACE_NAME = '转型金融评估工作台';

function valueOf(record: Record<string, unknown> | undefined, key: string): string {
  const value = record?.[key];
  return value === undefined || value === null || value === '' ? '—' : String(value);
}

function formatNumber(value: unknown): string {
  if (typeof value !== 'number' || Number.isNaN(value)) return '—';
  return new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 }).format(value);
}

function formatRate(value: unknown): string {
  if (typeof value !== 'number' || Number.isNaN(value)) return '—';
  return `${value > 0 ? '+' : ''}${(value * 100).toFixed(1)}%`;
}

function statusForQuality(detail: CompanyDetail | null): AppStatus {
  const issues = detail?.analysis.quality_issues ?? [];
  if (issues.some((issue) => issue.severity === 'error')) return 'blocked';
  return issues.length ? 'warning' : 'done';
}

function stageDetail(stage: PipelineStage): string {
  return stage.detail;
}

function InlineMessage({ text }: { text: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return <>{parts.map((part, index) => part.startsWith('**') && part.endsWith('**') ? <strong key={`${part}-${index}`}>{part.slice(2, -2)}</strong> : part)}</>;
}

function MessageContent({ content }: { content: string }) {
  return <div className="message-body">{content.split('\n').map((line, index) => {
    const key = `${index}-${line}`;
    if (/^#{2,4}\s/.test(line)) return <h4 key={key}><InlineMessage text={line.replace(/^#{2,4}\s/, '')} /></h4>;
    if (/^\|/.test(line) && !/^\|[-|\s]+\|$/.test(line)) return <div className="table-line" key={key}>{line.split('|').filter(Boolean).map((cell) => cell.trim()).join('  ·  ')}</div>;
    if (/^[-—]\s/.test(line)) return <div className="list-line" key={key}><span>•</span><InlineMessage text={line.replace(/^[-—]\s/, '')} /></div>;
    if (/^\d+[.)]\s/.test(line)) return <div className="list-line numbered" key={key}><InlineMessage text={line} /></div>;
    return <p key={key}>{line ? <InlineMessage text={line} /> : '\u00a0'}</p>;
  })}</div>;
}

function App() {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [runs, setRuns] = useState<AssessmentRun[]>([]);
  const [run, setRun] = useState<AssessmentRun | null>(null);
  const [sourceBatch, setSourceBatch] = useState<SourceBatch | null>(null);
  const [detail, setDetail] = useState<CompanyDetail | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [processSummary, setProcessSummary] = useState<ProcessSummary | null>(null);
  const [workflowDefinitions, setWorkflowDefinitions] = useState<WorkflowDefinition[]>([]);
  const [workflows, setWorkflows] = useState<WorkflowCheckpoint[]>([]);
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [models, setModels] = useState<ModelOption[]>([]);
  const [selectedModel, setSelectedModel] = useState<string | undefined>();
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [runLoading, setRunLoading] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState('');
  const [composer, setComposer] = useState('');
  const [workspaceModalOpen, setWorkspaceModalOpen] = useState(false);
  const [newWorkspaceName, setNewWorkspaceName] = useState('');
  const [runModalOpen, setRunModalOpen] = useState(false);
  const [newRunCode, setNewRunCode] = useState('TF0001');
  const [newRunName, setNewRunName] = useState('');
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [capabilities, setCapabilities] = useState<Record<string, unknown> | null>(null);
  const [workflowBusy, setWorkflowBusy] = useState<string | null>(null);

  const availableCodes = sourceBatch?.available_company_codes ?? ['TF0001', 'TF0002'];
  const analysis = detail?.analysis;
  const basic = analysis?.input_data?.basic_info;
  const supplement = analysis?.input_data?.supplement_info;
  const trend = analysis?.energy_trend;
  const qualityIssues = analysis?.quality_issues ?? [];
  const catalog = analysis?.catalog_matches;
  const reference = analysis?.reference_comparison;

  const pipeline = useMemo<PipelineStage[]>(() => {
    const qualityStatus = statusForQuality(detail);
    const catalogStatus = catalog?.status === '候选已生成' ? 'done' : catalog ? 'warning' : 'pending';
    return [
      { key: 'enterprise', label: '企业数据', status: detail ? 'done' : 'pending', detail: detail ? '三张输入表已按企业代号关联' : '等待选择评估运行' },
      { key: 'quality', label: '数据质量', status: detail ? qualityStatus : 'pending', detail: detail ? `${qualityIssues.length ? `发现 ${qualityIssues.length} 项待处理问题` : '未发现已登记质量问题'}` : '等待企业数据载入' },
      { key: 'evidence', label: '证据审查', status: attachments.length ? 'done' : detail ? 'warning' : 'pending', detail: attachments.length ? `${attachments.length} 个补充材料已登记` : '补充材料可在对话区上传' },
      { key: 'carbon', label: '碳排放测算', status: 'not_calculable', detail: '缺少组织边界、Scope、折标系数和排放因子版本' },
      { key: 'benchmark', label: '行业对标', status: 'not_implemented', detail: '正式行业基准方法尚未建设' },
      { key: 'transition', label: '转型路径识别', status: catalogStatus as AppStatus, detail: catalog ? `仅展示 ${catalog.candidates?.length ?? 0} 条目录候选，不代表正式行为识别` : '等待目录候选' },
      { key: 'score', label: '转型评分', status: 'pending', detail: '评分方法、权重和阈值待正式确认' },
      { key: 'credit', label: '信贷支持建议', status: 'not_implemented', detail: '本系统不输出授信通过或拒绝结论' },
    ];
  }, [attachments.length, catalog, detail, qualityIssues.length]);

  const energyChartOption = useMemo(() => {
    const resources = (trend?.resources ?? []).filter((item) => typeof item['2024'] === 'number' || typeof item['2025'] === 'number').slice(0, 7);
    return {
      animationDuration: 500,
      grid: { left: 40, right: 12, top: 16, bottom: 34 },
      tooltip: { trigger: 'axis', valueFormatter: (value: number) => formatNumber(value) },
      legend: { bottom: 0, itemWidth: 10, itemHeight: 10, textStyle: { color: '#69756d', fontSize: 11 } },
      xAxis: { type: 'category', data: resources.map((item) => item.name), axisLabel: { color: '#69756d', fontSize: 10, interval: 0, rotate: resources.length > 4 ? 22 : 0 }, axisLine: { lineStyle: { color: '#dfe5df' } } },
      yAxis: { type: 'value', axisLabel: { color: '#8a968e', fontSize: 10 }, splitLine: { lineStyle: { color: '#edf0ec' } } },
      series: [
        { name: '2024', type: 'bar', barMaxWidth: 16, data: resources.map((item) => item['2024'] ?? null), itemStyle: { color: '#a6c9bc', borderRadius: [4, 4, 0, 0] } },
        { name: '2025', type: 'bar', barMaxWidth: 16, data: resources.map((item) => item['2025'] ?? null), itemStyle: { color: '#1f6a5a', borderRadius: [4, 4, 0, 0] } },
      ],
    };
  }, [trend]);

  async function bootstrap() {
    setLoading(true);
    setError('');
    try {
      const [workspacePayload, sourcePayload, modelPayload, capabilityPayload] = await Promise.all([
        api.listWorkspaces(),
        api.getDefaultSourceBatch(),
        api.getModels(),
        api.getParserCapabilities(),
      ]);
      let nextWorkspace = workspacePayload.workspaces[0];
      let nextWorkspaces = workspacePayload.workspaces;
      if (!nextWorkspace) {
        nextWorkspace = await api.createWorkspace(DEFAULT_WORKSPACE_NAME);
        nextWorkspaces = [nextWorkspace];
      }
      setWorkspaces(nextWorkspaces);
      setWorkspace(nextWorkspace);
      setSourceBatch(sourcePayload);
      setModels(modelPayload.models);
      setSelectedModel(modelPayload.default_model_id ?? modelPayload.models[0]?.model_id);
      setCapabilities(capabilityPayload);
      await loadRuns(nextWorkspace.workspace_id, undefined, nextWorkspaces);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '工作台初始化失败');
    } finally {
      setLoading(false);
    }
  }

  async function loadRuns(workspaceId: string, preferredRunId?: string, workspaceList = workspaces) {
    setRunLoading(true);
    try {
      const payload = await api.listRuns(workspaceId);
      setRuns(payload.runs);
      const storedRunId = preferredRunId ?? (workspaceList.find((item) => item.workspace_id === workspaceId)?.last_active_run_id || localStorage.getItem(`tf-active-run:${workspaceId}`) || undefined);
      const nextRun = payload.runs.find((item) => item.assessment_run_id === storedRunId) ?? payload.runs[0] ?? null;
      setRun(nextRun);
      if (nextRun) localStorage.setItem(`tf-active-run:${workspaceId}`, nextRun.assessment_run_id);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '评估运行加载失败');
    } finally {
      setRunLoading(false);
    }
  }

  async function loadRunData(nextRun: AssessmentRun) {
    setRunLoading(true);
    setError('');
    try {
      const [nextDetail, messagePayload, summary, attachmentPayload, workflowPayload] = await Promise.all([
        api.getCompanyDetail(nextRun.assessment_run_id),
        api.listMessages(nextRun.assessment_run_id),
        api.getProcessSummary(nextRun.assessment_run_id),
        api.listAttachments(nextRun.assessment_run_id),
        api.listWorkflows(nextRun.assessment_run_id),
      ]);
      setDetail(nextDetail);
      setMessages(messagePayload.messages);
      setProcessSummary(summary);
      setAttachments(attachmentPayload.attachments);
      setWorkflowDefinitions(workflowPayload.definitions);
      setWorkflows(workflowPayload.workflows);
      const configuredModel = String(nextRun.model_config?.model_id ?? '');
      if (configuredModel && models.some((item) => item.model_id === configuredModel)) setSelectedModel(configuredModel);
    } catch (cause) {
      setDetail(null);
      setWorkflowDefinitions([]);
      setWorkflows([]);
      setError(cause instanceof Error ? cause.message : '当前评估运行加载失败');
    } finally {
      setRunLoading(false);
    }
  }

  useEffect(() => { void bootstrap(); }, []);
  useEffect(() => {
    if (run) void loadRunData(run);
  }, [run?.assessment_run_id]);

  async function selectWorkspace(id: string) {
    const nextWorkspace = workspaces.find((item) => item.workspace_id === id);
    if (!nextWorkspace) return;
    setWorkspace(nextWorkspace);
    setDetail(null);
    await loadRuns(id);
  }

  async function selectRun(nextRun: AssessmentRun) {
    setRun(nextRun);
    setDetail(null);
    if (workspace) localStorage.setItem(`tf-active-run:${workspace.workspace_id}`, nextRun.assessment_run_id);
  }

  async function createWorkspace() {
    if (!newWorkspaceName.trim()) return;
    try {
      const created = await api.createWorkspace(newWorkspaceName.trim());
      const nextList = [created, ...workspaces];
      setWorkspaces(nextList);
      setWorkspace(created);
      setRuns([]);
      setRun(null);
      setNewWorkspaceName('');
      setWorkspaceModalOpen(false);
      message.success('工作空间已创建');
    } catch (cause) {
      message.error(cause instanceof Error ? cause.message : '工作空间创建失败');
    }
  }

  async function createRun() {
    if (!workspace || !sourceBatch) {
      message.error('默认配套数据尚未准备好，请稍后重试');
      return;
    }
    try {
      const created = await api.createRun(workspace.workspace_id, {
        enterprise_code: newRunCode,
        source_batch_id: sourceBatch.source_batch_id,
        run_name: newRunName.trim() || `${newRunCode} 企业评估`,
        model_config: { mode: selectedModel ? 'auto' : 'offline', ...(selectedModel ? { model_id: selectedModel } : {}) },
        basic_info_index: { 企业代号: newRunCode, 索引来源: '基本信息' },
      });
      setRuns((current) => [created, ...current.filter((item) => item.assessment_run_id !== created.assessment_run_id)]);
      setRun(created);
      setNewRunName('');
      setRunModalOpen(false);
      message.success(`${newRunCode} 评估运行已建立`);
    } catch (cause) {
      message.error(cause instanceof Error ? cause.message : '运行创建失败');
    }
  }

  async function sendMessage() {
    if (!run || !composer.trim() || processing) return;
    const content = composer.trim();
    setComposer('');
    setProcessing(true);
    try {
      await api.turn(run.assessment_run_id, content, selectedModel);
      await loadRunData(run);
    } catch (cause) {
      setComposer(content);
      message.error(cause instanceof Error ? cause.message : '会话处理失败');
    } finally {
      setProcessing(false);
    }
  }

  async function retryMessage() {
    if (!run || processing) return;
    setProcessing(true);
    try {
      await api.retry(run.assessment_run_id, selectedModel);
      await loadRunData(run);
    } catch (cause) {
      message.error(cause instanceof Error ? cause.message : '重试失败');
    } finally {
      setProcessing(false);
    }
  }

  async function stopMessage() {
    if (!run) return;
    try {
      await api.stop(run.assessment_run_id);
      await loadRunData(run);
    } catch (cause) {
      message.error(cause instanceof Error ? cause.message : '停止请求失败');
    }
  }

  async function handleAttachment(file: File) {
    if (!run) return;
    try {
      await api.uploadAttachment(run.assessment_run_id, file);
      await loadRunData(run);
      message.success('补充材料已登记，等待证据解析状态');
    } catch (cause) {
      message.error(cause instanceof Error ? cause.message : '附件上传失败');
    }
  }

  async function startWorkflow(workflowName: WorkflowCheckpoint['workflow_name']) {
    if (!run) return;
    const actionKey = `start:${workflowName}`;
    setWorkflowBusy(actionKey);
    try {
      await api.startWorkflow(run.assessment_run_id, workflowName);
      await loadRunData(run);
      message.success('M4流程已启动，检查点已保存');
    } catch (cause) {
      message.error(cause instanceof Error ? cause.message : '流程启动失败');
    } finally {
      setWorkflowBusy(null);
    }
  }

  async function pauseWorkflow(workflow: WorkflowCheckpoint) {
    if (!run) return;
    const actionKey = `${workflow.workflow_name}:${workflow.status}`;
    setWorkflowBusy(actionKey);
    try {
      await api.pauseWorkflow(run.assessment_run_id, workflow.workflow_name);
      await loadRunData(run);
      message.success('流程已暂停，当前检查点已保存');
    } catch (cause) {
      message.error(cause instanceof Error ? cause.message : '流程暂停失败');
    } finally {
      setWorkflowBusy(null);
    }
  }

  async function resumeWorkflow(workflow: WorkflowCheckpoint, confirmNoAdditional = false) {
    if (!run) return;
    const answer = composer.trim();
    if (workflow.status === 'waiting_for_input' && !answer && !confirmNoAdditional) {
      message.warning('请先在输入框填写补充回答，或明确确认暂不补充。');
      return;
    }
    if (confirmNoAdditional && answer) {
      message.warning('请清空输入框后再确认暂不补充，不能同时提交两种回应。');
      return;
    }
    if (answer) setComposer('');
    const actionKey = `${workflow.workflow_name}:${workflow.status}`;
    setWorkflowBusy(actionKey);
    try {
      await api.resumeWorkflow(run.assessment_run_id, workflow.workflow_name, answer ? [answer] : [], confirmNoAdditional);
      await loadRunData(run);
      message.success('流程已恢复');
    } catch (cause) {
      if (answer) setComposer(answer);
      message.error(cause instanceof Error ? cause.message : '流程恢复失败');
    } finally {
      setWorkflowBusy(null);
    }
  }

  async function reviewWorkflow(workflow: WorkflowCheckpoint, decision: 'approve' | 'request_changes') {
    if (!run) return;
    const actionKey = `${workflow.workflow_name}:${decision}`;
    setWorkflowBusy(actionKey);
    try {
      await api.reviewWorkflow(run.assessment_run_id, workflow.workflow_name, decision);
      await loadRunData(run);
      message.success(decision === 'approve' ? '人工确认已记录' : '已退回补充流程');
    } catch (cause) {
      message.error(cause instanceof Error ? cause.message : '人工确认失败');
    } finally {
      setWorkflowBusy(null);
    }
  }

  const visibleMessages = messages.filter((item) => item.role !== 'tool' && !['tool_call', 'tool_result'].includes(item.message_type));
  const latestStatus = visibleMessages.filter((item) => item.role !== 'user').at(-1);
  const hasRun = Boolean(run);

  if (loading) {
    return <div className="boot-screen"><div className="boot-mark"><ThunderboltOutlined /></div><Spin size="large" /><p>正在恢复评估工作台…</p></div>;
  }

  return (
    <ConfigProvider theme={{ token: { colorPrimary: '#1f6a5a', colorInfo: '#1f6a5a', borderRadius: 12, fontFamily: '"PingFang SC", "Noto Sans SC", sans-serif', colorText: '#202620', colorBgContainer: '#ffffff' }, components: { Button: { controlHeight: 42, fontWeight: 600 }, Input: { controlHeight: 44 }, Select: { controlHeight: 42 }, Collapse: { contentBg: 'transparent', headerBg: 'transparent' } } }}>
      <AntdApp>
        <div className={`workbench ${leftCollapsed ? 'left-collapsed' : ''} ${rightCollapsed ? 'right-collapsed' : ''}`}>
          <aside className="task-sidebar" aria-label="工作空间和评估运行">
            <div className="brand-row">
              <div className="brand-symbol"><ThunderboltOutlined /></div>
              <div className="brand-copy"><strong>碳迹可循</strong><span>转型金融评估工作台</span></div>
            </div>
            <div className="sidebar-scroll">
              <div className="sidebar-kicker">工作空间</div>
              <div className="workspace-switcher">
                <Select value={workspace?.workspace_id} onChange={selectWorkspace} options={workspaces.map((item) => ({ value: item.workspace_id, label: item.name }))} suffixIcon={<AppstoreOutlined />} aria-label="选择工作空间" />
                <Button type="text" icon={<PlusOutlined />} onClick={() => setWorkspaceModalOpen(true)} aria-label="新建工作空间" />
              </div>
              <Button className="new-assessment" type="primary" block icon={<PlusOutlined />} onClick={() => setRunModalOpen(true)} disabled={!sourceBatch}>新建企业评估</Button>
              <div className="sidebar-section">
                <div className="sidebar-section-heading"><span>当前空间的运行</span><span className="run-count">{runs.length}</span></div>
                <div className="run-list">
                  {runLoading && !runs.length ? <div className="sidebar-loading"><Spin size="small" /> 正在加载</div> : runs.length ? runs.map((item) => (
                    <button className={`run-item ${item.assessment_run_id === run?.assessment_run_id ? 'active' : ''}`} key={item.assessment_run_id} onClick={() => void selectRun(item)}>
                      <span className="run-dot" /><span className="run-copy"><strong>{item.enterprise_code}</strong><small>{item.run_name || '企业评估'}</small></span><StatusBadge status={item.status === 'report_ready' ? 'done' : item.quality_gate_status === 'passed_with_warnings' ? 'warning' : 'pending'} compact />
                    </button>
                  )) : <div className="sidebar-empty">还没有评估运行<br /><span>从默认配套数据开始</span></div>}
                </div>
              </div>
              <div className="sidebar-section recent-section">
                <div className="sidebar-section-heading"><span>本轮工作边界</span></div>
                <div className="boundary-note"><SafetyCertificateOutlined /><span>只展示真实可回放的数据和状态。碳核算、评分与授信结论尚未建设。</span></div>
              </div>
            </div>
            <div className="sidebar-footer">
              <div className="source-mini"><DatabaseOutlined /><span><strong>配套模拟数据</strong><small>默认已准备 · 仅用于开发测试</small></span></div>
              <button className="sidebar-action" onClick={() => setSettingsOpen(true)}><SettingOutlined /><span>设置与诊断</span></button>
            </div>
            <button className="edge-toggle left-edge" onClick={() => setLeftCollapsed((value) => !value)} aria-label={leftCollapsed ? '展开左侧栏' : '收起左侧栏'}>{leftCollapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}</button>
          </aside>

          <main className="main-area">
            <header className="topbar">
              <div className="topbar-context">
                <div className="eyebrow"><span className="live-dot" /> 专业 Agent 工作台 <span className="slash">/</span> {workspace?.name ?? '未选择工作空间'}</div>
                <h1>{run ? `${run.enterprise_code} 企业转型金融评估` : '从一个企业评估开始'}</h1>
                <p>{run ? `${run.run_name || '当前评估运行'} · ${run.rule_version || '规则版本待载入'}` : '默认配套数据已经准备好，选择企业即可开始查看。'}</p>
              </div>
              <div className="topbar-actions">
                <Tooltip title="新建企业评估"><Button className="topbar-icon quick-new-run" type="text" icon={<PlusOutlined />} onClick={() => setRunModalOpen(true)} aria-label="新建企业评估" /></Tooltip>
                {run && <div className="model-control"><span>会话模型</span><Select size="small" value={selectedModel} onChange={setSelectedModel} placeholder="离线基础流程" options={models.map((model) => ({ value: model.model_id, label: model.display_name }))} allowClear aria-label="选择会话模型" /></div>}
                <Tooltip title="收起右侧检查器"><Button className="topbar-icon" type="text" icon={rightCollapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />} onClick={() => setRightCollapsed((value) => !value)} aria-label={rightCollapsed ? '展开右侧检查器' : '收起右侧检查器'} /></Tooltip>
              </div>
            </header>

            <div className="data-ribbon"><DatabaseOutlined /><span>{sourceBatch?.data_notice ?? '命题方脱敏模拟数据，仅用于比赛开发测试，不代表真实企业业务数据。'}</span><Tag bordered={false}>规则 {run?.rule_version ?? 'M3基线'}</Tag></div>
            {error && <div className="error-banner" role="alert"><InfoCircleOutlined /><span>{error}</span><Button type="text" icon={<CloseOutlined />} onClick={() => setError('')} aria-label="关闭错误提示" /></div>}

            {!hasRun ? (
              <section className="empty-workspace">
                <div className="empty-orbit"><div className="orbit-core"><ThunderboltOutlined /></div><span className="orbit-ring ring-one" /><span className="orbit-ring ring-two" /></div>
                <div className="empty-copy"><span className="section-eyebrow">M3 专业评估工作台</span><h2>先选择一家企业，<br /><em>再让数据自己说话。</em></h2><p>系统会从配套工作簿中加载企业事实、质量提示、能耗变化和目录候选。每次评估运行只绑定一家企业，所有消息和证据彼此隔离。</p><Button type="primary" size="large" icon={<PlusOutlined />} onClick={() => setRunModalOpen(true)} disabled={!sourceBatch}>新建企业评估</Button></div>
                <div className="empty-list"><div><CheckCircleOutlined /><span>三张输入表已准备</span></div><div><BarChartOutlined /><span>2024—2025 能耗趋势</span></div><div><SafetyCertificateOutlined /><span>参考结论独立隔离</span></div></div>
              </section>
            ) : (
              <section className="conversation-shell">
                <div className="run-status-strip"><div className="current-enterprise"><Avatar size={34} className="enterprise-avatar">{run?.enterprise_code.slice(-2)}</Avatar><div><span>当前评估企业</span><strong>{run?.enterprise_code} <small>{valueOf(basic, '企业名称') !== '—' ? valueOf(basic, '企业名称') : '配套数据企业'}</small></strong></div></div><div className="run-state"><StatusBadge status={statusForQuality(detail)} /><span>{detail ? '结构化事实已载入' : '正在载入企业事实'}</span></div></div>
                <ToolActivityCard summary={processSummary} processing={processing} />
                <WorkflowControlCard definitions={workflowDefinitions} workflows={workflows} busy={workflowBusy} onStart={(workflowName) => void startWorkflow(workflowName)} onPause={(workflow) => void pauseWorkflow(workflow)} onResume={(workflow, confirmNoAdditional) => void resumeWorkflow(workflow, confirmNoAdditional)} onReview={(workflow, decision) => void reviewWorkflow(workflow, decision)} />
                <div className="conversation-scroll">
                  {!visibleMessages.length && <div className="agent-intro"><div className="agent-avatar"><ThunderboltOutlined /></div><div><strong>我已准备好检查 {run?.enterprise_code}</strong><p>我会先读取当前运行的企业画像、数据质量和能耗变化，再告诉你哪些环节已有依据、哪些环节还缺资料。</p><div className="suggestion-row"><button onClick={() => setComposer('请先概览当前企业的数据质量和能耗变化')}>概览数据质量</button><button onClick={() => setComposer('请查看转型目录候选')}>查看目录候选</button><button onClick={() => setComposer('哪些材料还需要补充？')}>查看待补材料</button></div></div></div>}
                  {visibleMessages.map((item) => <div className={`chat-message ${item.role}`} key={item.message_id}><div className="message-meta">{item.role === 'user' ? <><UserOutlined /> 你</> : <><span className="mini-agent"><ThunderboltOutlined /></span> 评估 Agent</>} {item.payload?.mode === 'offline' && <Tag bordered={false}>离线流程</Tag>}</div><MessageContent content={item.content} /></div>)}
                  {latestStatus?.payload?.mode === 'offline' && <div className="offline-callout"><InfoCircleOutlined /><span>当前外部会话模型不可用，已回退到离线基础流程。企业详情、能耗、质量、目录和参考对照仍可继续查看。</span><Button type="link" onClick={() => void retryMessage()} disabled={processing}>重试</Button></div>}
                </div>
                <div className="composer-zone">
                  {attachments.length > 0 && <div className="attachment-strip">{attachments.map((item) => <Tag key={item.attachment_id} closable={false} icon={<FileTextOutlined />}>{item.original_filename}</Tag>)}</div>}
                  <div className="composer-box"><label className="clip-button" aria-label="添加补充材料"><PaperClipOutlined /><input type="file" accept=".pdf,.docx,.png,.jpg,.jpeg,.webp,.tiff,.bmp" onChange={(event) => { const file = event.target.files?.[0]; if (file) void handleAttachment(file); event.currentTarget.value = ''; }} /></label><Input.TextArea value={composer} onChange={(event) => setComposer(event.target.value)} onPressEnter={(event) => { if (!event.shiftKey) { event.preventDefault(); void sendMessage(); } }} autoSize={{ minRows: 1, maxRows: 5 }} placeholder={`围绕 ${run?.enterprise_code} 提问，或告诉 Agent 下一步…`} aria-label="输入评估问题"/><Tooltip title={processing ? '停止当前处理' : '发送消息'}><Button type="primary" shape="circle" icon={processing ? <PauseCircleOutlined /> : <SendOutlined />} onClick={() => processing ? void stopMessage() : void sendMessage()} disabled={!processing && !composer.trim()} aria-label={processing ? '停止当前处理' : '发送消息'} /></Tooltip></div>
                  <div className="composer-meta"><span><LockOutlined /> 当前对话绑定 {run?.enterprise_code}，不会跨企业读取事实</span><span>Enter 发送 · Shift + Enter 换行</span></div>
                </div>
              </section>
            )}
          </main>

          <aside className="inspector-sidebar" aria-label="评估检查器">
            <div className="inspector-header"><div><span className="section-eyebrow">评估检查器</span><h2>{run?.enterprise_code ?? '尚未开始'}</h2></div>{run && <Button type="text" icon={<ReloadOutlined />} onClick={() => void loadRunData(run)} aria-label="刷新评估数据" />}</div>
            {run ? <div className="inspector-scroll">
              <section className="inspector-card pipeline-card"><div className="card-title"><span>评估进度</span><span className="progress-caption">{pipeline.filter((item) => item.status === 'done').length}/8 已完成</span></div><Progress percent={Math.round((pipeline.filter((item) => item.status === 'done').length / pipeline.length) * 100)} showInfo={false} strokeColor="#1f6a5a" trailColor="#e8ede8" size="small"/><AssessmentPipeline stages={pipeline} /></section>
              <Collapse className="inspector-collapse" ghost defaultActiveKey={['profile', 'quality', 'energy', 'catalog']} items={[
                { key: 'profile', label: <span className="collapse-label"><UserOutlined /> 企业画像</span>, children: <ProfilePanel basic={basic} supplement={supplement} /> },
                { key: 'quality', label: <span className="collapse-label"><SafetyCertificateOutlined /> 数据质量 <Tag bordered={false} className="count-tag">{qualityIssues.length}</Tag></span>, children: <QualityPanel issues={qualityIssues} /> },
                { key: 'energy', label: <span className="collapse-label"><FundOutlined /> 能源表现</span>, children: <EnergyPanel trend={trend} chartOption={energyChartOption} /> },
                { key: 'catalog', label: <span className="collapse-label"><FileSearchOutlined /> 转型目录候选</span>, children: <CatalogPanel catalog={catalog} /> },
                { key: 'reference', label: <span className="collapse-label"><SlidersOutlined /> 参考对照 <Tag bordered={false} className="reference-tag">独立层</Tag></span>, children: <ReferencePanel reference={reference} /> },
              ]} />
              <section className="inspector-card boundary-card"><div className="card-title"><span>能力边界</span><InfoCircleOutlined /></div><div className="boundary-grid"><div><span>碳核算</span><StatusBadge status="not_calculable" compact /></div><div><span>评分</span><StatusBadge status="pending" compact /></div><div><span>授信</span><StatusBadge status="not_implemented" compact /></div></div><p>缺少正式核算边界、排放因子、行业基准和评分方法，因此不输出碳排放量、评分或授信结论。</p></section>
            </div> : <div className="inspector-empty"><Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="创建评估运行后，这里会显示企业画像和评估进度" /></div>}
            <button className="edge-toggle right-edge" onClick={() => setRightCollapsed((value) => !value)} aria-label={rightCollapsed ? '展开右侧栏' : '收起右侧栏'}>{rightCollapsed ? <MenuFoldOutlined /> : <MenuUnfoldOutlined />}</button>
          </aside>
        </div>

        <Modal title="新建工作空间" open={workspaceModalOpen} onCancel={() => setWorkspaceModalOpen(false)} onOk={() => void createWorkspace()} okText="创建" cancelText="取消">
          <p className="modal-hint">工作空间用于管理多家企业的独立评估运行。</p><Input value={newWorkspaceName} onChange={(event) => setNewWorkspaceName(event.target.value)} placeholder="例如：铜产业转型评估" maxLength={60} onPressEnter={() => void createWorkspace()} autoFocus />
        </Modal>
        <Modal title="新建企业评估" open={runModalOpen} onCancel={() => setRunModalOpen(false)} onOk={() => void createRun()} okText="建立运行" cancelText="取消">
          <p className="modal-hint">默认配套工作簿已经准备好。一次评估运行只绑定一家企业，切换企业会创建新的运行。</p>
          <div className="modal-field"><label htmlFor="enterprise-code">企业代号</label><Select id="enterprise-code" showSearch value={newRunCode} onChange={setNewRunCode} options={availableCodes.map((code) => ({ value: code, label: code }))} optionFilterProp="label" style={{ width: '100%' }} /></div>
          <div className="modal-field"><label htmlFor="run-name">运行名称（可选）</label><Input id="run-name" value={newRunName} onChange={(event) => setNewRunName(event.target.value)} placeholder={`${newRunCode} 企业评估`} maxLength={80} /></div>
          <div className="modal-notice"><DatabaseOutlined /><span>数据来源：命题方配套脱敏模拟数据，仅用于比赛开发测试。</span></div>
        </Modal>
        <Modal title="设置与诊断" open={settingsOpen} footer={<Button onClick={() => setSettingsOpen(false)}>关闭</Button>} onCancel={() => setSettingsOpen(false)}>
          <div className="settings-list"><div><span>默认数据</span><strong>{sourceBatch?.source_filename ?? '未找到'}</strong></div><div><span>数据状态</span><strong>命题方脱敏模拟数据</strong></div><div><span>外部会话模型</span><strong>{models.length ? `${models.length} 个已配置模型` : '未配置，使用离线基础流程'}</strong></div><div><span>解析能力</span><strong>{capabilities ? '已读取能力状态' : '载入中'}</strong></div></div><div className="admin-note"><LockOutlined /><span>管理员诊断入口保留在后端受控接口中。前端不显示 API Key、原始审计载荷或服务商内部信息。</span></div>
        </Modal>
      </AntdApp>
    </ConfigProvider>
  );
}

function ProfilePanel({ basic, supplement }: { basic?: Record<string, unknown>; supplement?: Record<string, unknown> }) {
  return <div className="profile-grid"><div><span>行业</span><strong>{valueOf(basic, '行业')}</strong></div><div><span>地区</span><strong>{valueOf(basic, '地区')}</strong></div><div><span>细分领域</span><strong>{valueOf(basic, '细分行业/领域')}</strong></div><div><span>成立年份</span><strong>{valueOf(basic, '成立年份')}</strong></div><div className="profile-wide"><span>主要产品/服务</span><strong>{valueOf(supplement, '主要产品/服务')}</strong></div></div>;
}

function QualityPanel({ issues }: { issues: Array<Record<string, unknown>> }) {
  if (!issues.length) return <div className="panel-empty"><CheckCircleOutlined /> 当前运行没有登记质量问题</div>;
  return <div className="quality-list">{issues.slice(0, 6).map((issue, index) => <div className="quality-item" key={String(issue.issue_id ?? index)}><span className={`quality-dot quality-${issue.severity ?? 'info'}`} /><div><strong>{String(issue.message ?? '质量提示')}</strong><small>{[issue.sheet_name, issue.field].filter(Boolean).join(' · ') || '企业级派生检查'}</small></div></div>)}{issues.length > 6 && <small className="panel-footnote">还有 {issues.length - 6} 项，完整列表可在详情流程中查看。</small>}</div>;
}

function EnergyPanel({ trend, chartOption }: { trend?: CompanyDetail['analysis']['energy_trend']; chartOption: Record<string, unknown> }) {
  const resources = trend?.resources ?? [];
  const comparable = resources.filter((item) => item.status === '可比较').length;
  return <div className="energy-panel"><div className="energy-summary"><span><strong>{comparable}</strong><small>项可比较</small></span><span><strong>{resources.length - comparable}</strong><small>项待补充</small></span></div>{resources.length ? <ReactECharts option={chartOption} style={{ height: 220, width: '100%' }} notMerge /> : <div className="panel-empty">暂无能源数据</div>}<p className="panel-footnote">{trend?.calculation_note ?? '仅比较工作簿原始值，不输出正式碳排放量。'}</p></div>;
}

function CatalogPanel({ catalog }: { catalog?: CompanyDetail['analysis']['catalog_matches'] }) {
  const candidates = catalog?.candidates ?? [];
  return <div className="catalog-panel"><div className="catalog-status"><span>当前状态</span><strong>{catalog?.status ?? '待载入'}</strong></div>{candidates.slice(0, 3).map((candidate, index) => <div className="catalog-item" key={`${candidate.catalog_row_id ?? index}`}><div><strong>{String(candidate.transition_path ?? '未命名转型路径')}</strong><small>{String(candidate.category ?? '行业级候选')} · {String(candidate.catalog_row_id ?? '临时行标识')}</small></div>{candidate.top_provisional_candidate === true && <Tag bordered={false}>候选靠前</Tag>}</div>)}{!candidates.length && <div className="panel-empty">当前行业暂无目录候选或待补充行业信息</div>}<p className="panel-footnote">候选排序是暂定规则，不是评分；最终路径需人工复核。</p></div>;
}

function ReferencePanel({ reference }: { reference?: CompanyDetail['analysis']['reference_comparison'] }) {
  return <div className="reference-panel"><div className="reference-guard"><CheckCircleOutlined /><span>模型输入隔离：{reference?.leakage_guard?.status === 'passed' ? '通过' : '待检查'}</span></div><p>{reference?.comparison_notice ?? '转型规划结论仅用于参考对照，不进入模型输入、特征或标签。'}</p><div className="reference-meta"><span>参考字段</span><strong>{reference?.reference_fields_present ?? 0} 个</strong></div></div>;
}

export default function RootApp() {
  return <App />;
}
