import type { ScreeningAnalysis, ScreeningInput } from '../types/screening';

const API_BASE = (import.meta.env.VITE_API_URL || (import.meta.env.DEV ? 'http://localhost:8000' : '')).replace(/\/$/, '');

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  if (!API_BASE) throw new ApiError('This hosted demo is running without a connected API service.', 0);
  const headers = new Headers(init.headers);
  headers.set('Accept', 'application/json');
  if (init.body) headers.set('Content-Type', 'application/json');
  const token = sessionStorage.getItem('biosentry.token');
  if (token) headers.set('Authorization', `Bearer ${token}`);

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, { ...init, headers });
  } catch {
    throw new ApiError('Cannot reach Oralytics API. Start the backend and check VITE_API_URL.', 0);
  }
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 401) sessionStorage.removeItem('biosentry.token');
    const detail = body?.detail;
    throw new ApiError(typeof detail === 'string' ? detail : 'The API request failed.', response.status);
  }
  if (body?.access_token) sessionStorage.setItem('biosentry.token', body.access_token as string);
  return body as T;
}

export const api = {
  health: () => request<{ status: string }>('/api/health'),
  me: () => request<{ id: number; full_name: string; email: string; role: string }>('/api/v1/auth/me'),
  analyzeScreening: (input: ScreeningInput) => request<ScreeningAnalysis>('/api/v1/screenings/analyze', { method: 'POST', body: JSON.stringify(input) }),
  listScreenings: () => request<ScreeningAnalysis[]>('/api/v1/screenings'),
  getReport: (recordCode: string) => request<ScreeningAnalysis>(`/api/v1/screenings/${encodeURIComponent(recordCode)}/report`),
  getFacilities: () => request<Facility[]>('/api/v1/facilities'),
  listReferrals: () => request<Referral[]>('/api/v1/referrals'),
  createReferral: (input: { screening_id: number; facility_id: number; reason: string; priority: string; status: string }) => request<Referral>('/api/v1/referrals', { method: 'POST', body: JSON.stringify(input) }),
  updateReferralStatus: (id: number, status: string) => request<{ id: number; status: string; status_history: Referral['status_history'] }>(`/api/v1/referrals/${id}/status`, { method: 'PATCH', body: JSON.stringify({ status }) }),
  requestEmailOtp: (email: string) => request<{ message: string; expires_in: number; retry_after: number }>('/api/v1/auth/email-otp/request', { method: 'POST', body: JSON.stringify({ email }) }),
  verifyEmailOtp: (email: string, code: string) => request<{ verification_token: string; expires_in: number }>('/api/v1/auth/email-otp/verify', { method: 'POST', body: JSON.stringify({ email, code }) }),
  login: (email: string, password: string) => request<{ access_token: string; user: { full_name: string; role: string } }>('/api/v1/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  register: (input: { full_name: string; email: string; phone?: string | null; organization?: string | null; password: string; role: string; consent: boolean; email_verification_token: string }) => request<{ access_token: string; user: { full_name: string; role: string } }>('/api/v1/auth/register', { method: 'POST', body: JSON.stringify(input) }),
};

export interface Facility {
  id: number;
  name: string;
  type: string;
  address: string;
  latitude: number | null;
  longitude: number | null;
  data_source: string;
  is_simulated: boolean;
}

export interface Referral {
  id: number;
  screening_id: number;
  screening_code?: string;
  facility_id: number | null;
  reason: string;
  priority: string;
  status: string;
  status_history: Array<{ status: string; at: string }>;
  is_simulated?: boolean;
}
