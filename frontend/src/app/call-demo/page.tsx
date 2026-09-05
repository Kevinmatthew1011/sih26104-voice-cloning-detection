'use client';

import { useEffect, useState } from 'react';
import { Phone, PhoneOff, ShieldAlert } from 'lucide-react';
import { assessScamTranscript, demoScenarios, ScamAssessment } from '@/lib/scam-demo';

type Status = 'idle' | 'ringing' | 'active' | 'ended';
interface CallState {
  status: Status; messages: string[]; assessment: ScamAssessment; outcome: string;
}
interface HistoryEntry { caller: string; outcome: string; reasons: string[] }
const emptyCall: CallState = { status: 'idle', messages: [], assessment: assessScamTranscript([]), outcome: '' };
const button = 'rounded-xl border border-slate-700 px-4 py-3 font-medium hover:bg-slate-800 disabled:opacity-40 disabled:cursor-not-allowed';

export default function CallDemoPage() {
  const [scenarioId, setScenarioId] = useState('otp');
  const [call, setCall] = useState<CallState>(emptyCall);
  const [autoEnd, setAutoEnd] = useState(true);
  const [draft, setDraft] = useState('');
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const scenario = demoScenarios.find(item => item.id === scenarioId)!;
  const busy = call.status === 'ringing' || call.status === 'active';

  // Functional updates prevent queued transcript events from reopening an ended call.
  function addMessage(message: string) {
    setCall(previous => {
      if (previous.status !== 'active' || previous.messages.length >= 50 || !message.trim()) return previous;
      const messages = [...previous.messages, message.trim().slice(0, 500)];
      return { ...previous, messages, assessment: assessScamTranscript(messages) };
    });
  }

  useEffect(() => {
    if (call.status !== 'active' || call.assessment.risk === 'high') return;
    const next = scenario.messages[call.messages.length];
    if (!next) return;
    const timer = setTimeout(() => addMessage(next), 2500);
    return () => clearTimeout(timer);
  }, [call.status, call.messages.length, call.assessment.risk, scenario]);

  useEffect(() => {
    if (call.status !== 'active' || call.assessment.risk !== 'high' || !autoEnd) return;
    const timer = setTimeout(() => {
      setCall(previous => previous.status === 'active'
        ? { ...previous, status: 'ended', outcome: 'Automatically ended: high-risk scam indicators' }
        : previous);
    }, 2000);
    return () => clearTimeout(timer);
  }, [call.status, call.assessment.risk, autoEnd]);

  function startCall() {
    if (call.status === 'ended') {
      setHistory(previous => [{ caller: scenario.caller, outcome: call.outcome, reasons: call.assessment.reasons }, ...previous].slice(0, 10));
    }
    setCall({ ...emptyCall, status: 'ringing' });
    setDraft('');
  }

  function endCall(outcome: string) {
    setCall(previous => ({ ...previous, status: 'ended', outcome }));
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="space-y-3">
        <span className="text-xs font-semibold uppercase tracking-widest text-cyan-400">Interactive simulation</span>
        <h1 className="text-3xl font-bold">Scam call protection</h1>
        <p className="text-slate-400">See how suspicious caller requests trigger a warning and a simulated hang-up. No real calls are placed or declined.</p>
        <p className="text-sm text-slate-400">Uses sample or typed English messages and simple rules. No microphone recording, speech transcription, or voice-clone inference runs in this demo.</p>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <section className="space-y-5 rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
          <label className="block space-y-2"> <span>Demo scenario</span>
            <select className="w-full rounded-lg border border-slate-700 bg-slate-950 p-3" value={scenarioId} disabled={busy || call.status === 'ended'} onChange={event => setScenarioId(event.target.value)}>
              {demoScenarios.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
          </label>
          <label className="flex items-start gap-3 text-sm">
            <input type="checkbox" className="mt-1" checked={autoEnd} onChange={event => setAutoEnd(event.target.checked)} />
            Automatically end high-risk simulated calls after a two-second warning
          </label>
          <div className="rounded-xl border border-slate-700 p-6 text-center space-y-3">
            <Phone className="mx-auto h-8 w-8 text-cyan-400" />
            <h2 className="font-semibold">{scenario.caller}</h2>
            <p role="status" className="capitalize text-slate-300">{call.status === 'idle' ? 'Ready for a demo call' : call.status === 'active' ? 'Connected · simulated call' : call.status}</p>
            <div className="flex flex-wrap justify-center gap-3">
              {call.status === 'idle' && <button className={button} onClick={startCall}>Simulate incoming call</button>}
              {call.status === 'ringing' && <>
                <button className={`${button} text-emerald-400`} onClick={() => setCall(previous => ({ ...previous, status: 'active' }))}>Answer</button>
                <button className={`${button} text-red-400`} onClick={() => endCall('Declined before answering')}>Decline</button>
              </>}
              {call.status === 'active' && <button className={`${button} text-red-400`} onClick={() => endCall('Ended by user')}><PhoneOff className="mr-2 inline h-4 w-4" />End simulated call</button>}
              {call.status === 'ended' && <button className={button} onClick={() => {
                setHistory(previous => [{ caller: scenario.caller, outcome: call.outcome, reasons: call.assessment.reasons }, ...previous].slice(0, 10));
                setCall(emptyCall); setDraft('');
              }}>New demo</button>}
            </div>
          </div>
          {(call.assessment.risk === 'high' || call.assessment.risk === 'warning') && <div role="alert" className={`rounded-xl border p-4 space-y-2 ${call.assessment.risk === 'high' ? 'border-red-500/50 bg-red-950/40 text-red-200' : 'border-amber-500/50 bg-amber-950/40 text-amber-200'}`}>
            <h3 className="font-bold"><ShieldAlert className="mr-2 inline h-5 w-5" />Possible scam · {call.assessment.risk === 'high' ? 'High risk' : 'Caution'}</h3>
            <ul className="list-disc pl-5 text-sm">{call.assessment.reasons.map(reason => <li key={reason}>{reason}</li>)}</ul>
            <p className="text-sm">Do not share private codes or send money. Verify the caller through a trusted channel.</p>
            {call.status === 'active' && call.assessment.risk === 'high' && autoEnd && <p className="font-semibold">Ending this simulated call in two seconds…</p>}
          </div>}
          {call.assessment.risk === 'no_indicators' && <p className="text-sm text-slate-300">No matching scam indicators so far. This does not verify the caller or guarantee safety.</p>}
          {call.status === 'ended' && <p role="status" className="rounded-lg bg-slate-800 p-3">{call.outcome}. No real call was affected.</p>}
        </section>

        <section className="space-y-4 rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
          <h2 className="text-lg font-semibold">Caller messages</h2>
          <p className="text-sm text-slate-400">Sample messages appear every 2.5 seconds after answering. Try your own caller request below.</p>
          <div role="log" aria-label="Simulated caller transcript" className="max-h-80 min-h-40 space-y-3 overflow-y-auto">
            {call.messages.length ? call.messages.map((message, index) => <p key={index} className="rounded-xl bg-slate-800 p-3 text-sm break-words">{message}</p>) : <p className="text-sm text-slate-500">No conversation yet.</p>}
          </div>
          <form className="space-y-3" onSubmit={event => { event.preventDefault(); addMessage(draft); setDraft(''); }}>
            <label htmlFor="caller-message" className="block text-sm">Custom caller message</label>
            <textarea id="caller-message" className="w-full rounded-lg border border-slate-700 bg-slate-950 p-3" maxLength={500} rows={3} value={draft} disabled={call.status !== 'active' || call.messages.length >= 50} onChange={event => setDraft(event.target.value)} placeholder="Example: Please send me your verification code." />
            <button className={button} disabled={call.status !== 'active' || !draft.trim() || call.messages.length >= 50}>Add caller message</button>
          </form>
        </section>
      </div>
      <section className="space-y-3 rounded-2xl border border-slate-800 p-6">
        <h2 className="text-lg font-semibold">Demo call history</h2>
        <p className="text-sm text-slate-400">Last ten previous calls on this page. Cleared when you leave or reload; separate from the audio audit log.</p>
        {history.length === 0 ? <p className="text-sm text-slate-500">Finish a call and choose New demo to add it here.</p> : history.map((entry, index) => <div key={index} className="border-t border-slate-800 pt-3 text-sm"><p className="font-semibold">{entry.caller} · {entry.outcome}</p><p className="text-slate-400">{entry.reasons.join(' ') || 'No scam indicators recorded.'}</p></div>)}
      </section>
    </div>
  );
}
