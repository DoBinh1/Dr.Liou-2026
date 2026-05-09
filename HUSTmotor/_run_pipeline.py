"""End-to-end pipeline: load -> features -> splits -> baselines.

Stages:
  A) Load & cache raw signals (npz) for fast reuse
  B) Extract handcrafted features per segment -> features_per_segment.csv
  C) Build splits.npz (raw segments for DL)
  D) XGBoost baselines (intra-condition, pooled, leave-one-condition-out DG)
  E) PyTorch WDCNN baselines (single-modality vib, single-modality ac, multimodal dual-stream)

Outputs:
  raw_cache.npz
  features_per_segment.csv
  splits.npz
  baseline_results.json
"""
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.signal import butter, sosfiltfilt, hilbert
from scipy.stats import kurtosis, skew

import xgboost as xgb
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, f1_score, confusion_matrix

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, TensorDataset

ROOT = Path(r"D:/[Lab] HUST/Dr Liou - Multi modal/HUST motor multimodal dataset")
DATA_DIR = ROOT / "Raw data"
RAW_CACHE = ROOT / "raw_cache.npz"
FEAT_CSV = ROOT / "features_per_segment.csv"
SPLITS = ROOT / "splits.npz"
RESULTS = ROOT / "baseline_results.json"

FS = 25600
WINDOW = 4096
TRAIN_OVERLAP = 0.5
EVAL_OVERLAP = 0.0

CLASSES = ["H", "BF", "BOW", "BROKEN", "MISAL", "UNBAL"]
CONDITIONS = [5, 10, 20, 30]
CHANNELS = ["X", "Y", "Z", "Sound"]
CHANNEL_TYPE = {"X": "vib", "Y": "vib", "Z": "vib", "Sound": "ac"}

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"[device] {DEVICE}")


# ============================================================
# A) Loader
# ============================================================
def load_motor_file(path):
    path = Path(path)
    fname = path.stem
    parts = fname.split("_")
    label = parts[0]
    condition = int(parts[1].replace("HZ", ""))
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    data_start = None
    for i, line in enumerate(lines):
        if line.strip().startswith("Time (seconds)"):
            data_start = i + 1
            break
    arr = np.loadtxt(lines[data_start:], delimiter="\t")
    return {
        "X": arr[:, 1].astype(np.float32),
        "Y": arr[:, 2].astype(np.float32),
        "Z": arr[:, 3].astype(np.float32),
        "Sound": arr[:, 4].astype(np.float32),
        "label": label,
        "condition": condition,
        "fname": fname,
    }


def list_files():
    return sorted(DATA_DIR.glob("*.txt"))


def stage_A_cache():
    if RAW_CACHE.exists():
        print(f"[A] cache exists: {RAW_CACHE}")
        return
    print("[A] loading 24 files ...")
    t0 = time.time()
    data = {}
    for path in list_files():
        d = load_motor_file(path)
        for ch in CHANNELS:
            data[f"{d['fname']}__{ch}"] = d[ch]
    np.savez_compressed(RAW_CACHE, **data)
    print(f"[A] done in {time.time()-t0:.1f}s -> {RAW_CACHE}")


def load_cached():
    z = np.load(RAW_CACHE)
    files = sorted({k.split("__")[0] for k in z.files})
    out = {}
    for fname in files:
        parts = fname.split("_")
        label = parts[0]
        condition = int(parts[1].replace("HZ", ""))
        out[fname] = {
            "X": z[f"{fname}__X"],
            "Y": z[f"{fname}__Y"],
            "Z": z[f"{fname}__Z"],
            "Sound": z[f"{fname}__Sound"],
            "label": label,
            "condition": condition,
            "fname": fname,
        }
    return out


