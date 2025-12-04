export interface GeneratedPage {
  _id?: string;
  task_id: string;
  page_id: string;
  page_name: string;
  page_url: string;
  sequence_num: number;
  gender: 'female' | 'male' | 'unknown';
  status: string;
  creation_time: string;
}

export interface PageGenerationTask {
  id: string;
  _id?: string;
  profile_id: string;
  num_pages: number;
  base_page_name: string;
  public_profile_url?: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  celery_task_id: string | null;
  pages_created: number;
  pages_failed: number;
  shares_sent?: number;
  shares_failed?: number;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  pages: GeneratedPage[];
  progress: number;
  // Aliases for backward compatibility
  base_name?: string;
  count?: number;
}

export interface EfficiencyReport {
  total_tasks: number;
  total_pages: number;
  pages_created: number;
  pages_failed: number;
  success_rate: number;
  avg_pages_per_task: number;
}

export interface BenchmarkResult {
  pages: {
    name: string;
    page_id: string;
    success: boolean;
    duration: number;
    error: string;
  }[];
  metrics: {
    pages_created: number;
    total_time: number;
    errors: number;
    avg_time_per_page: number;
    success_rate: number;
  };
  total_time: number;
}

export interface CreateTaskRequest {
  base_name: string;
  count: number;
  profile_id?: string;
  public_profile_url?: string;
  profile_name?: string;
}

export interface BenchmarkRequest {
  base_name: string;
  count: number;
  headless: boolean;
  timeout: number;
}

export interface Profile {
  id: string;
  email: string;
  name: string;
  created_at: string;
  is_active: boolean;
}

export interface PageInvite {
  _id: string;
  page_id: string;
  page_name: string;
  invitee_email: string;
  invite_link: string;
  role: 'admin' | 'editor' | 'moderator' | 'advertiser' | 'analyst';
  invited_by: string;
  status: 'pending' | 'accepted' | 'declined' | 'expired';
  created_at: string;
  accepted_at: string | null;
}

export interface InviteRequest {
  email: string;
  role: string;
}

export interface InviteResponse {
  success: boolean;
  invite_id?: string;
  page_id?: string;
  email?: string;
  role?: string;
  invite_link?: string;
  message?: string;
  error?: string;
}
