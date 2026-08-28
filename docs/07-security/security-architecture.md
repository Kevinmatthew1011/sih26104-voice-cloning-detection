# Security Architecture & Defense-in-Depth: SIH26104

## 1. Security Philosophy

The **VOICE-GUARD Security Subsystem** applies defense-in-depth principles across the entire audio ingestion, decoding, inference, and persistence lifecycle. The system is hardened against malicious audio uploads, Denial of Service (DoS) attacks, model inversion, memory exhaustion, and audit tampering.

```mermaid
graph TD
    subgraph Layer1["1. Network & Gateway Security"]
        RateLimit["IP Rate Limiting (10 req/min)"]
        CORS["Strict CORS & Security Headers"]
    end
    
    subgraph Layer2["2. Ingestion & Stream Hardening"]
        StreamSize["Chunked Streaming Size Cap (Max 25 MB)"]
        MagicBytes["Magic Byte Header Verification"]
        Sanitize["Filename Cleansing & Traversal Stripping"]
        SHA256["SHA-256 Cryptographic Fingerprint"]
    end
    
    subgraph Layer3["3. Safe Media Processing"]
        PyAVSandbox["In-Memory PyAV (FFmpeg) Decoding"]
        NoSubprocess["Zero Subprocess Shell Invocation"]
        TempCleanup["Deterministic Finally Temp File Cleanup"]
    end
    
    subgraph Layer4["4. Policy & Domain Protection"]
        DecisionEngine["3-Tier Deterministic Action Policy"]
        MicQuarantine["Capture-Domain Quarantine (browser_mic -> VERIFY)"]
    end
    
    subgraph Layer5["5. Forensic Audit Trail"]
        ImmutableLog["Immutable Database Case Record"]
        JSONReport["Cryptographic Audit Evidence Receipt"]
    end
    
    Layer1 --> Layer2 --> Layer3 --> Layer4 --> Layer5
```

---

## 2. Security Controls Matrix

| Security Layer | Implemented Control | Threat Mitigated |
| :--- | :--- | :--- |
| **Network** | Process-Local Token Bucket Rate Limiting (10 req/min, burst 3) | API brute-forcing, automated DoS, model inversion attacks. |
| **Network** | Restricted CORS & Security Headers | Cross-site request forgery, iframe clickjacking. |
| **Ingestion** | Streaming 25 MB chunked size enforcement | Memory exhaustion, zip bombs, oversized file buffer overflows. |
| **Ingestion** | Magic Byte Header Matching (`RIFF`, `OggS`, `EBML`, `fLaC`, `ID3`)| Executable spoofing, polyglot files, non-audio uploads. |
| **Ingestion** | Path sanitization (`os.path.basename`, traversal stripping) | Path traversal attacks (`../../etc/passwd`). |
| **Ingestion** | SHA-256 integrity hash generation | File tampering, chain-of-custody disputes. |
| **Processing**| In-memory PyAV stream decoding without shell subprocesses | Shell injection vulnerabilities, command injection. |
| **Processing**| Deterministic `finally` cleanup of disk artifacts | Disk exhaustion via temporary upload accumulation. |
| **Inference** | Async thread offloading (`asyncio.to_thread`) | Event loop starvation, API thread blocking. |
| **Policy** | Capture-domain reliability override (`unvalidated` $\to$ `VERIFY`) | False positive account lockouts from microphone domain shift. |
| **Audit** | Immutable append-only audit records and JSON report receipts | Non-repudiation, compliance audit falsification. |
