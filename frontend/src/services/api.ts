import axios from 'axios';
import {
  PageGenerationTask,
  EfficiencyReport,
  BenchmarkResult,
  CreateTaskRequest,
  BenchmarkRequest,
  PageInvite,
  InviteRequest,
  InviteResponse,
  GeneratedPage,
} from '../types';

const API_BASE = 'http://localhost:8000/api';

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const taskService = {
  // Get all tasks
  getTasks: async (): Promise<PageGenerationTask[]> => {
    const response = await api.get('/tasks/');
    return response.data;
  },

  // Get single task
  getTask: async (id: string): Promise<PageGenerationTask> => {
    const response = await api.get(`/tasks/${id}/`);
    return response.data;
  },

  // Create new task
  createTask: async (data: CreateTaskRequest): Promise<PageGenerationTask> => {
    const response = await api.post('/tasks/', data);
    return response.data;
  },

  // Start task
  startTask: async (id: string): Promise<PageGenerationTask> => {
    const response = await api.post(`/tasks/${id}/start/`);
    return response.data;
  },

  // Cancel task
  cancelTask: async (id: string): Promise<PageGenerationTask> => {
    const response = await api.post(`/tasks/${id}/cancel/`);
    return response.data;
  },

  // Delete task
  deleteTask: async (id: string): Promise<void> => {
    await api.delete(`/tasks/${id}/`);
  },

  // Get efficiency report
  getEfficiencyReport: async (): Promise<EfficiencyReport> => {
    const response = await api.get('/tasks/efficiency_report/');
    return response.data;
  },

  // Get all created pages
  getAllPages: async (): Promise<GeneratedPage[]> => {
    const response = await api.get('/pages/');
    return response.data;
  },
};

export const automationService = {
  // Run benchmark
  runBenchmark: async (data: BenchmarkRequest): Promise<BenchmarkResult> => {
    const response = await api.post('/automation/benchmark/', data);
    return response.data;
  },

  // Health check
  healthCheck: async (): Promise<{ status: string; selenium: string }> => {
    const response = await api.get('/automation/health/');
    return response.data;
  },
};

export const inviteService = {
  // Test invite access flow
  testInviteAccess: async (pageId: string, profileUrl: string, profileName: string): Promise<{
    success: boolean;
    error?: string;
    details?: string;
  }> => {
    const response = await api.post('/automation/test-invite/', {
      page_id: pageId,
      profile_url: profileUrl,
      profile_name: profileName,
    });
    return response.data;
  },

  // Send invite to a person for a page
  invitePerson: async (pageId: string, data: InviteRequest): Promise<InviteResponse> => {
    const response = await api.post(`/pages/${pageId}/invite/`, data);
    return response.data;
  },

  // Get invites for a specific page
  getPageInvites: async (pageId: string): Promise<PageInvite[]> => {
    const response = await api.get(`/pages/${pageId}/invites/`);
    return response.data;
  },

  // Get all invites
  getAllInvites: async (): Promise<PageInvite[]> => {
    const response = await api.get('/invites/');
    return response.data;
  },

  // Accept an invite
  acceptInvite: async (inviteId: string): Promise<{ message: string; status: string }> => {
    const response = await api.post(`/invites/${inviteId}/accept/`);
    return response.data;
  },

  // Decline an invite
  declineInvite: async (inviteId: string): Promise<{ message: string; status: string }> => {
    const response = await api.post(`/invites/${inviteId}/decline/`);
    return response.data;
  },
};