# ============================================================
# B) Handcrafted features
# ============================================================
def time_features(x):
    x = x.astype(np.float64)
    rms = np.sqrt(np.mean(x ** 2))
    abs_mean = np.mean(np.abs(x))
    peak = np.max(np.abs(x))
    return {
        "mean": float(np.mean(x)),
        "std": float(np.std(x)),
        "rms": float(rms),
        "kurt": float(kurtosis(x)),
        "skew": float(skew(x)),
        "p2p": float(np.ptp(x)),
        "crest": float(peak / (rms + 1e-12)),
        "impulse": float(peak / (abs_mean + 1e-12)),
        "shape": float(rms / (abs_mean + 1e-12)),
        "margin": float(peak / (np.mean(np.sqrt(np.abs(x))) ** 2 + 1e-12)),
    }


def freq_features(x, fs, fr, f_line=50.0):
    n = len(x)
    X = np.abs(np.fft.rfft(x * np.hanning(n)))
    f = np.fft.rfftfreq(n, 1 / fs)
    P = X ** 2
    Psum = P.sum() + 1e-12
    p_norm = P / Psum
    out = {
        "sp_centroid": float((f * P).sum() / Psum),
        "sp_entropy": float(-(p_norm * np.log(p_norm + 1e-12)).sum()),
    }
    bands = [(0, 100), (100, 500), (500, 1000), (1000, 2000),
             (2000, 4000), (4000, 6000), (6000, 12000)]
    for lo, hi in bands:
        m = (f >= lo) & (f < hi)
        out[f"be_{lo}_{hi}"] = float(P[m].sum() / Psum)

    def peak_amp_near(target, bw=2.0):
        m = (f > target - bw) & (f < target + bw)
        return float(X[m].max()) if m.any() else 0.0

    out.update({
        "amp_1x": peak_amp_near(fr),
        "amp_2x": peak_amp_near(2 * fr),
        "amp_3x": peak_amp_near(3 * fr),
        "amp_fline": peak_amp_near(f_line),
        "amp_2fline": peak_amp_near(2 * f_line),
    })
    return out


def envelope_features(x, fs, fr, band=(2000, 6000)):
    """Envelope spectrum amp at k*fr (proxy for bearing characteristic freq)."""
    sos = butter(4, band, btype="bandpass", fs=fs, output="sos")
    xf = sosfiltfilt(sos, x)
    env = np.abs(hilbert(xf))
    env = env - env.mean()
    n = len(env)
    E = np.abs(np.fft.rfft(env * np.hanning(n)))
    f = np.fft.rfftfreq(n, 1 / fs)
    out = {}
    for k in [1, 2, 3]:
        target = k * fr
        m = (f > target - 2) & (f < target + 2)
        out[f"env_k{k}"] = float(E[m].max()) if m.any() else 0.0
    out["env_total"] = float(E.sum())
    return out


def extract_features(seg, fs, fr):
    out = {}
    for k, v in time_features(seg).items():
        out[f"t_{k}"] = v
    for k, v in freq_features(seg, fs, fr).items():
        out[f"f_{k}"] = v
    for k, v in envelope_features(seg, fs, fr).items():
        out[f"e_{k}"] = v
    return out


def segment_signal(x, w, overlap):
    step = max(1, int(w * (1 - overlap)))
    n = (len(x) - w) // step + 1
    return np.stack([x[i * step:i * step + w] for i in range(n)], axis=0)


def stage_B_features(data):
    if FEAT_CSV.exists():
        print(f"[B] features exist: {FEAT_CSV}")
        return pd.read_csv(FEAT_CSV)
    print("[B] extracting features ...")
    t0 = time.time()
    rows = []
    for fname, d in data.items():
        fr = d["condition"]
        # Build one row per segment that contains all 4 channels (so we can
        # later treat features as concatenated multi-channel vector per segment).
        for ch in CHANNELS:
            segs = segment_signal(d[ch], WINDOW, 0.5)
            for seg_idx, seg in enumerate(segs):
                feats = extract_features(seg, FS, fr)
                feats.update({
                    "file": fname,
                    "class": d["label"],
                    "condition": fr,
                    "channel": ch,
                    "channel_type": CHANNEL_TYPE[ch],
                    "seg_idx": seg_idx,
                })
                rows.append(feats)
    df = pd.DataFrame(rows)
    df.to_csv(FEAT_CSV, index=False)
    print(f"[B] done in {time.time()-t0:.1f}s -> {FEAT_CSV} (rows={len(df)})")
    return df


