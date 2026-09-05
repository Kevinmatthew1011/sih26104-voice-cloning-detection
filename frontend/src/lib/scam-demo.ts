import type { DetectionResult } from './types';

export type ScamRisk = 'unassessed' | 'no_indicators' | 'warning' | 'high';
export interface ScamAssessment {
  risk: ScamRisk;
  reasons: string[];
}

export type AcousticStatus =
  | 'not_analyzed'
  | 'audio_unavailable'
  | 'analyzing'
  | 'synthetic_detected'
  | 'likely_genuine'
  | 'inconclusive'
  | 'error';

export interface AcousticAssessment {
  status: AcousticStatus;
  label: string;
  syntheticProbability: number | null;
  confidence: number | null;
  riskLevel: 'low' | 'medium' | 'high' | 'not_assessed';
  prediction: 'real' | 'synthetic' | 'replay' | 'unknown' | null;
  action: 'ALLOW' | 'VERIFY' | 'BLOCK' | 'NOT_EVALUATED' | null;
  engineType: string | null;
  modelVersion: string | null;
  rawResult?: DetectionResult | null;
  errorMessage?: string | null;
}

export type UnifiedVerdictLevel = 'UNASSESSED' | 'LOW' | 'MEDIUM' | 'HIGH';

export interface UnifiedAssessment {
  verdict: UnifiedVerdictLevel;
  headline: string;
  explanation: string;
  acousticSummary: string;
  semanticSummary: string;
  recommendedAction: string;
  disclaimer: string;
}

export interface DemoScenario {
  id: string;
  name: string;
  caller: string;
  expectedPattern: string;
  sampleAudioPath?: string | null;
  messages: string[];
}

export const demoScenarios: DemoScenario[] = [
  {
    id: 'otp',
    name: 'Bank impersonation',
    caller: 'Unverified bank representative',
    expectedPattern: 'Authority pressure + private OTP theft demand',
    sampleAudioPath: null,
    messages: [
      'Hello, I am calling about your bank account.',
      'Your account will be blocked. Act now to avoid losing access.',
      'Please tell me your OTP to verify your account.',
    ],
  },
  {
    id: 'payment',
    name: 'Urgent payment demand',
    caller: 'Unknown caller',
    expectedPattern: 'Delivery issue pretext + coercive money transfer',
    sampleAudioPath: null,
    messages: [
      'There is a problem with your delivery.',
      'Transfer money to this safe account immediately.',
    ],
  },
  {
    id: 'support',
    name: 'Remote-access scam',
    caller: 'Unverified technical support',
    expectedPattern: 'Tech support impersonation + remote desktop takeover',
    sampleAudioPath: null,
    messages: [
      'I am calling from technical support.',
      'Install AnyDesk and give me remote access to your computer.',
    ],
  },
  {
    id: 'ordinary',
    name: 'Ordinary conversation',
    caller: 'Demo contact',
    expectedPattern: 'Benign coordination / meeting schedule',
    sampleAudioPath: null,
    messages: [
      'Hello, are we still meeting tomorrow?',
      'I can meet you at the cafe at ten.',
      'Great, see you then.',
    ],
  },
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
        reasons.add('Caller requests a private code or password.');
        high = true;
      }
      if (/\b(install|download|enable|give)\b.{0,60}\b(anydesk|teamviewer|remote access)\b/.test(text)) {
        reasons.add('Caller requests remote access to your device.');
        high = true;
      }
      if (/\b(transfer|send|pay|buy)\b.{0,60}\b(money|payment|gift cards?|crypto|bitcoin)\b/.test(text)) {
        reasons.add('Caller requests a payment or money transfer.');
      }
      if (/\b(urgent|immediately|act now|arrest|account will be blocked|safe account)\b/.test(text)) {
        reasons.add('Caller uses urgency, threats, or a safe-account claim.');
      }
    }
  }
  if (reasons.has('Caller requests a payment or money transfer.') && reasons.has('Caller uses urgency, threats, or a safe-account claim.')) {
    high = true;
  }
  return {
    risk: high ? 'high' : reasons.size ? 'warning' : messages.some(m => m.trim()) ? 'no_indicators' : 'unassessed',
    reasons: [...reasons],
  };
}

