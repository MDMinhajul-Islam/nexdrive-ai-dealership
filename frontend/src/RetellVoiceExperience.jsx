import { useEffect, useRef, useState } from 'react';
import { RetellWebClient } from 'retell-client-js-sdk';
import { api } from './api';

const retellWebClient = new RetellWebClient();
const DEMO_CUSTOMER_ID = 'CUST-000005';
const DEMO_SALESPERSON_ID = 'SP-001';
const ACTIVE_STATES = new Set(['connecting', 'connected', 'agent-speaking']);
const MICROPHONE_ERROR = 'Microphone access is required to talk with the AI sales assistant.';
const SAFE_CONNECTION_ERROR = 'Unable to start the voice call. Please try again.';

const STATUS_LABELS = {
  idle: 'Ready to talk',
  connecting: 'Connecting...',
  connected: 'Listening...',
  'agent-speaking': 'Speaking...',
  ended: 'Call Ended',
  error: 'Unable to Start Call',
};

async function microphoneIsDenied(error) {
  if (error?.name === 'NotAllowedError' || error?.name === 'PermissionDeniedError') return true;
  try {
    const result = await navigator.permissions?.query({ name: 'microphone' });
    return result?.state === 'denied';
  } catch {
    return false;
  }
}

export function RetellVoiceExperience({
  children,
  prompts,
  testDrive = false,
  customerId = DEMO_CUSTOMER_ID,
  salespersonId = DEMO_SALESPERSON_ID,
}) {
  const [callState, setCallState] = useState('idle');
  const [muted, setMuted] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const latestTranscript = useRef(null);
  const startInProgress = useRef(false);
  const mounted = useRef(true);
  const requestController = useRef(null);

  useEffect(() => {
    mounted.current = true;
    const connected = () => {
      if (!mounted.current) return;
      startInProgress.current = false;
      setCallState('connected');
    };
    const agentStarted = () => mounted.current && setCallState('agent-speaking');
    const agentStopped = () => mounted.current && setCallState('connected');
    const updated = update => {
      if (!mounted.current) return;
      if (update?.transcript !== undefined) latestTranscript.current = update.transcript;
    };
    const ended = () => {
      if (!mounted.current) return;
      startInProgress.current = false;
      setMuted(false);
      setCallState('ended');
    };
    const failed = async error => {
      const denied = await microphoneIsDenied(error);
      if (!mounted.current) return;
      startInProgress.current = false;
      setMuted(false);
      setErrorMessage(denied ? MICROPHONE_ERROR : SAFE_CONNECTION_ERROR);
      setCallState('error');
    };

    retellWebClient.on('call_started', connected);
    retellWebClient.on('call_ready', connected);
    retellWebClient.on('agent_start_talking', agentStarted);
    retellWebClient.on('agent_stop_talking', agentStopped);
    retellWebClient.on('update', updated);
    retellWebClient.on('call_ended', ended);
    retellWebClient.on('error', failed);

    return () => {
      mounted.current = false;
      requestController.current?.abort();
      retellWebClient.off('call_started', connected);
      retellWebClient.off('call_ready', connected);
      retellWebClient.off('agent_start_talking', agentStarted);
      retellWebClient.off('agent_stop_talking', agentStopped);
      retellWebClient.off('update', updated);
      retellWebClient.off('call_ended', ended);
      retellWebClient.off('error', failed);
      retellWebClient.stopCall();
      startInProgress.current = false;
    };
  }, []);

  const startCall = async () => {
    if (startInProgress.current || ACTIVE_STATES.has(callState)) return;
    if (!window.isSecureContext || !navigator.mediaDevices) {
      setErrorMessage('A secure HTTPS connection and microphone access are required for voice calls.');
      setCallState('error');
      return;
    }

    startInProgress.current = true;
    setErrorMessage('');
    latestTranscript.current = null;
    setMuted(false);
    setCallState('connecting');

    try {
      requestController.current = new AbortController();
      const response = await api('/api/retell/create-web-call', {
        method: 'POST',
        signal: requestController.current.signal,
        body: JSON.stringify({
          customer_id: customerId,
          assigned_salesperson: salespersonId,
        }),
      });
      if (!mounted.current) return;
      if (!response?.access_token) throw new Error('Malformed web-call response');
      await retellWebClient.startCall({ accessToken: response.access_token });
      if (!mounted.current) retellWebClient.stopCall();
    } catch (error) {
      if (!mounted.current) return;
      startInProgress.current = false;
      if (import.meta.env.DEV && error?.status) {
        console.warn('Retell create-web-call request failed', { status: error.status });
      }
      const denied = await microphoneIsDenied(error);
      setErrorMessage(denied ? MICROPHONE_ERROR : SAFE_CONNECTION_ERROR);
      setCallState('error');
    }
  };

  const endCall = () => retellWebClient.stopCall();
  const toggleMute = () => {
    if (!ACTIVE_STATES.has(callState) || callState === 'connecting') return;
    if (muted) retellWebClient.unmute();
    else retellWebClient.mute();
    setMuted(value => !value);
  };

  const active = callState === 'connected' || callState === 'agent-speaking';
  const callInProgress = ACTIVE_STATES.has(callState);
  const focusedCallView = callInProgress || callState === 'ended';
  const canStart = !ACTIVE_STATES.has(callState);
  const helperText = callState === 'error'
    ? errorMessage
    : callState === 'ended'
      ? 'Your private conversation has ended. Start another call whenever you are ready.'
      : testDrive
        ? 'Nex will verify this vehicle before offering appointment times.'
        : 'Start a private voice conversation with the NexDrive AI sales assistant.';

  return <>
    <section className={`voice-stage ${focusedCallView ? 'voice-focus' : ''}`}>
      {!focusedCallView && children}
      <div className={`voice-console ${callState}`}>
        <span className="voice-agent-label"><b>N</b>NEXDRIVE VOICE</span>
        <div className="voice-rings">
          <i/><i/><i/>
          <button
            onClick={startCall}
            disabled={!canStart}
            aria-label={callInProgress ? (muted ? 'Microphone muted' : 'Voice call active') : 'Start voice call'}
          >
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3Zm-7 9a7 7 0 0 0 14 0m-7 7v3"/></svg>
          </button>
        </div>
        <span className="voice-status" role="status" aria-live="polite">
          {muted && active ? 'Microphone muted' : STATUS_LABELS[callState]}
        </span>
        <h2>Talk to AI Sales Agent</h2>
        {!callInProgress && <p>{helperText}</p>}
        <div className="voice-controls">
          {canStart
            ? <button className="gold voice-start" onClick={startCall}>{callState === 'error' ? 'Try Again' : callState === 'ended' ? 'Start New Call' : 'Start Call'}</button>
            : callState === 'connecting'
              ? <button className="gold voice-start" disabled>Connecting...</button>
              : <>
                <button className="outline" onClick={toggleMute} aria-pressed={muted}>{muted ? 'Unmute' : 'Mute'}</button>
                <button className="voice-end" onClick={endCall} disabled={!active}>End Call</button>
              </>}
        </div>
        {!callInProgress && <small>{callState === 'ended'
          ? 'Microphone access is used only while a voice call is active.'
          : 'No appointment is created until you explicitly confirm a valid slot.'}</small>}
      </div>
    </section>
    {!focusedCallView && <section className="conversation-prompts">
      <span>TRY SAYING</span>
      {prompts.map(prompt => <button key={prompt} onClick={startCall} disabled={!canStart}>“{prompt}”</button>)}
    </section>}
  </>;
}