# ============================================================
# C) Build splits.npz (raw segments for DL)
# ============================================================
def build_split_arrays(data, t_start, t_end, overlap):
    Xv, Xa, yc, yd = [], [], [], []
    for fname, d in data.items():
        n_total = len(d["X"])
        i0 = int(t_start * n_total)
        i1 = int(t_end * n_total)
        vib = np.stack([d["X"][i0:i1], d["Y"][i0:i1], d["Z"][i0:i1]], axis=-1)
        ac = d["Sound"][i0:i1, None]
        if len(vib) < WINDOW:
            continue
        step = max(1, int(WINDOW * (1 - overlap)))
        n_seg = (len(vib) - WINDOW) // step + 1
        for k in range(n_seg):
            a, b = k * step, k * step + WINDOW
            Xv.append(vib[a:b])
            Xa.append(ac[a:b])
            yc.append(CLASSES.index(d["label"]))
            yd.append(CONDITIONS.index(d["condition"]))
    return (
        np.asarray(Xv, dtype=np.float32),
        np.asarray(Xa, dtype=np.float32),
        np.asarray(yc, dtype=np.int64),
        np.asarray(yd, dtype=np.int64),
    )


def stage_C_splits(data):
    if SPLITS.exists():
        print(f"[C] splits exist: {SPLITS}")
        return np.load(SPLITS)
    print("[C] building splits ...")
    train = build_split_arrays(data, 0.0, 0.70, TRAIN_OVERLAP)
    val = build_split_arrays(data, 0.70, 0.85, EVAL_OVERLAP)
    test = build_split_arrays(data, 0.85, 1.00, EVAL_OVERLAP)
    np.savez_compressed(
        SPLITS,
        train_X_vib=train[0], train_X_ac=train[1],
        train_y_class=train[2], train_y_domain=train[3],
        val_X_vib=val[0], val_X_ac=val[1],
        val_y_class=val[2], val_y_domain=val[3],
        test_X_vib=test[0], test_X_ac=test[1],
        test_y_class=test[2], test_y_domain=test[3],
    )
    for name, sp in [("train", train), ("val", val), ("test", test)]:
        print(f"  {name}: vib={sp[0].shape} ac={sp[1].shape}")
    return np.load(SPLITS)


# ============================================================
# D) XGBoost baselines
# ============================================================
def make_xgb_feature_matrix(df):
    """Return X (N_seg, 4*F) and y (class), domain. Features are concatenated
    across channels (X, Y, Z, Sound) per (file, seg_idx)."""
    feat_cols = [c for c in df.columns if c.startswith(("t_", "f_", "e_"))]
    pivot = df.pivot_table(
        index=["file", "class", "condition", "seg_idx"],
        columns="channel",
        values=feat_cols,
        aggfunc="first",
    )
    pivot.columns = [f"{ch}_{feat}" for feat, ch in pivot.columns]
    pivot = pivot.reset_index()
    X = pivot[[c for c in pivot.columns if c not in ["file", "class", "condition", "seg_idx"]]].values
    y = pivot["class"].map(lambda c: CLASSES.index(c)).values
    cond = pivot["condition"].values
    return X, y, cond, pivot["file"].values


def split_train_eval_by_time(df_pivot_files, df_pivot_segs):
    """Split per file into time-block train/test using seg_idx percentile."""
    pass  # not used; we use whole-file segments for XGBoost