export function computeAcousticAssessment(
  result?: DetectionResult | null,
  error?: string | null
): AcousticAssessment {
  if (error) {
    return {
      status: 'error',
      label: 'Acoustic Analysis Error',
      syntheticProbability: null,
      confidence: null,
      riskLevel: 'not_assessed',
      prediction: null,
      action: null,
      engineType: null,
      modelVersion: null,
      errorMessage: error,
    };
  }

  if (!result) {
    return {
      status: 'not_analyzed',
      label: 'Not analyzed',
      syntheticProbability: null,
      confidence: null,
      riskLevel: 'not_assessed',
      prediction: null,
      action: null,
      engineType: null,
      modelVersion: null,
    };
  }

  const pSynth =
    result.decision?.synthetic_probability ??
    (typeof result.metadata_json?.synthetic_probability === 'number'
      ? (result.metadata_json.synthetic_probability as number)
      : result.prediction === 'synthetic'
      ? result.confidence
      : result.prediction === 'real'
      ? 1 - result.confidence
      : null);

  const isSynthetic = result.prediction === 'synthetic' || (pSynth !== null && pSynth >= 0.50);
  const isGenuine = result.prediction === 'real' || (pSynth !== null && pSynth < 0.50);

  const status: AcousticStatus = isSynthetic
    ? 'synthetic_detected'
    : isGenuine
    ? 'likely_genuine'
    : 'inconclusive';

  const label = isSynthetic
    ? 'Synthetic Voice Detected'
    : isGenuine
    ? 'Likely Genuine Voice'
    : 'Inconclusive Voice Telemetry';

  return {
    status,
    label,
    syntheticProbability: pSynth !== null ? Number(pSynth.toFixed(4)) : null,
    confidence: result.confidence ?? null,
    riskLevel: result.risk_level ?? (isSynthetic ? 'high' : 'low'),
    prediction: result.prediction ?? null,
    action: result.action ?? result.decision?.action ?? null,
    engineType: result.engine_type ?? null,
    modelVersion: result.model_version ?? null,
    rawResult: result,
  };
}

