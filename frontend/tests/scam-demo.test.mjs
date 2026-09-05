import { test } from 'node:test';
import assert from 'node:assert/strict';
import { assessScamTranscript, demoScenarios } from '../src/lib/scam-demo.ts';

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