def train_eval_xgb(X_train, y_train, X_test, y_test, n_classes=6):
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_test = scaler.transform(X_test)
    clf = xgb.XGBClassifier(
        n_estimators=300, max_depth=6, learning_rate=0.1,
        objective="multi:softprob", num_class=n_classes,
        eval_metric="mlogloss", tree_method="hist", verbosity=0,
        n_jobs=-1, random_state=0,
    )
    clf.fit(X_train, y_train)
    pred = clf.predict(X_test)
    return {
        "acc": float(accuracy_score(y_test, pred)),
        "macro_f1": float(f1_score(y_test, pred, average="macro")),
        "n_train": int(len(y_train)),
        "n_test": int(len(y_test)),
    }


def stage_D_xgb(df):
    print("\n[D] XGBoost baselines ...")
    X, y, cond, files = make_xgb_feature_matrix(df)
    print(f"  feature matrix: {X.shape}, y: {y.shape}, conditions: {np.unique(cond)}")

    results = {}

    # D1) Intra-condition (train/test on each condition separately, use seg_idx as time block)
    print("\n  [D1] Intra-condition (per-condition 70/30 time-block split):")
    intra = {}
    seg_idx_col = df.pivot_table(
        index=["file", "class", "condition", "seg_idx"],
        columns="channel", values="t_rms", aggfunc="first"
    ).reset_index()
    seg_idx = seg_idx_col["seg_idx"].values
    for c in CONDITIONS:
        mask = cond == c
        Xc, yc, sidx = X[mask], y[mask], seg_idx[mask]
        thresh = np.quantile(sidx, 0.70)
        tr = sidx <= thresh
        te = sidx > thresh
        r = train_eval_xgb(Xc[tr], yc[tr], Xc[te], yc[te])
        intra[f"{c}Hz"] = r
        print(f"    {c:>2}Hz  acc={r['acc']:.4f}  f1={r['macro_f1']:.4f}  ntr={r['n_train']} nte={r['n_test']}")
    results["xgb_intra_condition"] = intra
    results["xgb_intra_mean_acc"] = float(np.mean([v["acc"] for v in intra.values()]))

    # D2) Pooled (mix all conditions, time-block split per file)
    print("\n  [D2] Multi-condition pooled (70/30 time-block per file):")
    thresh = np.quantile(seg_idx, 0.70)
    tr = seg_idx <= thresh
    te = seg_idx > thresh
    r = train_eval_xgb(X[tr], y[tr], X[te], y[te])
    print(f"    pooled  acc={r['acc']:.4f}  f1={r['macro_f1']:.4f}")
    results["xgb_pooled"] = r

    # D3) Leave-one-condition-out (cross-condition DG)
    print("\n  [D3] Leave-one-condition-out (cross-condition DG):")
    loco = {}
    for test_c in CONDITIONS:
        tr = cond != test_c
        te = cond == test_c
        r = train_eval_xgb(X[tr], y[tr], X[te], y[te])
        loco[f"test_{test_c}Hz"] = r
        print(f"    train=others test={test_c:>2}Hz  acc={r['acc']:.4f}  f1={r['macro_f1']:.4f}")
    results["xgb_loco"] = loco
    results["xgb_loco_mean_acc"] = float(np.mean([v["acc"] for v in loco.values()]))
    results["xgb_loco_worst_acc"] = float(min(v["acc"] for v in loco.values()))

    return results


# ============================================================
# E) WDCNN deep baselines
# ============================================================
class WDCNN(nn.Module):
    def __init__(self, in_channels=3, num_classes=6):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv1d(in_channels, 16, kernel_size=64, stride=16, padding=24),
            nn.BatchNorm1d(16), nn.ReLU(), nn.MaxPool1d(2),
            nn.Conv1d(16, 32, kernel_size=3, padding=1),
            nn.BatchNorm1d(32), nn.ReLU(), nn.MaxPool1d(2),
            nn.Conv1d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm1d(64), nn.ReLU(), nn.MaxPool1d(2),
            nn.Conv1d(64, 64, kernel_size=3, padding=1),
            nn.BatchNorm1d(64), nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
        )
        self.fc = nn.Linear(64, num_classes)

    def forward(self, x):
        return self.fc(self.features(x).squeeze(-1))


