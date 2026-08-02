// TypeScript 类型 — 对应 src/api/schemas.py 的 Pydantic 模型

// ===== 简历相关 =====
export interface SkillItem {
  name: string;
  category?: string;
  level?: string;
  confidence?: number;
  source_line?: number;
}

export interface ProjectItem {
  name: string;
  role?: string;
  tech_stack?: string[];
  time_period?: string;
  key_result?: string;
  description?: string;
  confidence?: number;
}

export interface AchievementItem {
  description: string;
  project_name?: string;
  metric_value?: string;
  confidence?: number;
}

export interface EducationItem {
  school?: string;
  degree?: string;
  major?: string;
  time?: string;
  graduation?: string;
  gpa?: string;
  confidence?: number;
}

export interface WorkItem {
  company?: string;
  position?: string;
  department?: string;
  time_period?: string;
  description?: string;
  achievements?: string[];
  tech_stack?: string[];
  confidence?: number;
}

export interface ResumeProfile {
  name?: string;
  email?: string;
  phone?: string;
  skills: SkillItem[];
  projects: ProjectItem[];
  achievements: AchievementItem[];
  education: EducationItem[];
  work_experience?: WorkItem[];
  summary?: string;
}

export interface VerificationReport {
  raw_text_hash?: string;
  raw_text_length?: number;
  total_extracted?: number;
  high_confidence?: number;
  medium_confidence?: number;
  low_confidence?: number;
  sections_found?: string[];
  verification_report?: string;
}

export interface FieldSource {
  field_name: string;
  source_text: string;
  source_line: number;
  extraction_method: string;
  confidence: number;
}

export interface ResumeUploadResponse {
  success: boolean;
  filename: string;
  profile: ResumeProfile;
  collections: Record<string, number>;
  message: string;
  verification: VerificationReport;
  field_sources: FieldSource[];
}

export interface ProfileResponse {
  name: string;
  email: string;
  skills_count: number;
  projects_count: number;
  achievements_count: number;
  profile: Record<string, unknown>;
  collection_stats: Record<string, number>;
}

// ===== 面试相关 =====
export interface InterviewRequest {
  question: string;
  mode?: string;
  temperature?: number;
}

export interface Citation {
  source: string;
  content: string;
  chunk_id?: string;
  score?: number;
}

export interface InterviewResponse {
  question: string;
  answer: string;
  question_type: string;
  citations: Citation[];
  review_scores: Record<string, number>;
  review_total: number;
  revision_count: number;
  error?: string;
}

// ===== 模拟面试相关 =====
export interface MockStartRequest {
  focus_areas: string[];
  difficulty: string;
  max_rounds?: number;
}

export interface MockStartResponse {
  session_id: string;
  first_question: string;
  total_rounds: number;
}

export interface MockNextRequest {
  session_id: string;
  answer: string;
}

export interface MockNextResponse {
  question: string;
  round_number: number;
  previous_feedback?: Record<string, unknown>;
  is_last: boolean;
  session_summary?: string;
}

// ===== 自我介绍相关 =====
export interface SelfIntroRequest {
  target_position: string;
  target_company: string;
  length: string; // "30s" | "1min" | "3min"
}

export interface SelfIntroResponse {
  intro_30s: string;
  intro_1min: string;
  intro_3min: string;
}

// ===== JD 匹配相关 =====
export interface JDMatchRequest {
  jd_text: string;
  target_position: string;
}

export interface JDMatchResponse {
  match_score: number;
  match_rate: number;
  matched_skills: string[];
  missing_skills: string[];
  recommended_skills: string[];
  missing_categories: string[];
  strength_analysis: string;
  gap_analysis: string;
}

// ===== 项目-JD 匹配相关 =====
export interface JDRequirements {
  tech_stack?: string[];
  soft_skills?: string[];
  experience_years?: number | null;
  keywords?: string[];
  responsibilities?: string[];
}

export interface ProjectMatchItem {
  name: string;
  role?: string;
  tech_stack?: string[];
  time_period?: string;
  key_result?: string;
  match_score: number;
  tech_overlap: number;
  years_match: number;
  complexity_score: number;
  matched_tech: string[];
}

export interface ProjectMatchRequest {
  jd_text: string;
  target_position: string;
}

export interface ProjectMatchResponse {
  jd_requirements: JDRequirements;
  projects: ProjectMatchItem[];
  top_project: ProjectMatchItem | null;
  targeted_answer: string;
  targeted_resume_desc: string;
  resume_content: string;
  added_skills: string[];
  matched_skills: string[];
  missing_skills: string[];
  message: string;
}

// ===== 系统相关 =====
export interface SystemInfoResponse {
  app_name: string;
  version: string;
  model: string;
  embedding_model: string;
  collections: Record<string, number>;
  memory_stats: Record<string, unknown>;
}

export interface HealthResponse {
  status: string;
  app: string;
  version: string;
}

// ===== SSE 事件 =====
export interface SSEEvent {
  type: string;
  node?: string;
  status?: string;
  data?: Record<string, unknown>;
  content?: string;
}

// ===== DAG 状态 =====
export type NodeStatus = 'pending' | 'running' | 'success' | 'failed';
export type DAGNodeId = 'planner' | 'router' | 'retrieval' | 'writer' | 'review' | 'end';

export interface DAGNodeState {
  status: NodeStatus;
  data?: Record<string, unknown>;
}

export interface WriterEntry {
  draft: string;
  revision_count: number;
  citations_count: number;
  citations?: Citation[];
}

export interface ReviewerDetail {
  needs_revision: boolean;
  scores: Record<string, number>;
  feedback: string;
  confidence: number;
}

export interface ReviewEntry {
  reviewers: Record<string, ReviewerDetail>;
  review_scores?: Record<string, number>;
  review_total: number;
  vote_decision: string;
  revision_feedback: string;
  revision_count: number;
  needs_revision?: boolean;
  elapsed_ms?: number;
}

export interface DAGState {
  nodes: Record<string, DAGNodeState>;
  writerEntries: WriterEntry[];
  reviewEntries: ReviewEntry[];
  finalAnswer: string;
  progress: number;
  progressText: string;
  error: string | null;
  reviewTotal?: number;
  revisionCount?: number;
}
