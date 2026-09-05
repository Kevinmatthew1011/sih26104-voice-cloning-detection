export type ScamRisk = 'unassessed' | 'no_indicators' | 'warning' | 'high';
export interface ScamAssessment { risk: ScamRisk; reasons: string[] }
export interface DemoScenario { id: string; name: string; caller: string; messages: string[] }

export const demoScenarios: DemoScenario[] = [
  { id: 'otp', name: 'Bank impersonation', caller: 'Unverified bank representative', messages: [
    'Hello, I am calling about your bank account.',
    'Your account will be blocked. Act now to avoid losing access.',
    'Please tell me your OTP to verify your account.',
  ] },
  { id: 'payment', name: 'Urgent payment demand', caller: 'Unknown caller', messages: [
    'There is a problem with your delivery.',
    'Transfer money to this safe account immediately.',
  ] },
  { id: 'support', name: 'Remote-access scam', caller: 'Unverified technical support', messages: [
    'I am calling from technical support.',
    'Install AnyDesk and give me remote access to your computer.',
  ] },
  { id: 'ordinary', name: 'Ordinary conversation', caller: 'Demo contact', messages: [
    'Hello, are we still meeting tomorrow?',
    'I can meet you at the cafe at ten.',
    'Great, see you then.',
  ] },
];

// Demonstration heuristics only: no calibrated score, identity verification, or ML claim.
export function assessScamTranscript(messages: string[]): ScamAssessment {
  const reasons = new Set<string>();
  let high = false;
  for (const message of messages) {
    for (const sentence of message.toLowerCase().split(/[.!?;\n]+/)) {
      const text = sentence.replace(/[’']/g, "'");
      // Ignore common safety advice; complex negation remains outside this demo's scope.
      if (/\b(never|do not|don't|not to)\b/.test(text)) continue;
      if (/\b(share|tell|read|give|send)\b.{0,50}\b(otp|one.time password|password|pin|verification code)\b/.test(text)) {
        reasons.add('Caller requests a private code or password.'); high = true;
      }
      if (/\b(install|download|enable|give)\b.{0,60}\b(anydesk|teamviewer|remote access)\b/.test(text)) {
        reasons.add('Caller requests remote access to your device.'); high = true;
      }
      if (/\b(transfer|send|pay|buy)\b.{0,60}\b(money|payment|gift cards?|crypto|bitcoin)\b/.test(text)) {
        reasons.add('Caller requests a payment or money transfer.');
      }
      if (/\b(urgent|immediately|act now|arrest|account will be blocked|safe account)\b/.test(text)) {
        reasons.add('Caller uses urgency, threats, or a safe-account claim.');
      }
    }
  }
  if (reasons.has('Caller requests a payment or money transfer.') && reasons.has('Caller uses urgency, threats, or a safe-account claim.')) high = true;
  return { risk: high ? 'high' : reasons.size ? 'warning' : messages.some(m => m.trim()) ? 'no_indicators' : 'unassessed', reasons: [...reasons] };
}