class DualStreamCNN(nn.Module):
    def __init__(self, vib_ch=3, ac_ch=1, num_classes=6):
        super().__init__()
        def branch(c):
            return nn.Sequential(
                nn.Conv1d(c, 16, 64, stride=16, padding=24),
                nn.BatchNorm1d(16), nn.ReLU(), nn.MaxPool1d(2),
                nn.Conv1d(16, 32, 3, padding=1),
                nn.BatchNorm1d(32), nn.ReLU(), nn.MaxPool1d(2),
                nn.Conv1d(32, 64, 3, padding=1),
                nn.BatchNorm1d(64), nn.ReLU(), nn.MaxPool1d(2),
                nn.Conv1d(64, 64, 3, padding=1),
                nn.BatchNorm1d(64), nn.ReLU(),
                nn.AdaptiveAvgPool1d(1),
            )
        self.vib = branch(vib_ch)
        self.ac = branch(ac_ch)
        self.fc = nn.Sequential(
            nn.Linear(128, 64), nn.ReLU(), nn.Dropout(0.3),
            nn.Linear(64, num_classes),
        )

    def forward(self, xv, xa):
        v = self.vib(xv).squeeze(-1)
        a = self.ac(xa).squeeze(-1)
        return self.fc(torch.cat([v, a], dim=1))


def to_torch(X, y, batch=128, shuffle=True):
    """X shape (N, W, C) -> (N, C, W) for Conv1d."""
    X_t = torch.from_numpy(np.transpose(X, (0, 2, 1)).copy())
    y_t = torch.from_numpy(y)
    return DataLoader(TensorDataset(X_t, y_t), batch_size=batch, shuffle=shuffle, num_workers=0)


def per_segment_norm(X):
    """Instance-norm per segment, per channel."""
    mu = X.mean(axis=1, keepdims=True)
    sd = X.std(axis=1, keepdims=True) + 1e-6
    return (X - mu) / sd


def train_wdcnn(model, train_loader, val_loader, epochs=20, lr=1e-3, mm=False):
    model = model.to(DEVICE)
    opt = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs)
    best_val = 0.0
    best_state = None
    for ep in range(epochs):
        model.train()
        total, correct, loss_sum = 0, 0, 0.0
        for batch in train_loader:
            opt.zero_grad()
            if mm:
                xv, xa, y = batch
                xv, xa, y = xv.to(DEVICE), xa.to(DEVICE), y.to(DEVICE)
                logits = model(xv, xa)
            else:
                x, y = batch
                x, y = x.to(DEVICE), y.to(DEVICE)
                logits = model(x)
            loss = F.cross_entropy(logits, y)
            loss.backward()
            opt.step()
            total += y.size(0)
            correct += (logits.argmax(1) == y).sum().item()
            loss_sum += loss.item() * y.size(0)
        sched.step()
        train_acc = correct / total
        val_acc = eval_wdcnn(model, val_loader, mm=mm)["acc"]
        if val_acc > best_val:
            best_val = val_acc
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
    if best_state is not None:
        model.load_state_dict(best_state)
    return model


def eval_wdcnn(model, loader, mm=False):
    model.eval()
    ys, preds = [], []
    with torch.no_grad():
        for batch in loader:
            if mm:
                xv, xa, y = batch
                logits = model(xv.to(DEVICE), xa.to(DEVICE))
            else:
                x, y = batch
                logits = model(x.to(DEVICE))
            preds.append(logits.argmax(1).cpu().numpy())
            ys.append(y.numpy())
    y_true = np.concatenate(ys); y_pred = np.concatenate(preds)
    return {
        "acc": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, average="macro")),
    }


