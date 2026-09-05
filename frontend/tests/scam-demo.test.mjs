import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  assessScamTranscript,
  demoScenarios,
  getDemoScenario,
  computeAcousticAssessment,
  computeUnifiedAssessment,
  runScenario,
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

// Phase 2.5: Presentation-Ready Scenario Automation Tests

test('1. built-in scam scenarios contain semantic indicators', () => {
  const scamScenarios = demoScenarios.filter((s) => s.id !== 'ordinary');
  assert.ok(scamScenarios.length >= 3, 'Expected at least 3 scam scenarios');

  for (const scenario of scamScenarios) {
    const assessment = assessScamTranscript(scenario.messages);
    assert.ok(
      assessment.reasons.length > 0,
      `Scenario "${scenario.name}" must produce matched semantic reasons`
    );
    assert.equal(
      assessment.risk,
      'high',
      `Scenario "${scenario.name}" must evaluate to high scam risk`
    );
    assert.ok(
      Array.isArray(scenario.expectedIndicators) && scenario.expectedIndicators.length > 0,
      `Scenario "${scenario.name}" must declare expectedIndicators`
    );
    assert.ok(
      Boolean(scenario.title && scenario.impersonationContext),
      `Scenario "${scenario.name}" must include title and impersonationContext`
    );
  }
});

test('2. benign control remains benign/low when acoustic is genuine', () => {
  const benignScenario = demoScenarios.find((s) => s.id === 'ordinary');
  assert.ok(benignScenario, 'Benign control scenario must exist');

  const semantic = assessScamTranscript(benignScenario.messages);
  assert.equal(semantic.risk, 'no_indicators');
  assert.equal(semantic.reasons.length, 0);

  const unified = computeUnifiedAssessment(mockLikelyGenuineAcoustic, semantic);
  assert.equal(unified.verdict, 'LOW');
  assert.match(unified.headline, /low threat/i);
});

test('3. missing audio path does not fabricate acoustic assessment', async () => {
  for (const scenario of demoScenarios) {
    const result = await runScenario({
      scenario: { ...scenario, sampleAudioPath: null },
      attachedFile: null,
    });
    assert.equal(result.acoustic.syntheticProbability, null);
    assert.equal(result.acoustic.confidence, null);
    assert.equal(result.acoustic.prediction, null);
    assert.notEqual(result.acoustic.status, 'synthetic_detected');
    assert.notEqual(result.acoustic.status, 'likely_genuine');
    assert.equal(result.acoustic.status, 'audio_unavailable');
    assert.match(result.acoustic.label, /unavailable — semantic risk only/i);
  }
});

test('4. unified verdict still works when acoustic layer is unavailable', () => {
  const unavailableAcousticStates = [
    {
      status: 'audio_unavailable',
      label: 'Acoustic analysis unavailable — semantic risk only',
      syntheticProbability: null,
      confidence: null,
      riskLevel: 'not_assessed',
      prediction: null,
      action: null,
      engineType: null,
      modelVersion: null,
    },
    {
      status: 'error',
      label: 'Acoustic analysis unavailable — semantic risk only',
      syntheticProbability: null,
      confidence: null,
      riskLevel: 'not_assessed',
      prediction: null,
      action: null,
      engineType: null,
      modelVersion: null,
      errorMessage: 'Backend server is offline',
    },
  ];

  for (const acoustic of unavailableAcousticStates) {
    // High scam intent without acoustic => MEDIUM with clear notice
    const scamSemantic = assessScamTranscript([
      'Your account will be blocked immediately.',
      'Please tell me your OTP to verify your account.',
    ]);
    assert.equal(scamSemantic.risk, 'high');
    const scamUnified = computeUnifiedAssessment(acoustic, scamSemantic);
    assert.equal(scamUnified.verdict, 'MEDIUM');
    assert.match(scamUnified.acousticSummary, /Acoustic analysis unavailable — semantic risk only/);
    assert.match(scamUnified.explanation, /Acoustic analysis unavailable — semantic risk only/);

    // Benign transcript without acoustic => UNASSESSED with clear notice
    const benignSemantic = assessScamTranscript([
      'Hello, are we still meeting tomorrow for the project review?',
    ]);
    assert.equal(benignSemantic.risk, 'no_indicators');
    const benignUnified = computeUnifiedAssessment(acoustic, benignSemantic);
    assert.equal(benignUnified.verdict, 'UNASSESSED');
    assert.match(benignUnified.acousticSummary, /Acoustic analysis unavailable — semantic risk only/);
    assert.match(benignUnified.explanation, /Acoustic analysis unavailable — semantic risk only/);
  }
});

test('5. no scenario contains a hard-coded synthetic probability', () => {
  for (const scenario of demoScenarios) {
    const s = scenario;
    assert.equal(s.syntheticProbability, undefined, `Scenario "${scenario.name}" must not define syntheticProbability`);
    assert.equal(s.confidence, undefined, `Scenario "${scenario.name}" must not define confidence`);
    assert.equal(s.prediction, undefined, `Scenario "${scenario.name}" must not define prediction`);
    assert.equal(s.score, undefined, `Scenario "${scenario.name}" must not define score`);
    assert.equal(s.pSynth, undefined, `Scenario "${scenario.name}" must not define pSynth`);
  }
});

