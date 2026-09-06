/**
 * WebRTC / VoIP Real Cross-Tab and Multi-Peer Call Manager.
 *
 * Provides real two-peer RTCPeerConnection audio transmission between:
 * - Tab A: Caller (captures real microphone, creates SDP Offer, transmits Opus RTP stream)
 * - Tab B: Protected User (receives caller MediaStream via ontrack, attaches to audible <audio>,
 *           and feeds remote audio ONLY into VOICE-GUARD acoustic detection).
 *
 * Signaling is exchanged through:
 * 1. FastAPI WebSocket signaling endpoint: /api/v1/webrtc/signal/{room_id}
 * 2. Same-origin BroadcastChannel('vg-rtc-{room_id}') for instantaneous zero-latency local tab discovery.
 */

export type WebRTCRole = 'caller' | 'protected_user';
export type WebRTCConnectionStatus = 'IDLE' | 'CONNECTING' | 'CONNECTED' | 'ENDED' | 'ERROR';
export type WebRTCMicStatus = 'ACTIVE' | 'MUTED' | 'ERROR';
export type WebRTCRemoteAudioStatus = 'WAITING' | 'ACTIVE' | 'PLAYING' | 'ERROR';

export interface WebRTCCallCallbacks {
  onRemoteStream?: (stream: MediaStream) => void;
  onConnectionStateChange?: (state: RTCPeerConnectionState) => void;
  onConnectionStatusChange?: (status: WebRTCConnectionStatus) => void;
  onMicStatusChange?: (status: WebRTCMicStatus) => void;
  onRemoteAudioStatusChange?: (status: WebRTCRemoteAudioStatus) => void;
  onError?: (error: string) => void;
  onDiagnostics?: (value: string) => void;
}

interface SignalingMessage {
  type: 'offer' | 'answer' | 'ice-candidate' | 'join' | 'leave';
  fromRole?: WebRTCRole;
  sdp?: RTCSessionDescriptionInit;
  candidate?: RTCIceCandidateInit;
  msgId?: string;
}

export class WebRTCCallSession {
  private pc: RTCPeerConnection | null = null;
  private localPc: RTCPeerConnection | null = null;
  private remotePc: RTCPeerConnection | null = null;
  private localStream: MediaStream | null = null;
  private remoteStream: MediaStream | null = null;
  private ws: WebSocket | null = null;
  private bc: BroadcastChannel | null = null;
  private role: WebRTCRole | null = null;
  private roomId: string = 'voiceguard-test';
  private callbacks: WebRTCCallCallbacks = {};
  private seenMsgIds = new Set<string>();
  private signalingChain: Promise<void> = Promise.resolve();
  private pendingCandidates: RTCIceCandidateInit[] = [];

  public isCallActive(): boolean {
    if (this.pc && this.pc.connectionState !== 'closed') return true;
    if (this.localPc && this.localPc.connectionState !== 'closed') return true;
    return false;
  }

  public getRemoteStream(): MediaStream | null {
    return this.remoteStream;
  }

  public getLocalStream(): MediaStream | null {
    return this.localStream;
  }

  public muteMicrophone(muted: boolean): void {
    if (this.localStream) {
      this.localStream.getAudioTracks().forEach((track) => {
        track.enabled = !muted;
      });
      this.callbacks.onMicStatusChange?.(muted ? 'MUTED' : 'ACTIVE');
    }
  }

