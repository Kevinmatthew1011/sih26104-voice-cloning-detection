import sys
import json
import time
import hashlib
from pathlib import Path
import soundfile as sf
import numpy as np

def compute_sha256(filepath: Path) -> str:
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest()

def pad_audio(x: np.ndarray, max_len: int = 64600) -> np.ndarray:
    x_len = x.shape[0]
    if x_len >= max_len:
        return x[:max_len]
    num_repeats = int(max_len / x_len) + 1
    padded_x = np.tile(x, num_repeats)[:max_len]
    return padded_x

def main():
    root = Path(__file__).resolve().parent.parent.parent
    aasist_dir = root / "ml_eval" / "aasist"
    sys.path.insert(0, str(aasist_dir))

    import torch
    import torchaudio
    from models.AASIST import Model

    print("=================================================================")
    print("           AASIST PHASE 2: ENVIRONMENT & SMOKE TEST              ")
    print("=================================================================\n")

    # 1. Environment Introspection
    cuda_avail = torch.cuda.is_available()
    device_name = torch.cuda.get_device_name(0) if cuda_avail else "N/A (CPU)"
    cuda_ver = torch.version.cuda if cuda_avail else "N/A"
    device = torch.device("cuda:0" if cuda_avail else "cpu")

    print(f"1. ENVIRONMENT DETAILS:")
    print(f"   - Python Version:       {sys.version.split()[0]}")
    print(f"   - PyTorch Version:      {torch.__version__}")
    print(f"   - TorchAudio Version:   {torchaudio.__version__}")
    print(f"   - CUDA Available:       {cuda_avail}")
    print(f"   - GPU Device:           {device_name}")
    print(f"   - Torch CUDA Version:   {cuda_ver}")
    print(f"   - Active Device:        {device}")

    # 2. Checkpoint & Model Loading
    config_file = aasist_dir / "config" / "AASIST.conf"
    weights_file = aasist_dir / "weights" / "AASIST.pth"

    assert config_file.exists(), f"Missing config: {config_file}"
    assert weights_file.exists(), f"Missing weights: {weights_file}"

    weights_sha256 = compute_sha256(weights_file)
    print(f"\n2. CHECKPOINT & CONFIG INTEGRITY:")
    print(f"   - Config File:          {config_file}")
    print(f"   - Weights File:         {weights_file}")
    print(f"   - Checkpoint SHA-256:   {weights_sha256}")
    assert weights_sha256 == "51d2d9cf0738172f61e2a384ec50a54a55363240f67c971ed55a92435bc1a1c0", "SHA-256 mismatch with official release!"

    with open(config_file, "r") as f:
        config = json.load(f)

    model = Model(config["model_config"])
    state_dict = torch.load(weights_file, map_location=device, weights_only=True)
    model.load_state_dict(state_dict)
    model.to(device)
    model.eval()
    print("   [OK] AASIST architecture instantiated and weights loaded successfully.")

    # 3. Smoke Test C: Known Bonafide Sample
    print("\n3. SMOKE TEST C: KNOWN BONAFIDE SAMPLE (LA_T_1138215.flac)")
    bona_path = root / "datasets" / "ASVspoof2019_LA" / "LA" / "ASVspoof2019_LA_train" / "flac" / "LA_T_1138215.flac"
    assert bona_path.exists(), f"Sample missing: {bona_path}"

    wav_bona, sr_bona = sf.read(str(bona_path))
    assert sr_bona == 16000, f"Unexpected sample rate: {sr_bona}"
    wav_bona_pad = pad_audio(wav_bona, 64600)
    tensor_bona = torch.FloatTensor(wav_bona_pad).unsqueeze(0).to(device)

    if cuda_avail:
        torch.cuda.reset_peak_memory_stats()
        torch.cuda.synchronize()

    with torch.no_grad():
        _, out_bona = model(tensor_bona)

    if cuda_avail:
        torch.cuda.synchronize()

    # Note: in AASIST, out[:, 0] is spoof logit, out[:, 1] is bonafide logit
    out_bona_np = out_bona.cpu().numpy()[0]
    logit_spoof_b, logit_bona_b = out_bona_np[0], out_bona_np[1]
    bona_pred = "bonafide" if logit_bona_b > logit_spoof_b else "spoof"
    
    print(f"   - Raw Output Logits:    Spoof={logit_spoof_b:.4f}, Bonafide={logit_bona_b:.4f}")
    print(f"   - Difference (Bona-Sp): {logit_bona_b - logit_spoof_b:+.4f}")
    print(f"   - Classification:       {bona_pred} (Expected: bonafide)")
    assert np.isfinite(out_bona_np).all(), "Non-finite output detected"
    assert bona_pred == "bonafide", "Failed on known bonafide sample"

    # 4. Smoke Test D: Known Spoof Sample
    print("\n4. SMOKE TEST D: KNOWN SPOOF SAMPLE (LA_T_1004644.flac)")
    spoof_path = root / "datasets" / "ASVspoof2019_LA" / "LA" / "ASVspoof2019_LA_train" / "flac" / "LA_T_1004644.flac"
    assert spoof_path.exists(), f"Sample missing: {spoof_path}"

    wav_spoof, sr_spoof = sf.read(str(spoof_path))
    assert sr_spoof == 16000, f"Unexpected sample rate: {sr_spoof}"
    wav_spoof_pad = pad_audio(wav_spoof, 64600)
    tensor_spoof = torch.FloatTensor(wav_spoof_pad).unsqueeze(0).to(device)

    with torch.no_grad():
        _, out_spoof = model(tensor_spoof)

    out_spoof_np = out_spoof.cpu().numpy()[0]
    logit_spoof_s, logit_bona_s = out_spoof_np[0], out_spoof_np[1]
    spoof_pred = "spoof" if logit_spoof_s > logit_bona_s else "bonafide"

    print(f"   - Raw Output Logits:    Spoof={logit_spoof_s:.4f}, Bonafide={logit_bona_s:.4f}")
    print(f"   - Difference (Bona-Sp): {logit_bona_s - logit_spoof_s:+.4f}")
    print(f"   - Classification:       {spoof_pred} (Expected: spoof)")
    assert np.isfinite(out_spoof_np).all(), "Non-finite output detected"
    assert spoof_pred == "spoof", "Failed on known spoof sample"

    # 5. Smoke Test E: 100-Sample Deterministic EVAL Batch (50 Bonafide + 50 Spoof)
    print("\n5. SMOKE TEST E: 100-SAMPLE DETERMINISTIC EVAL BATCH (50 Bonafide + 50 Spoof)")
    eval_proto = root / "datasets" / "ASVspoof2019_LA" / "LA" / "ASVspoof2019_LA_cm_protocols" / "ASVspoof2019.LA.cm.eval.trl.txt"
    eval_audio_dir = root / "datasets" / "ASVspoof2019_LA" / "LA" / "ASVspoof2019_LA_eval" / "flac"

    eval_bona_keys = []
    eval_spoof_keys = []

    with open(eval_proto, "r") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) == 5:
                spk, audio_id, env, att, label = parts
                if label == "bonafide" and len(eval_bona_keys) < 50:
                    eval_bona_keys.append((audio_id, 0)) # 0: bonafide
                elif label == "spoof" and len(eval_spoof_keys) < 50:
                    eval_spoof_keys.append((audio_id, 1)) # 1: spoof
                if len(eval_bona_keys) == 50 and len(eval_spoof_keys) == 50:
                    break

    test_samples = eval_bona_keys + eval_spoof_keys
    print(f"   Selected {len(test_samples)} samples (50 Bonafide + 50 Spoof).")

    # Load audio waveforms
    t0_audio_load = time.perf_counter()
    waveforms = []
    labels = []
    for audio_id, lab in test_samples:
        fpath = eval_audio_dir / f"{audio_id}.flac"
        wav, _ = sf.read(str(fpath))
        waveforms.append(pad_audio(wav, 64600))
        labels.append(lab)
    t_audio_load = time.perf_counter() - t0_audio_load

    batch_x = torch.FloatTensor(np.array(waveforms, dtype=np.float32))
    labels_np = np.array(labels, dtype=np.int32)

    # Batch inference
    batch_size = 25
    num_batches = int(np.ceil(len(test_samples) / batch_size))
    
    all_logits = []
    if cuda_avail:
        torch.cuda.reset_peak_memory_stats()
        torch.cuda.synchronize()

    t0_infer = time.perf_counter()
    with torch.no_grad():
        for i in range(num_batches):
            bx = batch_x[i*batch_size : (i+1)*batch_size].to(device)
            _, bout = model(bx)
            all_logits.append(bout.cpu().numpy())

    if cuda_avail:
        torch.cuda.synchronize()
    t_infer = time.perf_counter() - t0_infer

    logits_all = np.concatenate(all_logits, axis=0) # shape (100, 2)
    assert logits_all.shape == (100, 2), f"Bad logits shape: {logits_all.shape}"
    assert np.isfinite(logits_all).all(), "Non-finite logits found in batch"

    # Prediction: 1 (synthetic/spoof) if logit_spoof (col 0) > logit_bona (col 1) else 0 (bonafide)
    preds = (logits_all[:, 0] > logits_all[:, 1]).astype(np.int32)
    correct = np.sum(preds == labels_np)
    accuracy = correct / len(labels_np)

    # Confusion matrix
    tn = int(np.sum((labels_np == 0) & (preds == 0)))
    fp = int(np.sum((labels_np == 0) & (preds == 1)))
    fn = int(np.sum((labels_np == 1) & (preds == 0)))
    tp = int(np.sum((labels_np == 1) & (preds == 1)))

    peak_vram_mb = torch.cuda.max_memory_allocated() / (1024 * 1024) if cuda_avail else 0.0

    print(f"   - Audio Loading Time:   {t_audio_load:.4f}s")
    print(f"   - Model Forward Time:   {t_infer:.4f}s ({t_infer/len(test_samples)*1000:.2f} ms/sample)")
    print(f"   - Throughput:           {len(test_samples)/t_infer:.1f} samples/sec")
    print(f"   - Peak GPU VRAM Usage:  {peak_vram_mb:.2f} MB")
    print(f"   - Batch Accuracy:       {accuracy*100:.2f}% ({correct}/{len(labels_np)})")
    print(f"   - Confusion Matrix:     TN={tn}, FP={fp}, FN={fn}, TP={tp}")
    print(f"   - Bonafide Accuracy:    {tn}/50 ({tn/50*100:.1f}%)")
    print(f"   - Spoof Accuracy:       {tp}/50 ({tp/50*100:.1f}%)")

    print("\n=================================================================")
    print("              ALL SMOKE TESTS PASSED CLEANLY!                    ")
    print("=================================================================")

if __name__ == "__main__":
    main()
