import type {
  AssessmentRun,
  Attachment,
  CompanyDetail,
  ConversationResponse,
  Message,
  ModelOption,
  ProcessSummary,
  SourceBatch,
  Workspace,
  WorkflowCheckpoint,
  KnowledgeIndexStatus,
  KnowledgeSearchResponse,
  WorkflowList,
} from './contracts';

const API_PREFIX = '/api/v1';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_PREFIX}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    ...init,
  });
  const contentType = response.headers.get('content-type') ?? '';
  const payload = contentType.includes('application/json') ? await response.json() : await response.text();
  if (!response.ok) {
    const detail = typeof payload === 'object' && payload && 'detail' in payload ? payload.detail : payload;
    throw new Error(String(detail || `请求失败（${response.status}）`));
  }
  return payload as T;
}

export const api = {
  listWorkspaces: () => request<{ workspaces: Workspace[] }>('/workspaces'),
  createWorkspace: (name: string) => request<Workspace>('/workspaces', { method: 'POST', body: JSON.stringify({ name }) }),
  getDefaultSourceBatch: () => request<SourceBatch>('/source-batches/default'),
  listRuns: (workspaceId: string) => request<{ runs: AssessmentRun[] }>(`/workspaces/${workspaceId}/runs`),
  createRun: (workspaceId: string, body: {
    enterprise_code: string;
    source_batch_id: string;
    run_name: string;
    model_config?: Record<string, unknown>;
    basic_info_index?: Record<string, unknown>;
  }) => request<AssessmentRun>(`/workspaces/${workspaceId}/runs`, { method: 'POST', body: JSON.stringify(body) }),
  getRun: (runId: string) => request<AssessmentRun>(`/assessment-runs/${runId}`),
  getCompanyDetail: (runId: string) => request<CompanyDetail>(`/assessment-runs/${runId}/company-detail`),
  listMessages: (runId: string) => request<{ messages: Message[] }>(`/assessment-runs/${runId}/messages`),
  getProcessSummary: (runId: string) => request<ProcessSummary>(`/assessment-runs/${runId}/conversation/summary`),
  listWorkflows: (runId: string) => request<WorkflowList>(`/assessment-runs/${runId}/workflows`),
  startWorkflow: (runId: string, workflowName: WorkflowCheckpoint['workflow_name']) => request<WorkflowCheckpoint>(`/assessment-runs/${runId}/workflows/start`, {
    method: 'POST',
    body: JSON.stringify({ workflow_name: workflowName }),
  }),
  pauseWorkflow: (runId: string, workflowName: WorkflowCheckpoint['workflow_name']) => request<WorkflowCheckpoint>(`/assessment-runs/${runId}/workflows/${workflowName}/pause`, { method: 'POST' }),
  resumeWorkflow: (runId: string, workflowName: WorkflowCheckpoint['workflow_name'], answers: string[] = [], confirmNoAdditional = false) => request<WorkflowCheckpoint>(`/assessment-runs/${runId}/workflows/${workflowName}/resume`, {
    method: 'POST',
    body: JSON.stringify({ answers, confirm_no_additional: confirmNoAdditional }),
  }),
  reviewWorkflow: (runId: string, workflowName: WorkflowCheckpoint['workflow_name'], decision: 'approve' | 'request_changes') => request<WorkflowCheckpoint>(`/assessment-runs/${runId}/workflows/${workflowName}/review`, {
    method: 'POST',
    body: JSON.stringify({ decision }),
  }),
  listAttachments: (runId: string) => request<{ attachments: Attachment[] }>(`/assessment-runs/${runId}/attachments`),
  getModels: () => request<{ models: ModelOption[]; external_configured: boolean; default_model_id?: string | null }>('/models'),
  getParserCapabilities: () => request<Record<string, unknown>>('/parsers/capabilities'),
  getKnowledgeIndex: () => request<KnowledgeIndexStatus>('/knowledge/indexes/current'),
  searchKnowledge: (runId: string, query: string, topK = 5, sourceRoles: string[] = [], signal?: AbortSignal) => request<KnowledgeSearchResponse>(`/assessment-runs/${runId}/knowledge/search`, {
    method: 'POST',
    signal,
    body: JSON.stringify({ query, top_k: topK, source_roles: sourceRoles }),
  }),
  getKnowledgeChunk: (runId: string, chunkId: string) => request<Record<string, unknown>>(`/assessment-runs/${runId}/knowledge/chunks/${chunkId}`),
  listKnowledgeRetrievals: (runId: string) => request<{ assessment_run_id: string; retrievals: Array<Record<string, unknown>> }>(`/assessment-runs/${runId}/knowledge/retrievals`),
  turn: (runId: string, content: string, modelId?: string) => request<ConversationResponse>(`/assessment-runs/${runId}/conversation/turn`, {
    method: 'POST',
    body: JSON.stringify({ content, ...(modelId ? { model_id: modelId } : {}), mode: modelId ? 'auto' : 'offline' }),
  }),
  stop: (runId: string) => request<Record<string, unknown>>(`/assessment-runs/${runId}/conversation/stop`, { method: 'POST' }),
  retry: (runId: string, modelId?: string) => request<ConversationResponse>(`/assessment-runs/${runId}/conversation/retry`, {
    method: 'POST',
    body: JSON.stringify(modelId ? { model_id: modelId } : {}),
  }),
  uploadAttachment: async (runId: string, file: File) => {
    const form = new FormData();
    form.append('file', file);
    const response = await fetch(`${API_PREFIX}/assessment-runs/${runId}/attachments`, { method: 'POST', body: form });
    const payload = await response.json();
    if (!response.ok) throw new Error(String(payload.detail || '附件上传失败'));
    return payload as Attachment;
  },
};