export function computeUnifiedAssessment(
  acoustic: AcousticAssessment,
  semantic: ScamAssessment
): UnifiedAssessment {
  const isAcousticAssessed =
    acoustic.status === 'synthetic_detected' ||
    acoustic.status === 'likely_genuine' ||
    acoustic.status === 'inconclusive';

  const isAcousticSynthetic =
    acoustic.status === 'synthetic_detected' ||
    (acoustic.syntheticProbability !== null && acoustic.syntheticProbability >= 0.70) ||
    (acoustic.prediction === 'synthetic' && acoustic.riskLevel === 'high');

  const isAcousticModerate =
    acoustic.status === 'inconclusive' ||
    acoustic.riskLevel === 'medium' ||
    (acoustic.syntheticProbability !== null &&
      acoustic.syntheticProbability >= 0.50 &&
      acoustic.syntheticProbability < 0.70);

  const isAcousticGenuine =
    acoustic.status === 'likely_genuine' ||
    (acoustic.syntheticProbability !== null && acoustic.syntheticProbability < 0.50) ||
    (acoustic.prediction === 'real' && acoustic.riskLevel === 'low');

  const isSemanticHigh = semantic.risk === 'high';
  const isSemanticWarning = semantic.risk === 'warning';
  const isSemanticBenign = semantic.risk === 'no_indicators';
  const isSemanticUnassessed = semantic.risk === 'unassessed';

  const disclaimer =
    'Unified threat assessment is a dual-layer risk evaluation based on acoustic spoof telemetry and conversational heuristics. It provides fraud risk scoring, not absolute certainty or proof of caller identity.';

  // HIGH: strong acoustic synthetic evidence AND strong semantic scam intent
  if (isAcousticSynthetic && isSemanticHigh) {
    return {
      verdict: 'HIGH',
      headline: 'HIGH THREAT — Possible AI-Assisted Impersonation Scam',
      explanation:
        'Acoustic analysis flagged strong synthetic voice indicators, and conversational analysis detected overt scam patterns (credential theft, remote access, or coercive financial demands).',
      acousticSummary: `Synthetic voice indicators detected${
        acoustic.syntheticProbability !== null ? ` (P_synth=${(acoustic.syntheticProbability * 100).toFixed(1)}%)` : ''
      } by ${acoustic.engineType || 'AASIST'}.`,
      semanticSummary: `High-risk scam intent flagged: ${semantic.reasons.join(' ')}`,
      recommendedAction:
        'Immediately disconnect. Do not share OTPs, passwords, or initiate fund transfers. Independently verify the caller through official contact details.',
      disclaimer,
    };
  }

  // MEDIUM: only one layer is strongly suspicious OR both layers have moderate signals
  if (
    (isAcousticSynthetic && (isSemanticBenign || isSemanticWarning || isSemanticUnassessed)) ||
    (isSemanticHigh && (isAcousticGenuine || !isAcousticAssessed)) ||
    (isAcousticModerate && (isSemanticHigh || isSemanticWarning || isSemanticBenign)) ||
    (isSemanticWarning && (isAcousticSynthetic || isAcousticModerate || isAcousticGenuine || !isAcousticAssessed))
  ) {
    let headline = 'MEDIUM THREAT — Suspicious Fraud Indicators';
    let explanation = '';

    if (isAcousticSynthetic && (isSemanticBenign || isSemanticUnassessed)) {
      headline = 'SUSPICIOUS — Potential Synthetic Voice on Neutral Content';
      explanation =
        'Acoustic analysis indicates synthetic or cloned voice characteristics, though no explicit financial or credential scam keywords matched in the transcript.';
    } else if (isSemanticHigh && isAcousticGenuine) {
      headline = 'CAUTION — High Scam Intent with Organic Voice Characteristics';
      explanation =
        'Conversational heuristics flagged high-risk scam intent, although voice acoustics appear consistent with human speech.';
    } else if (isSemanticHigh && !isAcousticAssessed) {
      headline = 'CAUTION — High Scam Intent (Acoustic Unanalyzed)';
      explanation =
        'High-risk conversational scam patterns detected in transcript. Voice cloning acoustic analysis has not been executed on this call stream.';
    } else {
      headline = 'CAUTION — Moderate Fraud Risk Indicators';
      explanation =
        'Moderate scam phrasing or acoustic ambiguity detected. Elevated vigilance is advised.';
    }

    return {
      verdict: 'MEDIUM',
      headline,
      explanation,
      acousticSummary: isAcousticAssessed
        ? `${acoustic.label}${acoustic.syntheticProbability !== null ? ` (P_synth=${(acoustic.syntheticProbability * 100).toFixed(1)}%)` : ''}`
        : 'Acoustic voice analysis not performed or unavailable.',
      semanticSummary:
        semantic.reasons.length > 0
          ? `Scam indicators flagged: ${semantic.reasons.join(' ')}`
          : 'No explicit keyword triggers detected in transcript.',
      recommendedAction:
        'Exercise heightened caution. Verify caller identity through independent, trusted channels before taking any action.',
      disclaimer,
    };
  }

  // LOW: both layers are low-risk / benign
  if (isAcousticGenuine && isSemanticBenign) {
    return {
      verdict: 'LOW',
      headline: 'LOW THREAT — Nominal Indicators',
      explanation:
        'Acoustic features appear consistent with genuine human speech, and conversation content exhibits no suspicious scam patterns.',
      acousticSummary: `Likely genuine voice${
        acoustic.syntheticProbability !== null ? ` (P_synth=${(acoustic.syntheticProbability * 100).toFixed(1)}%)` : ''
      }.`,
      semanticSummary: 'No suspicious scam indicators identified in transcript.',
      recommendedAction:
        'Standard operational handling. Note: low threat does not verify caller identity or guarantee caller authenticity.',
      disclaimer:
        'Low risk does NOT imply verified safety. Spoof detection and keyword heuristics cannot guarantee absolute authenticity.',
    };
  }

  // UNASSESSED: acoustic analysis has not run and semantic evidence is insufficient
  return {
    verdict: 'UNASSESSED',
    headline: 'UNASSESSED — Telemetry Incomplete',
    explanation:
      'Acoustic voice analysis has not run, and the conversation transcript contains insufficient content for reliable threat evaluation.',
    acousticSummary: isAcousticAssessed ? acoustic.label : 'Acoustic analysis has not run.',
    semanticSummary:
      semantic.risk === 'unassessed'
        ? 'No caller messages analyzed.'
        : 'Transcript contains insufficient or baseline conversation.',
    recommendedAction: 'Awaiting audio sample or caller transcript to begin dual-layer assessment.',
    disclaimer,
  };
}
