/* API response types — mirrors backend Pydantic schemas. */

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface UserResponse {
  username: string;
  role: string;
}

export interface RepoResponse {
  id: number;
  github_url: string;
  webhook_status: string;
  created_at: string;
  pr_count: number;
}

export interface RepoListResponse {
  repos: RepoResponse[];
  total: number;
}

export interface ReviewListItem {
  id: number;
  pr_id: number;
  pr_number: number;
  pr_title: string;
  repo_name: string;
  confidence_score: number;
  decision: string;
  created_at: string;
  findings_count: number;
  tests_passed: number;
  tests_total: number;
}

export interface ReviewListResponse {
  reviews: ReviewListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface FindingResponse {
  id: number;
  review_id: number;
  type: string;
  description: string;
  file: string;
  line: number | null;
}

export interface ProposedFixResponse {
  id: number;
  review_id: number;
  diff_text: string;
  reasoning_text: string;
  accepted: boolean;
}

export interface TestRunResponse {
  id: number;
  review_id: number;
  passed: boolean;
  failed: boolean;
  traceback_text: string | null;
}

export interface ReviewDetailResponse {
  id: number;
  pr_id: number;
  pr_number: number;
  pr_title: string;
  repo_name: string;
  confidence_score: number;
  decision: string;
  created_at: string;
  findings: FindingResponse[];
  proposed_fixes: ProposedFixResponse[];
  test_runs: TestRunResponse[];
}

export interface AnalyticsSummary {
  total_prs_analyzed: number;
  total_bugs_caught: number;
  fix_acceptance_rate: number;
  avg_confidence_score: number;
}

export type ReviewDecision = "accepted" | "needs_human_review" | "error" | "pending";
