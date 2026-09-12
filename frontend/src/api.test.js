// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest';

const path = '/api/admin/appointments/APT-000321';
beforeEach(() => {
  vi.resetModules();
  localStorage.clear();
  vi.stubGlobal('fetch', vi.fn());
});
afterEach(() => { vi.unstubAllGlobals(); vi.unstubAllEnvs(); });

it.each(['https://api.example.com', 'https://api.example.com/'])('uses the configured backend origin %s and current bearer token', async origin => {
  vi.stubEnv('VITE_API_BASE_URL', origin);
  localStorage.setItem('nexdrive_admin_session', JSON.stringify({ access_token: 'test-session-token' }));
  fetch.mockResolvedValue(new Response(JSON.stringify({ success: true })));
  const { api } = await import('./api');
  await expect(api(path, { method: 'DELETE' }, true)).resolves.toEqual({ success: true });
  expect(fetch).toHaveBeenCalledWith(`https://api.example.com${path}`, {
    method: 'DELETE', headers: { 'Content-Type': 'application/json', Authorization: 'Bearer test-session-token' },
  });
});

it('uses a relative path when a same-origin API is configured by the host', async () => {
  vi.stubEnv('VITE_API_BASE_URL', '');
  fetch.mockResolvedValue(new Response('{}'));
  const { api } = await import('./api');
  await api(path, { method: 'DELETE' }, true);
  expect(fetch.mock.calls[0][0]).toBe(path);
});

it('sanitizes network and unreachable API errors', async () => {
  vi.stubEnv('VITE_API_BASE_URL', 'https://unreachable.invalid');
  fetch.mockRejectedValue(new TypeError('Failed to fetch'));
  const { api } = await import('./api');
  await expect(api(path, { method: 'DELETE' }, true)).rejects.toThrow('Could not reach the server. Please try again.');
});

it.each([403, 404, 409, 500, 503])('preserves safe backend errors and HTTP status %s', async status => {
  fetch.mockResolvedValue(new Response(JSON.stringify({ detail: { message: 'Safe backend message' } }), { status }));
  const { api } = await import('./api');
  await expect(api(path, { method: 'DELETE' }, true)).rejects.toMatchObject({ status, message: 'Safe backend message' });
});

it('clears an expired session and requests a new login on 401', async () => {
  localStorage.setItem('nexdrive_admin_session', JSON.stringify({ access_token: 'expired-test-token' }));
  fetch.mockResolvedValue(new Response('{}', { status: 401 }));
  const { api, getSession } = await import('./api');
  await expect(api(path, { method: 'DELETE' }, true)).rejects.toMatchObject({ status: 401, message: 'Your admin session has expired or is invalid. Please sign in again.' });
  expect(getSession()).toBeNull();
});