test('6. no scenario claims guaranteed identity verification or guaranteed safety', () => {
  // Check scenario definitions
  for (const scenario of demoScenarios) {
    const text = `${scenario.name} ${scenario.caller} ${scenario.impersonationContext} ${scenario.expectedPattern} ${scenario.messages.join(' ')}`.toLowerCase();
    assert.doesNotMatch(text, /\bguarantee(s|d)? safety\b/);
    assert.doesNotMatch(text, /\bguarantee(s|d)? identity\b/);
    assert.doesNotMatch(text, /\bverified safe\b/);
    assert.doesNotMatch(text, /\bverified identity\b/);
  }

  // Check all possible unified outputs across scenarios and acoustic states
  const testAcoustics = [
    mockHighSyntheticAcoustic,
    mockLikelyGenuineAcoustic,
    mockUnassessedAcoustic,
    {
      status: 'audio_unavailable',
      label: 'Acoustic analysis unavailable — semantic risk only',
      syntheticProbability: null,
      confidence: null,
      riskLevel: 'not_assessed',
      prediction: null,
      action: null,
      engineType: null,
      modelVersion: null,
    },
    {
      status: 'error',
      label: 'Acoustic analysis unavailable — semantic risk only',
      syntheticProbability: null,
      confidence: null,
      riskLevel: 'not_assessed',
      prediction: null,
      action: null,
      engineType: null,
      modelVersion: null,
      errorMessage: 'Audio fixture not found: 404',
    },
  ];

  for (const scenario of demoScenarios) {
    const semantic = assessScamTranscript(scenario.messages);
    for (const acoustic of testAcoustics) {
      const assessment = computeUnifiedAssessment(acoustic, semantic);
      const unifiedText = `${assessment.headline} ${assessment.explanation} ${assessment.acousticSummary} ${assessment.semanticSummary} ${assessment.recommendedAction} ${assessment.disclaimer}`.toLowerCase();
      assert.doesNotMatch(unifiedText, /\bguarantee(s|d)? safety\b/);
      assert.doesNotMatch(unifiedText, /\bguarantee(s|d)? identity\b/);
      assert.doesNotMatch(unifiedText, /\bverified safe\b/);
      assert.doesNotMatch(unifiedText, /\bverified identity\b/);
    }
  }
});

test('runScenario handles backend offline / failure gracefully without dropping semantic analysis', async () => {
  const scenario = demoScenarios[0];
  const dummyFile = { name: 'sample.wav', type: 'audio/wav' };
  const mockFailingUpload = async () => {
    throw new Error('Backend offline (ECONNREFUSED)');
  };

  const result = await runScenario({
    scenario,
    attachedFile: dummyFile,
    uploadAndDetectFn: mockFailingUpload,
  });

  assert.equal(result.acoustic.status, 'error');
  assert.equal(result.acoustic.errorMessage, 'Backend offline (ECONNREFUSED)');
  assert.match(result.acoustic.label, /Acoustic analysis unavailable — semantic risk only/);
  assert.equal(result.semantic.risk, 'high');
  assert.equal(result.unified.verdict, 'MEDIUM');
  assert.match(result.unified.acousticSummary, /Acoustic analysis unavailable — semantic risk only/);
});

test('runScenario handles successful backend AASIST inference result', async () => {
  const scenario = demoScenarios[0];
  const dummyFile = { name: 'bank_sample.wav', type: 'audio/wav' };
  const mockSuccessUpload = async () => ({
    id: 'det-123',
    engine_type: 'aasist',
    prediction: 'synthetic',
    confidence: 0.94,
    risk_level: 'high',
    model_version: 'aasist-v1',
    created_at: new Date().toISOString(),
    decision: {
      action: 'BLOCK',
      synthetic_probability: 0.94,
      decision_message: 'Synthetic voice detected',
      policy_version: 'v1.0',
      reason_codes: ['SYNTHETIC_VOICE'],
      recommended_steps: [],
    },
  });

  const result = await runScenario({
    scenario,
    attachedFile: dummyFile,
    uploadAndDetectFn: mockSuccessUpload,
  });

  assert.equal(result.acoustic.status, 'synthetic_detected');
  assert.equal(result.acoustic.syntheticProbability, 0.94);
  assert.equal(result.semantic.risk, 'high');
  assert.equal(result.unified.verdict, 'HIGH');
  assert.match(result.unified.headline, /HIGH THREAT/i);
});

test('getDemoScenario supports backward-compatible ID lookup', () => {
  assert.equal(getDemoScenario('otp').id, 'otp');
  assert.equal(getDemoScenario('payment').id, 'executive');
  assert.equal(getDemoScenario('support').id, 'support');
  assert.equal(getDemoScenario('ordinary').id, 'ordinary');
});
