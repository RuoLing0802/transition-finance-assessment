export type Json = Record<string, unknown>;

export type Workspace = {
  workspace_id: string;
  name: string;
  last_active_run_id?: string | null;
  archived?: boolean;
  updated_at?: string;
};

export type AssessmentRun = {
  assessment_run_id: string;
  workspace_id: string;
  enterprise_id: string;
  enterprise_code: string;
  source_batch_id: string;
  m1_batch_id?: string;
  run_name: string;
  rule_version: string;
  model_config?: Json;
  status: string;
  quality_gate_status?: string;
  simulated_data: boolean;
  data_notice?: string | null;
  created_at?: string;
  updated_at?: string;
};

export type SourceBatch = {
  source_batch_id: string;
  m1_batch_id: string;
  source_filename: string;
  sha256: string;
  source: string;
  simulated_data: boolean;
  validation_status: string;
  available_company_codes: string[];
  reused?: boolean;
  data_notice?: string | null;
};

export type Message = {
  message_id: string;
  assessment_run_id: string;
  role: 'user' | 'assistant' | 'system' | 'tool';
  message_type: string;
  content: string;
  tool_name?: string | null;
  payload?: Json;
  created_at?: string;
};

export type ProcessSummary = {
  assessment_run_id: string;
  steps: Array<{ label: string; status: 'current' | 'done' | 'error' }>;
  notice: string;
};

export type ModelOption = {
  model_id: string;
  model_name?: string;
  display_name: string;
  provider_id?: string;
  multimodal?: boolean;
  supports_vision?: boolean;
  mode?: string;
};

export type CompanyDetail = {
  workspace_id: string;
  assessment_run_id: string;
  enterprise_id: string;
  enterprise_code: string;
  source_batch_id: string;
  simulated_data: boolean;
  data_notice: string;
  rule_version: string;
  model_config?: Json;
  run_status: string;
  analysis: {
    company_code: string;
    input_data?: {
      basic_info?: Json;
      energy_info?: Json;
      supplement_info?: Json;
    };
    quality_issues?: Array<Json & { severity?: string; message?: string; field?: string }>;
    energy_trend?: {
      years?: number[];
      resources?: Array<Json & { name?: string; unit?: string; 2024?: number | null; 2025?: number | null; change?: number | null; change_rate?: number | null; status?: string }>;
      operating_metrics?: Array<Json & { name?: string; unit?: string; 2024?: number | null; 2025?: number | null; change?: number | null; change_rate?: number | null; status?: string }>;
      calculation_note?: string;
    };
    catalog_matches?: {
      status?: string;
      query?: Json;
      candidates?: Array<Json & { industry?: string; category?: string; field?: string; path?: string; match_reason?: string; ambiguity?: boolean }>;
      manual_review_required?: boolean;
      match_policy?: string;
    };
    reference_comparison?: {
      status?: string;
      comparison_notice?: string;
      leakage_guard?: { status?: string };
      comparison_summary?: Json;
      reference_fields_present?: number;
    };
    boundaries?: Json;
  };
};

export type Attachment = {
  attachment_id: string;
  assessment_run_id: string;
  original_filename: string;
  file_type: string;
  status: string;
  confidence?: number | null;
  enterprise_code?: string | null;
  review_status?: string;
};

export type ConversationResponse = {
  mode: 'external' | 'offline' | 'stopped';
  degraded?: boolean;
  message: Message;
  tool_results?: Array<{ tool_name: string; status: string; result?: Json; error?: Json }>;
  data_notice?: string;
};

export type WorkflowDefinition = {
  workflow_name: 'baseline_review' | 'evidence_followup';
  label: string;
  description: string;
  nodes: string[];
  pause_points: string[];
};

export type WorkflowCheckpoint = {
  checkpoint_id: string;
  assessment_run_id: string;
  enterprise_id: string;
  enterprise_code: string;
  workflow_name: 'baseline_review' | 'evidence_followup';
  thread_id: string;
  status: 'running' | 'paused' | 'waiting_for_input' | 'waiting_human_review' | 'completed';
  current_node?: string | null;
  version: number;
  state: {
    completed_nodes?: string[];
    node_status?: Record<string, string>;
    follow_up_questions?: string[];
    pause_reason?: string | null;
    answer_count?: number;
    no_additional_confirmed?: boolean;
    quality_issue_count?: number;
    attachment_count?: number;
    review_decision?: string | null;
  };
  checkpoint?: Json;
  updated_at?: string;
};

export type WorkflowList = {
  assessment_run_id: string;
  engine: 'langgraph' | 'deterministic_fallback';
  thread_binding: string;
  definitions: WorkflowDefinition[];
  workflows: WorkflowCheckpoint[];
  notice: string;
};

export type KnowledgeSearchResult = {
  result_type: 'chunk' | 'source_metadata' | string;
  source_id: string;
  document_id?: string | null;
  chunk_id?: string | null;
  title: string;
  publisher?: string | null;
  version?: string | null;
  locator?: string | null;
  excerpt?: string | null;
  source_role: string;
  verification_status: string;
  visibility: string;
  use_boundary: string;
  official_url?: string | null;
  industry_scope: string[];
  match_tier: number;
  date_uncertain?: boolean;
};

export type KnowledgeSearchResponse = {
  retrieval_id: string;
  assessment_run_id: string;
  workspace_id: string;
  enterprise_id: string;
  enterprise_code: string;
  index_version_id: string;
  allowlist_version: string;
  knowledge_as_of: string;
  industry_scope: string[];
  query: string;
  results: KnowledgeSearchResult[];
  warnings: string[];
  degraded_mode?: string | null;
  data_notice: string;
  untrusted_content?: boolean;
  execution_boundary?: string;
};

export type KnowledgeIndexStatus = {
  available: boolean;
  fts5_available: boolean;
  index_version_id?: string;
  allowlist_version?: string;
  manifest_hash?: string;
  built_at?: string;
  searchable_candidate_count?: number;
  metadata_only_count?: number;
  diagnostic_only_count?: number;
  blocked_count?: number;
  notice?: string;
};
