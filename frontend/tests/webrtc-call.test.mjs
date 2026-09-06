import { test } from 'node:test';
import assert from 'node:assert/strict';
import { WebRTCCallSession } from '../src/lib/webrtc-call.ts';

function environment() {
  const sockets = [];
  const peers = [];
  const stream = () => ({ getAudioTracks() { return this.tracks; }, getTracks() { return this.tracks; }, tracks: [{ enabled: true, stop() { this.stopped = true; } }] });
  class Socket {
    static OPEN = 1;
    readyState = 0;
    constructor() { sockets.push(this); }
    send(data) { for (const other of sockets) if (other !== this && other.readyState === 1) other.onmessage?.({ data }); }
    open() { this.readyState = 1; this.onopen?.(); }
    close() { this.readyState = 3; }
  }
  class Peer {
    connectionState = 'new'; signalingState = 'stable'; remoteDescription = null;
    tracks = [];
    constructor() { peers.push(this); }
    addTrack(track) { this.tracks.push(track); }
    async createOffer() { return { type: 'offer', sdp: 'test-offer' }; }
    async createAnswer() { return { type: 'answer', sdp: 'test-answer' }; }
    async setLocalDescription(sdp) { this.localDescription = sdp; this.signalingState = sdp.type === 'offer' ? 'have-local-offer' : 'stable'; }
    async setRemoteDescription(sdp) { this.remoteDescription = sdp; this.signalingState = sdp.type === 'answer' ? 'stable' : 'have-remote-offer'; }
    async addIceCandidate() {}
    close() { this.connectionState = 'closed'; }
  }
  globalThis.window = { location: { protocol: 'http:' } };
  Object.defineProperty(globalThis, 'navigator', { configurable: true, value: { mediaDevices: { getUserMedia: async () => stream() } } });
  globalThis.WebSocket = Socket;
  globalThis.RTCPeerConnection = Peer;
  globalThis.RTCSessionDescription = class { constructor(value) { Object.assign(this, value); } };
  globalThis.RTCIceCandidate = class { constructor(value) { Object.assign(this, value); } };
  return { sockets, peers, stream };
}
const flush = async () => { for (let i = 0; i < 20; i++) await Promise.resolve(); };
for (const protectedFirst of [false, true]) {
  test(`WebSocket-only negotiation survives delayed opening; protected first=${protectedFirst}`, async () => {
    const { sockets, peers, stream } = environment();
    const caller = new WebRTCCallSession();
    const receiver = new WebRTCCallSession();
    let callerRemote, protectedRemote, ended;
    const a = () => caller.startCaller('test', { onRemoteStream: s => callerRemote = s });
    const b = () => receiver.startProtectedUser('test', { onRemoteStream: s => protectedRemote = s, onConnectionStatusChange: s => ended = s });
    if (protectedFirst) { await b(); sockets[0].open(); await a(); sockets[1].open(); }
    else { await a(); sockets[0].open(); await b(); sockets[1].open(); }
    await flush();
    assert.ok(peers.every(p => p.remoteDescription));
    assert.ok(peers.every(p => p.tracks.length === 1), 'both peers publish a microphone track');
    const remote = stream();
    peers[protectedFirst ? 1 : 0].ontrack({ streams: [remote] });
    peers[protectedFirst ? 0 : 1].ontrack({ streams: [remote] });
    assert.equal(callerRemote, remote);
    assert.equal(protectedRemote, remote);
    assert.notEqual(protectedRemote, receiver.getLocalStream());
    caller.endCall(); await flush();
    assert.equal(ended, 'ENDED');
    assert.equal(receiver.isCallActive(), false);
    assert.ok(peers.every(p => p.tracks[0].stopped));
  });
}

import { CallAudioStreamClient, computeLiveAcousticAssessment } from '../src/lib/call-audio-stream.ts';
test('remote analysis never captures or stops the protected microphone or remote tracks', async () => {
  const { stream } = environment();
  navigator.mediaDevices.getUserMedia = () => { throw new Error('Local mic must not be requested'); };
  const remote = stream();
  const client = new CallAudioStreamClient();
  await client.startFromStream(remote, {}, { engine: 'aasist' });
  client.disconnect();
  assert.equal(remote.tracks[0].stopped, undefined);
});
test('mock model version cannot be labeled AASIST even with a conflicting engine tag', () => {
  const result = computeLiveAcousticAssessment({engine:'aasist', model_version:'mock-v1', synthetic_probability:0.2, prediction:'real', risk_level:'low', action:'allow'});
  assert.equal(result.engineType, 'MOCK ENGINE');
});