  private initSignaling(roomId: string): void {
    this.roomId = roomId.trim().toLowerCase() || 'voiceguard-test';

    // 1. BroadcastChannel for same-origin tabs
    if (typeof window !== 'undefined' && 'BroadcastChannel' in window) {
      try {
        this.bc = new BroadcastChannel(`vg-rtc-${this.roomId}`);
        this.bc.onmessage = (event) => {
          this.enqueueSignal(event.data);
        };
      } catch {
        // BroadcastChannel not available
      }
    }

    // 2. WebSocket signaling for cross-browser / LAN peers
    if (typeof window !== 'undefined') {
      try {
        const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = process.env.NEXT_PUBLIC_API_URL
          ? process.env.NEXT_PUBLIC_API_URL.replace(/^http/, 'ws')
          : `${proto}//127.0.0.1:8000`;
        const url = `${host.replace(/\/+$/, '')}/api/v1/webrtc/signal/${encodeURIComponent(this.roomId)}`;
        this.ws = new WebSocket(url);
        this.ws.onopen = () => {
          // Announce only after the transport can actually deliver messages.
          this.sendSignaling({ type: 'join' });
          if (this.role === 'caller' && this.pc?.localDescription) {
            this.sendSignaling({ type: 'offer', sdp: this.pc.localDescription });
          }
        };
        this.ws.onerror = () => this.callbacks.onError?.('Signaling WebSocket unavailable; same-browser tab signaling may still work.');
        this.ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            this.enqueueSignal(data);
          } catch {
            // Non-JSON message
          }
        };
      } catch {
        // WebSocket initialization failed
      }
    }
  }

  private sendSignaling(msg: SignalingMessage): void {
    const id = `${msg.type}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    const payload = { ...msg, fromRole: this.role || undefined, msgId: id };
    this.seenMsgIds.add(id);

    if (this.bc) {
      try {
        this.bc.postMessage(payload);
      } catch {
        // Channel closed
      }
    }

    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      try {
        this.ws.send(JSON.stringify(payload));
      } catch {
        // Send failed
      }
    }
  }

  private enqueueSignal(msg: SignalingMessage): void {
    this.signalingChain = this.signalingChain.then(() => this.handleSignalingPayload(msg));
  }

  private async handleSignalingPayload(msg: SignalingMessage): Promise<void> {
    if (!msg || !msg.type) return;
    if (msg.msgId && this.seenMsgIds.has(msg.msgId)) return;
    if (msg.msgId) this.seenMsgIds.add(msg.msgId);
    if (msg.fromRole === this.role) return; // Ignore own echoes

    try {
      if (msg.type === 'leave') { this.endCall(false); return; }
      if (this.role === 'caller') {
        if (msg.type === 'join') {
          // Protected User joined room; send existing offer if ready
          if (this.pc && this.pc.localDescription) {
            this.sendSignaling({
              type: 'offer',
              sdp: this.pc.localDescription,
            });
          }
        } else if (msg.type === 'answer' && msg.sdp && this.pc) {
          if (this.pc.signalingState !== 'stable') {
            await this.pc.setRemoteDescription(new RTCSessionDescription(msg.sdp));
            // Flush pending ICE candidates
            while (this.pendingCandidates.length > 0) {
              const cand = this.pendingCandidates.shift();
              if (cand) await this.pc.addIceCandidate(new RTCIceCandidate(cand));
            }
          }
        } else if (msg.type === 'ice-candidate' && msg.candidate && this.pc) {
          if (this.pc.remoteDescription) {
            await this.pc.addIceCandidate(new RTCIceCandidate(msg.candidate));
          } else {
            this.pendingCandidates.push(msg.candidate);
          }
        }
      } else if (this.role === 'protected_user') {
        if (msg.type === 'join') {
          this.sendSignaling({ type: 'join' });
        } else if (msg.type === 'offer' && msg.sdp && this.pc && !this.pc.remoteDescription) {
          await this.pc.setRemoteDescription(new RTCSessionDescription(msg.sdp));
          const answer = await this.pc.createAnswer();
          await this.pc.setLocalDescription(answer);
          this.sendSignaling({
            type: 'answer',
            sdp: answer,
          });

          // Flush pending candidates
          while (this.pendingCandidates.length > 0) {
            const cand = this.pendingCandidates.shift();
            if (cand) await this.pc.addIceCandidate(new RTCIceCandidate(cand));
          }
        } else if (msg.type === 'ice-candidate' && msg.candidate && this.pc) {
          if (this.pc.remoteDescription) {
            await this.pc.addIceCandidate(new RTCIceCandidate(msg.candidate));
          } else {
            this.pendingCandidates.push(msg.candidate);
          }
        }
      }
    } catch (err) {
      this.callbacks.onError?.(err instanceof Error ? err.message : String(err));
    }
  }

  /**
   * Start call as Tab A: CALLER.
   * Captures microphone, creates RTCPeerConnection, and transmits audio track.
   */
  public async startCaller(
    roomId: string,
    callbacks: WebRTCCallCallbacks
  ): Promise<MediaStream> {
    this.role = 'caller';
    this.callbacks = callbacks;
    callbacks.onConnectionStatusChange?.('CONNECTING');

    // 1. Capture local microphone
    try {
      this.localStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
      callbacks.onMicStatusChange?.('ACTIVE');
    } catch (err) {
      callbacks.onMicStatusChange?.('ERROR');
      callbacks.onConnectionStatusChange?.('ENDED');
      throw err;
    }


    // 2. Initialize PeerConnection
    const rtcConfig: RTCConfiguration = {
      iceServers: [{ urls: 'stun:stun.l.google.com:19302' }],
    };
    this.pc = new RTCPeerConnection(rtcConfig);

    this.pc.onconnectionstatechange = () => {
      if (!this.pc) return;
      const state = this.pc.connectionState;
      this.reportDiagnostics();
      this.callbacks.onConnectionStateChange?.(state);
      if (state === 'connected') {
        this.callbacks.onConnectionStatusChange?.('CONNECTED');
      } else if (state === 'connecting') {
        this.callbacks.onConnectionStatusChange?.('CONNECTING');
      } else if (state === 'failed' || state === 'closed' || state === 'disconnected') {
        this.callbacks.onConnectionStatusChange?.('ENDED');
      }
    };

    this.pc.onicecandidate = (event) => {
      if (event.candidate) {
        this.sendSignaling({
          type: 'ice-candidate',
          candidate: event.candidate.toJSON(),
        });
      }
    };

    this.pc.ontrack = (event) => {
      this.remoteStream = event.streams[0] || new MediaStream([event.track]);
      this.callbacks.onRemoteAudioStatusChange?.('ACTIVE');
      this.callbacks.onRemoteStream?.(this.remoteStream);
    };
    this.pc.oniceconnectionstatechange = () => this.reportDiagnostics();

    // 3. Attach local audio tracks
    this.localStream.getAudioTracks().forEach((track) => {
      if (this.pc && this.localStream) {
        this.pc.addTrack(track, this.localStream);
      }
    });

    this.initSignaling(roomId);
    // 4. Create and send SDP Offer
    const offer = await this.pc.createOffer({
      offerToReceiveAudio: true,
      offerToReceiveVideo: false,
    });
    await this.pc.setLocalDescription(offer);
    this.sendSignaling({
      type: 'offer',
      sdp: offer,
    });

    return this.localStream;
  }

  /**
   * Start call as Tab B: PROTECTED USER.
   * Joins room, receives caller MediaStream via ontrack, and yields it for audible playback & detection.
   */
  public async startProtectedUser(
    roomId: string,
    callbacks: WebRTCCallCallbacks
  ): Promise<void> {
    this.role = 'protected_user';
    this.callbacks = callbacks;
    callbacks.onConnectionStatusChange?.('CONNECTING');
    callbacks.onRemoteAudioStatusChange?.('WAITING');


    const rtcConfig: RTCConfiguration = {
      iceServers: [{ urls: 'stun:stun.l.google.com:19302' }],
    };
    this.pc = new RTCPeerConnection(rtcConfig);

    this.pc.onconnectionstatechange = () => {
      if (!this.pc) return;
      const state = this.pc.connectionState;
      this.reportDiagnostics();
      this.callbacks.onConnectionStateChange?.(state);
      if (state === 'connected') {
        this.callbacks.onConnectionStatusChange?.('CONNECTED');
      } else if (state === 'connecting') {
        this.callbacks.onConnectionStatusChange?.('CONNECTING');
      } else if (state === 'failed' || state === 'closed' || state === 'disconnected') {
        this.callbacks.onConnectionStatusChange?.('ENDED');
      }
    };

    this.pc.onicecandidate = (event) => {
      if (event.candidate) {
        this.sendSignaling({
          type: 'ice-candidate',
          candidate: event.candidate.toJSON(),
        });
      }
    };

    this.pc.oniceconnectionstatechange = () => this.reportDiagnostics();
    try {
      this.localStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      this.localStream.getAudioTracks().forEach(track => this.pc?.addTrack(track, this.localStream!));
      callbacks.onMicStatusChange?.('ACTIVE');
    } catch (error) {
      this.endCall();
      callbacks.onConnectionStatusChange?.('ERROR');
      callbacks.onMicStatusChange?.('ERROR');
      throw error;
    }

    // Delivery of Caller's MediaStream via ontrack
    this.pc.ontrack = (event) => {
      const stream = event.streams[0] || new MediaStream([event.track]);
      this.remoteStream = stream;
      this.callbacks.onRemoteAudioStatusChange?.('ACTIVE');
      this.callbacks.onRemoteStream?.(stream);
    };

    this.initSignaling(roomId);
    // Send join announcement to prompt Caller for SDP offer
    this.sendSignaling({
      type: 'join',
    });
  }

  /**
   * Legacy loopback call simulation (kept for backwards compatibility with test harnesses).
   */
  public async startLoopbackCall(
    localStream: MediaStream,
    callbacks: WebRTCCallCallbacks
  ): Promise<MediaStream> {
    this.localStream = localStream;
    this.callbacks = callbacks;

    const rtcConfig: RTCConfiguration = {
      iceServers: [{ urls: 'stun:stun.l.google.com:19302' }],
    };

    this.localPc = new RTCPeerConnection(rtcConfig);
    this.remotePc = new RTCPeerConnection(rtcConfig);

    this.localPc.onconnectionstatechange = () => {
      if (this.localPc) {
        this.callbacks.onConnectionStateChange?.(this.localPc.connectionState);
      }
    };

    this.localPc.onicecandidate = (event) => {
      if (event.candidate && this.remotePc) {
        this.remotePc.addIceCandidate(event.candidate).catch(() => {});
      }
    };

    this.remotePc.onicecandidate = (event) => {
      if (event.candidate && this.localPc) {
        this.localPc.addIceCandidate(event.candidate).catch(() => {});
      }
    };

    const remoteStreamPromise = new Promise<MediaStream>((resolve) => {
      if (!this.remotePc) return;
      this.remotePc.ontrack = (event) => {
        const stream = event.streams[0] || new MediaStream([event.track]);
        this.remoteStream = stream;
        this.callbacks.onRemoteStream?.(stream);
        resolve(stream);
      };
    });

    localStream.getAudioTracks().forEach((track) => {
      if (this.localPc) {
        this.localPc.addTrack(track, localStream);
      }
    });

    const offer = await this.localPc.createOffer({
      offerToReceiveAudio: true,
      offerToReceiveVideo: false,
    });
    await this.localPc.setLocalDescription(offer);
    await this.remotePc.setRemoteDescription(offer);

    const answer = await this.remotePc.createAnswer();
    await this.remotePc.setLocalDescription(answer);
    await this.localPc.setRemoteDescription(answer);

    return remoteStreamPromise;
  }

  private reportDiagnostics(): void {
    const pc = this.pc;
    if (pc) this.callbacks.onDiagnostics?.(`Connection: ${pc.connectionState}; ICE: ${pc.iceConnectionState}; signaling: ${pc.signalingState}; remote track: ${this.remoteStream?.getAudioTracks()[0]?.readyState || 'waiting'}; track muted: ${this.remoteStream?.getAudioTracks()[0]?.muted ?? 'unknown'}`);
  }

  public endCall(notifyPeer = true): void {
    if (this.pc) {
      if (notifyPeer) this.sendSignaling({ type: 'leave' });
      this.pc.close();
      this.pc = null;
    }
    if (this.localPc) {
      this.localPc.close();
      this.localPc = null;
    }
    if (this.remotePc) {
      this.remotePc.close();
      this.remotePc = null;
    }
    if (this.localStream) {
      this.localStream.getTracks().forEach((t) => t.stop());
      this.localStream = null;
    }
    if (this.ws) {
      try {
        this.ws.close();
      } catch {
        // Ignore
      }
      this.ws = null;
    }
    if (this.bc) {
      try {
        this.bc.close();
      } catch {
        // Ignore
      }
      this.bc = null;
    }
    this.remoteStream?.getTracks().forEach(track => track.stop());
    this.remoteStream = null;
    this.pendingCandidates = [];
    this.seenMsgIds.clear();
    this.callbacks.onMicStatusChange?.('MUTED');
    this.callbacks.onRemoteAudioStatusChange?.('WAITING');
    this.callbacks.onDiagnostics?.('Connection: closed; remote track: ended');
    this.callbacks.onConnectionStatusChange?.('ENDED');
  }
}
