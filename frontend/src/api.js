export const API = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL || '';
const SUPABASE_KEY = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY || '';
const SESSION_KEY = 'nexdrive_admin_session';

export function getSession() {
  try { return JSON.parse(localStorage.getItem(SESSION_KEY) || 'null'); } catch { return null; }
}
export function clearSession() { localStorage.removeItem(SESSION_KEY); }
export async function signIn(email, password) {
  if (!SUPABASE_URL || !SUPABASE_KEY) throw new Error('Admin authentication is not configured.');
  const response = await fetch(`${SUPABASE_URL.replace(/\/$/, '')}/auth/v1/token?grant_type=password`, {
    method: 'POST', headers: { apikey: SUPABASE_KEY, 'Content-Type': 'application/json' }, body: JSON.stringify({ email, password }),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error_description || data.msg || 'Sign in failed.');
  const session = { access_token: data.access_token, refresh_token: data.refresh_token, user: data.user };
  localStorage.setItem(SESSION_KEY, JSON.stringify(session));
  return session;
}
export async function api(path, options = {}, admin = false) {
  const session = getSession();
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
  if (admin && session?.access_token) headers.Authorization = `Bearer ${session.access_token}`;
  const response = await fetch(`${API}${path}`, { ...options, headers });
  const data = await response.json().catch(() => ({}));
  if (response.status === 401 && admin) clearSession();
  if (!response.ok) {
    const error = new Error(data.detail || 'The request could not be completed.');
    error.status = response.status;
    throw error;
  }
  return data;
}
export const money = value => value == null ? '—' : new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(value);