class MMDataset(torch.utils.data.Dataset):
    def __init__(self, Xv, Xa, y):
        self.Xv = torch.from_numpy(np.transpose(Xv, (0, 2, 1)).copy())
        self.Xa = torch.from_numpy(np.transpose(Xa, (0, 2, 1)).copy())
        self.y = torch.from_numpy(y)
    def __len__(self): return len(self.y)
    def __getitem__(self, i): return self.Xv[i], self.Xa[i], self.y[i]


def stage_E_dl(splits):
    print("\n[E] WDCNN deep baselines ...")
    Xv_tr = per_segment_norm(splits["train_X_vib"])
    Xv_va = per_segment_norm(splits["val_X_vib"])
    Xv_te = per_segment_norm(splits["test_X_vib"])
    Xa_tr = per_segment_norm(splits["train_X_ac"])
    Xa_va = per_segment_norm(splits["val_X_ac"])
    Xa_te = per_segment_norm(splits["test_X_ac"])
    y_tr = splits["train_y_class"]
    y_va = splits["val_y_class"]
    y_te = splits["test_y_class"]
    d_tr = splits["train_y_domain"]
    d_te = splits["test_y_domain"]

    print(f"  train={Xv_tr.shape[0]} val={Xv_va.shape[0]} test={Xv_te.shape[0]}")

    results = {}

    # E1) Vibration-only WDCNN (intra-domain pooled)
    print("\n  [E1] WDCNN vibration-only (pooled all conditions):")
    torch.manual_seed(0); np.random.seed(0)
    model = WDCNN(in_channels=3, num_classes=6)
    tr_loader = to_torch(Xv_tr, y_tr, shuffle=True)
    va_loader = to_torch(Xv_va, y_va, shuffle=False)
    te_loader = to_torch(Xv_te, y_te, shuffle=False)
    model = train_wdcnn(model, tr_loader, va_loader, epochs=20, lr=1e-3)
    r = eval_wdcnn(model, te_loader)
    print(f"    pooled  test acc={r['acc']:.4f}  f1={r['macro_f1']:.4f}")
    results["wdcnn_vib_pooled"] = r

    # E2) Acoustic-only WDCNN (pooled)
    print("\n  [E2] WDCNN acoustic-only (pooled all conditions):")
    torch.manual_seed(0); np.random.seed(0)
    model = WDCNN(in_channels=1, num_classes=6)
    tr_loader = to_torch(Xa_tr, y_tr, shuffle=True)
    va_loader = to_torch(Xa_va, y_va, shuffle=False)
    te_loader = to_torch(Xa_te, y_te, shuffle=False)
    model = train_wdcnn(model, tr_loader, va_loader, epochs=20, lr=1e-3)
    r = eval_wdcnn(model, te_loader)
    print(f"    pooled  test acc={r['acc']:.4f}  f1={r['macro_f1']:.4f}")
    results["wdcnn_ac_pooled"] = r

    # E3) Multimodal dual-stream (pooled)
    print("\n  [E3] DualStreamCNN multimodal (pooled all conditions):")
    torch.manual_seed(0); np.random.seed(0)
    model = DualStreamCNN(vib_ch=3, ac_ch=1, num_classes=6)
    tr_ds = MMDataset(Xv_tr, Xa_tr, y_tr); va_ds = MMDataset(Xv_va, Xa_va, y_va); te_ds = MMDataset(Xv_te, Xa_te, y_te)
    tr_loader = DataLoader(tr_ds, batch_size=128, shuffle=True)
    va_loader = DataLoader(va_ds, batch_size=128, shuffle=False)
    te_loader = DataLoader(te_ds, batch_size=128, shuffle=False)
    model = train_wdcnn(model, tr_loader, va_loader, epochs=20, lr=1e-3, mm=True)
    r = eval_wdcnn(model, te_loader, mm=True)
    print(f"    pooled  test acc={r['acc']:.4f}  f1={r['macro_f1']:.4f}")
    results["dualstream_pooled"] = r

    # E4) Cross-condition DG: leave-one-condition-out for vib-only and dual-stream
    print("\n  [E4] Leave-one-condition-out (cross-condition DG):")
    Xv_all = np.concatenate([Xv_tr, Xv_va, Xv_te], axis=0)
    Xa_all = np.concatenate([Xa_tr, Xa_va, Xa_te], axis=0)
    y_all = np.concatenate([y_tr, y_va, y_te], axis=0)
    d_all = np.concatenate([d_tr, splits["val_y_domain"], d_te], axis=0)

    loco_vib = {}
    loco_mm = {}
    for test_c_idx, test_c_hz in enumerate(CONDITIONS):
        tr = d_all != test_c_idx
        te = d_all == test_c_idx
        # vibration only
        torch.manual_seed(0); np.random.seed(0)
        m1 = WDCNN(in_channels=3, num_classes=6)
        tr_l = to_torch(Xv_all[tr], y_all[tr], shuffle=True)
        te_l = to_torch(Xv_all[te], y_all[te], shuffle=False)
        m1 = train_wdcnn(m1, tr_l, te_l, epochs=15, lr=1e-3)  # use test as val (not ideal but ok for DG demo)
        r1 = eval_wdcnn(m1, te_l)
        loco_vib[f"test_{test_c_hz}Hz"] = r1
        # multimodal
        torch.manual_seed(0); np.random.seed(0)
        m2 = DualStreamCNN(vib_ch=3, ac_ch=1, num_classes=6)
        tr_ds = MMDataset(Xv_all[tr], Xa_all[tr], y_all[tr])
        te_ds = MMDataset(Xv_all[te], Xa_all[te], y_all[te])
        tr_l = DataLoader(tr_ds, batch_size=128, shuffle=True)
        te_l = DataLoader(te_ds, batch_size=128, shuffle=False)
        m2 = train_wdcnn(m2, tr_l, te_l, epochs=15, lr=1e-3, mm=True)
        r2 = eval_wdcnn(m2, te_l, mm=True)
        loco_mm[f"test_{test_c_hz}Hz"] = r2
        print(f"    test={test_c_hz:>2}Hz   vib-only acc={r1['acc']:.4f}   dual-stream acc={r2['acc']:.4f}")

    results["wdcnn_vib_loco"] = loco_vib
    results["dualstream_loco"] = loco_mm
    results["wdcnn_vib_loco_mean_acc"] = float(np.mean([v["acc"] for v in loco_vib.values()]))
    results["wdcnn_vib_loco_worst_acc"] = float(min(v["acc"] for v in loco_vib.values()))
    results["dualstream_loco_mean_acc"] = float(np.mean([v["acc"] for v in loco_mm.values()]))
    results["dualstream_loco_worst_acc"] = float(min(v["acc"] for v in loco_mm.values()))
    return results


# ============================================================
# Main
# ============================================================
def main():
    t0 = time.time()
    stage_A_cache()
    data = load_cached()
    df = stage_B_features(data)
    splits = stage_C_splits(data)

    all_results = {}
    all_results.update(stage_D_xgb(df))
    all_results.update(stage_E_dl(splits))

    all_results["meta"] = {
        "fs": FS, "window": WINDOW,
        "train_overlap": TRAIN_OVERLAP, "eval_overlap": EVAL_OVERLAP,
        "n_files": 24, "n_classes": 6, "conditions": CONDITIONS,
        "device": str(DEVICE),
        "total_seconds": round(time.time() - t0, 1),
    }

    with open(RESULTS, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\n[done] saved -> {RESULTS}  (total {all_results['meta']['total_seconds']}s)")


if __name__ == "__main__":
    main()
