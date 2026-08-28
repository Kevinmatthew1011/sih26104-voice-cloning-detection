# Production Readiness & Scaling Considerations: SIH26104

## 1. Production Architecture Topology

```mermaid
graph TD
    User([External Traffic / Internet]) --> CDN[Cloudflare / CDN]
    CDN --> LB[NGINX / Reverse Proxy Load Balancer]
    
    subgraph FrontendCluster["Frontend Tier"]
        FE1[Next.js Node Instance 1]
        FE2[Next.js Node Instance 2]
    end
    
    subgraph BackendCluster["Backend API Tier"]
        BE1[FastAPI Gunicorn Worker 1 (GPU/CPU)]
        BE2[FastAPI Gunicorn Worker 2 (GPU/CPU)]
    end
    
    subgraph StorageCluster["Persistence & Cache"]
        Redis[(Redis Distributed Token Bucket Limiter)]
        PostgreSQL[(PostgreSQL High-Availability Primary + Read Replicas)]
        S3[(Encrypted S3 Object Storage for Long-Term Audio Archive)]
    end
    
    LB --> FE1 & FE2
    LB --> BE1 & BE2
    BE1 & BE2 --> Redis
    BE1 & BE2 --> PostgreSQL
    BE1 & BE2 --> S3
```

---

## 2. Key Production Hardening Guidelines

### 2.1 Multi-Process Gunicorn Deployment
Deploy FastAPI using Gunicorn with Uvicorn worker classes:
```bash
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### 2.2 GPU Tensor Acceleration
Set `AASIST_DEVICE=cuda` in `.env` to enable CUDA tensor acceleration, reducing multi-window inference latency from $\approx 350\text{ ms}$ to $< 50\text{ ms}$ per 10-second audio stream.

### 2.3 Distributed Rate Limiting
Replace the in-memory rate limiter with a Redis-backed token bucket algorithm to share rate limit state across multiple load-balanced FastAPI worker nodes.

### 2.4 Audio Retention & Privacy Compliance (GDPR / DPDP)
Configure automated lifecycle policies to permanently delete temporary audio uploads from `UPLOAD_DIR` after processing, retaining only the SHA-256 integrity hash and forensic telemetry in the database to satisfy data protection regulations.
