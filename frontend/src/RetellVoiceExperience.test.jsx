// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  api: vi.fn(),
  listeners: new Map(),
  startCall: vi.fn(),
  stopCall: vi.fn(),
  mute: vi.fn(),
  unmute: vi.fn(),
}));

vi.mock('./api', () => ({ api: mocks.api }));
vi.mock('retell-client-js-sdk', () => ({
  RetellWebClient: class {
    on(event, handler) { mocks.listeners.set(event, handler); }
    off(event, handler) {
      if (mocks.listeners.get(event) === handler) mocks.listeners.delete(event);
    }
    startCall(options) { return mocks.startCall(options); }
    stopCall() { return mocks.stopCall(); }
    mute() { return mocks.mute(); }
    unmute() { return mocks.unmute(); }
  },
}));

import { RetellVoiceExperience } from './RetellVoiceExperience';

beforeEach(() => {
  mocks.listeners.clear();
  mocks.api.mockReset().mockResolvedValue({ access_token: 'temporary-token' });
  mocks.startCall.mockReset().mockResolvedValue(undefined);
  mocks.stopCall.mockReset();
  mocks.mute.mockReset();
  mocks.unmute.mockReset();
  Object.defineProperty(window, 'isSecureContext', { configurable: true, value: true });
  Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: {} });
});

afterEach(cleanup);

describe('Retell voice-first active call', () => {
  it('keeps transcript updates internal and renders only voice controls during a call', async () => {
    render(
      <RetellVoiceExperience prompts={['Find an SUV']}>
        <div>Intro content</div>
      </RetellVoiceExperience>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Start Call' }));
    await waitFor(() => expect(mocks.startCall).toHaveBeenCalledWith({ accessToken: 'temporary-token' }));

    expect(screen.getByRole('status')).toHaveTextContent('Connecting...');
    expect(screen.queryByText('Intro content')).not.toBeInTheDocument();
    expect(screen.queryByText('TRY SAYING')).not.toBeInTheDocument();

    act(() => mocks.listeners.get('call_ready')());
    expect(screen.getByRole('status')).toHaveTextContent('Listening...');

    act(() => mocks.listeners.get('update')({
      transcript: [{ role: 'user', content: 'This must not appear on screen' }],
    }));
    expect(screen.queryByText(/This must not appear/)).not.toBeInTheDocument();
    expect(screen.queryByText('RECENT CONVERSATION')).not.toBeInTheDocument();

    act(() => mocks.listeners.get('agent_start_talking')());
    expect(screen.getByRole('status')).toHaveTextContent('Speaking...');

    fireEvent.click(screen.getByRole('button', { name: 'Mute' }));
    expect(mocks.mute).toHaveBeenCalledOnce();
    expect(screen.getByRole('button', { name: 'Unmute' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: 'End Call' })).toBeEnabled();

    act(() => mocks.listeners.get('call_ended')());
    expect(screen.getByRole('status')).toHaveTextContent('Call Ended');
    expect(screen.getByRole('button', { name: 'Start New Call' })).toBeEnabled();
    expect(screen.queryByText('Intro content')).not.toBeInTheDocument();
    expect(screen.queryByText('TRY SAYING')).not.toBeInTheDocument();
    expect(screen.queryByText(/This must not appear/)).not.toBeInTheDocument();
  });
});
