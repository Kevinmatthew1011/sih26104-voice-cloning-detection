import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  assessScamTranscript,
  demoScenarios,
  computeAcousticAssessment,
  computeUnifiedAssessment,
} from '../src/lib/scam-demo.ts';

test('unassessed and ordinary speech never claim verified safety', () => {
  assert.equal(assessScamTranscript([]).risk, 'unassessed');
  assert.equal(assessScamTranscript(['Hello, see you tomorrow.']).risk, 'no_indicators');
});
test('scam scenarios escalate, ordinary scenario does not', () => {
  for (const scenario of demoScenarios) {
    assert.equal(assessScamTranscript(scenario.messages).risk, scenario.id === 'ordinary' ? 'no_indicators' : 'high');
  }
});
test('money alone warns; urgency across messages escalates', () => {
  assert.equal(assessScamTranscript(['Please send money.']).risk, 'warning');
  assert.equal(assessScamTranscript(['Please send money.', 'Act now!']).risk, 'high');
});
test('safety advice and incidental words do not trigger credential flags', () => {
  for (const text of ['Never share your OTP.', 'Do not send money.', 'Don’t tell me your PIN.', 'I will give you a pinball machine.']) {
    assert.equal(assessScamTranscript([text]).risk, 'no_indicators');
  }
});
test('case insensitive credential requests, remote access and deduplicated reasons', () => {
  assert.equal(assessScamTranscript(['SEND ME YOUR VERIFICATION CODE']).risk, 'high');
  assert.equal(assessScamTranscript(['Please install AnyDesk']).risk, 'high');
  assert.equal(assessScamTranscript(['Tell me your OTP.', 'Give me your password.']).reasons.length, 1);
});

// Dual-layer assessment unit tests

const mockHighSyntheticAcoustic = {
  status: 'synthetic_detected',
  label: 'Synthetic Voice Detected',
  syntheticProbability: 0.95,
  confidence: 0.95,
  riskLevel: 'high',
  prediction: 'synthetic',
  action: 'BLOCK',
  engineType: 'aasist',
  modelVersion: 'aasist-v1',
};

const mockLikelyGenuineAcoustic = {
  status: 'likely_genuine',
  label: 'Likely Genuine Voice',
  syntheticProbability: 0.05,
  confidence: 0.95,
  riskLevel: 'low',
  prediction: 'real',
  action: 'ALLOW',
  engineType: 'aasist',
  modelVersion: 'aasist-v1',
};

const mockUnassessedAcoustic = {
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

test('case 1: synthetic/high acoustic + strong scam intent => HIGH', () => {
  const strongScam = assessScamTranscript(['Please tell me your OTP to verify your account.']);
  assert.equal(strongScam.risk, 'high');
  const unified = computeUnifiedAssessment(mockHighSyntheticAcoustic, strongScam);
  assert.equal(unified.verdict, 'HIGH');
  assert.match(unified.headline, /HIGH THREAT/i);
});

test('case 2: genuine/low acoustic + strong scam intent => at least MEDIUM', () => {
  const strongScam = assessScamTranscript(['Install AnyDesk and give me remote access to your computer.']);
  assert.equal(strongScam.risk, 'high');
  const unified = computeUnifiedAssessment(mockLikelyGenuineAcoustic, strongScam);
  assert.ok(unified.verdict === 'MEDIUM' || unified.verdict === 'HIGH');
  assert.equal(unified.verdict, 'MEDIUM');
});

test('case 3: synthetic/high acoustic + benign transcript => at least MEDIUM', () => {
  const benign = assessScamTranscript(['Hello, are we still meeting tomorrow?']);
  assert.equal(benign.risk, 'no_indicators');
  const unified = computeUnifiedAssessment(mockHighSyntheticAcoustic, benign);
  assert.ok(unified.verdict === 'MEDIUM' || unified.verdict === 'HIGH');
  assert.equal(unified.verdict, 'MEDIUM');
});

test('case 4: genuine/low acoustic + benign transcript => LOW', () => {
  const benign = assessScamTranscript(['Hello, see you at the cafe at ten.']);
  assert.equal(benign.risk, 'no_indicators');
  const unified = computeUnifiedAssessment(mockLikelyGenuineAcoustic, benign);
  assert.equal(unified.verdict, 'LOW');
  assert.match(unified.headline, /LOW THREAT/i);
});

test('case 5: unavailable acoustic + insufficient semantic evidence => UNASSESSED', () => {
  const unassessedSemantic = assessScamTranscript([]);
  assert.equal(unassessedSemantic.risk, 'unassessed');
  const unified = computeUnifiedAssessment(mockUnassessedAcoustic, unassessedSemantic);
  assert.equal(unified.verdict, 'UNASSESSED');
});

test('case 6: no scenario claims verified safe', () => {
  const testAcoustics = [mockHighSyntheticAcoustic, mockLikelyGenuineAcoustic, mockUnassessedAcoustic];
  const testTranscripts = [
    [],
    ['Hello, how are you?'],
    ['Please send money.'],
    ['Transfer money immediately or your account will be blocked.'],
  ];

  for (const ac of testAcoustics) {
    for (const tr of testTranscripts) {
      const assessment = computeUnifiedAssessment(ac, assessScamTranscript(tr));
      const combinedText = `${assessment.headline} ${assessment.explanation} ${assessment.disclaimer}`.toLowerCase();
      assert.doesNotMatch(combinedText, /\bverified safe\b/);
      assert.doesNotMatch(combinedText, /\bguarantee(s|d)? safety\b/);
    }
  }
});

test('computeAcousticAssessment parses detection result schemas correctly', () => {
  const empty = computeAcousticAssessment(null);
  assert.equal(empty.status, 'not_analyzed');

  const withError = computeAcousticAssessment(null, 'Network timeout');
  assert.equal(withError.status, 'error');
  assert.equal(withError.errorMessage, 'Network timeout');

  const syntheticSample = computeAcousticAssessment({
    id: 'det-1',
    engine_type: 'aasist',
    prediction: 'synthetic',
    confidence: 0.98,
    risk_level: 'high',
    model_version: 'aasist-v1',
    processing_time_ms: 35,
    created_at: new Date().toISOString(),
    decision: {
      action: 'BLOCK',
      decision_message: 'Strong synthetic voice indicators detected.',
      synthetic_probability: 0.98,
      policy_version: 'v1.0',
      reason_codes: ['HIGH_SYNTHETIC'],
      recommended_steps: [],
    },
  });
  assert.equal(syntheticSample.status, 'synthetic_detected');
  assert.equal(syntheticSample.syntheticProbability, 0.98);
  assert.equal(syntheticSample.riskLevel, 'high');
});
