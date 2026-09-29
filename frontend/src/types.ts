export type ReleaseOutcome =
  | "PASS"
  | "PASS_WITH_CONDITIONS"
  | "BLOCK"
  | "INSUFFICIENT_EVIDENCE";

export interface DemoContext {
  tenant_id: string;
  project_id: string;
  users: Record<string, string>;
  synthetic: boolean;
}

export interface Project {
  id: string;
  name: string;
  intended_use: string;
  prohibited_uses: string[];
  business_owner: string;
  technical_owner: string;
  risk_tier: string;
  required_approver_roles: string[];
}

export interface Run {
  id: string;
  project_id: string;
  status: string;
  stage: string;
  progress_percent: number;
  created_at: string;
  error_summary?: string;
}

export interface Finding {
  id: string;
  title: string;
  category: string;
  severity: string;
  status: string;
  description: string;
  evidence: string[];
  likely_failure_stage: string;
  recommended_remediation: string;
}

export interface CaseResult {
  id: string;
  baseline_response: {
    answer: string;
    citations: string[];
    latency_ms: number;
    estimated_cost_usd: number;
  };
  candidate_response: {
    answer: string;
    citations: string[];
    latency_ms: number;
    estimated_cost_usd: number;
  };
  metrics: Record<string, unknown>;
  baseline_passed: boolean;
  candidate_passed: boolean;
  regression: boolean;
  mandatory_failed: boolean;
  error?: string;
}

export interface Decision {
  id: string;
  outcome: ReleaseOutcome;
  effective_outcome: ReleaseOutcome;
  policy_version: string;
  rationale: string;
  required_approvals: string[];
  rule_results: Array<{
    rule_id: string;
    description: string;
    triggered: boolean;
    outcome?: ReleaseOutcome;
    evidence: string[];
  }>;
}

export interface RunDetail {
  run: Run;
  case_results: CaseResult[];
  findings: Finding[];
  decision?: Decision;
  agent_traces: Array<Record<string, unknown>>;
  audit_timeline: Array<Record<string, unknown>>;
}

export interface Dashboard {
  synthetic: boolean;
  projects: Project[];
  recent_runs: Run[];
  open_critical_findings: number;
  operational_health: string;
}
