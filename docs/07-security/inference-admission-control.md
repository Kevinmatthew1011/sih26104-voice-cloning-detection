# Inference Admission Control & Resource Protection: SIH26104

## 1. The Resource Starvation Vulnerability

Deep neural network forward passes (such as AASIST graph convolutions) are CPU/GPU-intensive. If multiple long audio streams are submitted concurrently without admission control, the server CPU/GPU can experience thread exhaustion, leading to high API latency and dropped connections.

---

## 2. Implemented Admission & Concurrency Controls

```mermaid
flowchart LR
    Incoming[Incoming Audio Stream] --> StreamLimit["1. 25 MB Stream Size Cap"]
    StreamLimit --> FormatCheck["2. Fast Header & MIME Probe"]
    FormatCheck --> AsyncThread["3. ThreadPool Offloading (asyncio.to_thread)"]
    AsyncThread --> Inference["4. AASIST PyTorch Inference"]
    Inference --> Cleanup["5. Deterministic Memory & Disk Cleanup"]
```

1. **Async Thread Offloading**: Neural forward computations execute inside `asyncio.to_thread()`, keeping FastAPI's main asyncio event loop completely free to handle concurrent health probes and API routing.
2. **Audio Length Gating**: Stream processing is bounded to a maximum file size of 25 MB, bounding the maximum number of temporal sliding windows per request to $< 50$ windows.
3. **Deterministic Memory Cleanup**: Decoded NumPy float arrays and PyTorch tensors are freed immediately after top-$k$ score aggregation.
