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
