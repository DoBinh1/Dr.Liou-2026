"""Generate 01_exploration.ipynb - HUSTmotor exploration starter notebook (v2).

v2 adds:
  - Deeper signal processing: cepstrum, spectral kurtosis (kurtogram),
    CWT (PyWavelets), WPT energy distribution, coherence,
    cross-condition spectrum comparison, order spectrum
  - Baseline experiments: load + visualize baseline_results.json
    (XGBoost intra/pooled/LOCO, WDCNN vib/ac/dual-stream pooled and LOCO)

Run once: python _build_notebook.py
"""
import json
from pathlib import Path

OUT = Path(__file__).parent / "01_exploration.ipynb"


def md(*lines):
    src = []
    for i, l in enumerate(lines):
        if i < len(lines) - 1:
            src.append(l if l.endswith("\n") else l + "\n")
        else:
            src.append(l)
    return {"cell_type": "markdown", "metadata": {}, "source": src}


def code(*lines):
    src = []
    for i, l in enumerate(lines):
        if i < len(lines) - 1:
            src.append(l if l.endswith("\n") else l + "\n")
        else:
            src.append(l)
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": src,
    }


cells = []

# ============================================================
# Section 0 - title & overview
# ============================================================
cells.append(
    md(
        "# HUSTmotor Multimodal Dataset — Exploration Notebook (v2)",
        "",
        "**Mục đích**: starter notebook cho dataset understanding + signal processing nâng cao + baseline.",
        "",
        "Pipeline:",
        "1. **Section 1–4**: Setup, loader, quick inspection",
        "2. **Section 5–8**: Visualization cơ bản (raw, FFT, STFT, HES)",
        "3. **Section 9**: Deeper signal processing",
        "   - 9a. Spectral Kurtosis / Kurtogram → optimal bandpass cho envelope",
        "   - 9b. Cepstrum analysis → phát hiện harmonic family",
        "   - 9c. CWT (Continuous Wavelet Transform) — Morlet wavelet",
        "   - 9d. WPT (Wavelet Packet) energy distribution",
        "   - 9e. Coherence vibration ↔ acoustic",
        "   - 9f. Cross-condition spectrum comparison (same fault, 4 speeds)",
        "   - 9g. Order spectrum (speed normalization)",
        "4. **Section 10–14**: Handcrafted features + t-SNE + per-class stats + cross-condition",
        "5. **Section 15**: Segmentation utility (train/val/test splits.npz)",
        "6. **Section 16–17**: Baseline experiments",
        "   - 16. XGBoost (intra-condition, pooled, leave-one-condition-out DG)",
        "   - 17. WDCNN deep baselines (vib/ac/dual-stream, pooled and LOCO)",
        "7. **Section 18**: Results summary & next steps",
        "",
        "**Tham chiếu**: `TECHNICAL_REPORT.md`. Baseline runner: `_run_pipeline.py`.",
    )
)

# ============================================================
# 1. Setup
# ============================================================
cells.append(md("## 1. Setup"))
cells.append(
    code(
        "import os, json",
        "from pathlib import Path",
        "from collections import defaultdict",
        "",
        "import numpy as np",
        "import pandas as pd",
        "import matplotlib.pyplot as plt",
        "from scipy import signal as sps",
        "from scipy.stats import kurtosis, skew",
        "from scipy.signal import hilbert, stft, welch, butter, sosfiltfilt, coherence",
        "",
        "import pywt  # PyWavelets for CWT/WPT",
        "",
        "from sklearn.preprocessing import StandardScaler",
        "from sklearn.manifold import TSNE",
        "from sklearn.metrics import accuracy_score, f1_score, confusion_matrix",
        "",
        "plt.rcParams['figure.dpi'] = 100",
        "plt.rcParams['savefig.dpi'] = 150",
        "np.random.seed(42)",
    )
)

# ============================================================
# 2. Config
# ============================================================
cells.append(md("## 2. Config"))
cells.append(
    code(
        "ROOT = Path(r'D:/[Lab] HUST/Dr Liou - Multi modal/HUST motor multimodal dataset')",
        "DATA_DIR = ROOT / 'Raw data'",
        "FIG_DIR = ROOT / 'figures'",
        "FIG_DIR.mkdir(exist_ok=True)",
        "",
        "FS = 25600  # sampling frequency (Hz)",
        "N_TOTAL = 163840  # samples per file",
        "DURATION = N_TOTAL / FS  # 6.4 s",
        "",
        "CLASSES = ['H', 'BF', 'BOW', 'BROKEN', 'MISAL', 'UNBAL']",
        "CLASS_FULL = {",
        "    'H': 'Healthy', 'BF': 'Bearing Fault', 'BOW': 'Bowed Rotor',",
        "    'BROKEN': 'Broken Rotor Bars', 'MISAL': 'Rotor Misalignment',",
        "    'UNBAL': 'Voltage Unbalance',",
        "}",
        "CLASS_COLOR = dict(zip(CLASSES, plt.cm.tab10.colors[:6]))",
        "",
        "CONDITIONS = [5, 10, 20, 30]",
        "CHANNELS = ['X', 'Y', 'Z', 'Sound']",
        "CHANNEL_TYPE = {'X': 'vibration', 'Y': 'vibration', 'Z': 'vibration', 'Sound': 'acoustic'}",
        "",
        "F_LINE = 50.0  # line frequency (assumed Vietnam grid)",
        "",
        "print(f'Data dir: {DATA_DIR}')",
        "print(f'Files found: {len(list(DATA_DIR.glob(\"*.txt\")))}')",
        "print(f'fs={FS} Hz | duration={DURATION}s | N={N_TOTAL}')",
    )
)

# ============================================================
# 3. Loader
# ============================================================
cells.append(
    md(
        "## 3. Data Loader",
        "",
        "Format file: header ~17 dòng metadata, sau đó tab-separated `Time, X, Y, Z, Sound`.",
    )
)
cells.append(
    code(
        "def load_motor_file(path):",
        "    path = Path(path)",
        "    fname = path.stem",
        "    parts = fname.split('_')",
        "    label = parts[0]",
        "    condition = int(parts[1].replace('HZ', ''))",
        "    with open(path, 'r', encoding='utf-8', errors='ignore') as f:",
        "        lines = f.readlines()",
        "    data_start = None",
        "    for i, line in enumerate(lines):",
        "        if line.strip().startswith('Time (seconds)'):",
        "            data_start = i + 1; break",
        "    arr = np.loadtxt(lines[data_start:], delimiter='\\t')",
        "    return {",
        "        'time': arr[:, 0].astype(np.float32),",
        "        'X': arr[:, 1].astype(np.float32), 'Y': arr[:, 2].astype(np.float32),",
        "        'Z': arr[:, 3].astype(np.float32), 'Sound': arr[:, 4].astype(np.float32),",
        "        'label': label, 'condition': condition, 'fname': fname,",
        "    }",
        "",
        "def list_files():",
        "    return sorted(DATA_DIR.glob('*.txt'))",
        "",
        "files = list_files()",
        "print(f'Total files: {len(files)}')",
    )
)

# ============================================================
# 4. Quick inspection
# ============================================================
cells.append(md("## 4. Quick inspection — load 1 file"))
cells.append(
    code(
        "sample = load_motor_file(DATA_DIR / 'H_30HZ.txt')",
        "print(f\"label={sample['label']}, condition={sample['condition']} Hz, n={len(sample['X'])}\")",
        "for ch in CHANNELS:",
        "    s = sample[ch]",
        "    print(f'  {ch:6s}  mean={s.mean():+.4f}  std={s.std():.4f}  '",
        "          f'kurt={kurtosis(s):+.2f}  crest={np.max(np.abs(s))/(np.std(s)+1e-9):.2f}')",
    )
)

# ============================================================
# 5. Raw waveform 4 channels
# ============================================================
cells.append(md("## 5. Raw waveform — 4 channels (zoom 2 cycles)"))
cells.append(
    code(
        "def plot_raw_4ch(s, n_show=None):",
        "    fr = s['condition']",
        "    if n_show is None:",
        "        n_show = int(2 * FS / fr)",
        "    n_show = min(n_show, len(s['X']))",
        "    t = s['time'][:n_show]",
        "    fig, axes = plt.subplots(4, 1, figsize=(11, 7), sharex=True)",
        "    for ax, ch in zip(axes, CHANNELS):",
        "        col = 'C0' if CHANNEL_TYPE[ch]=='vibration' else 'C3'",
        "        ax.plot(t, s[ch][:n_show], lw=0.7, color=col)",
        "        ax.set_ylabel(f'{ch}\\n({CHANNEL_TYPE[ch]})'); ax.grid(alpha=0.3)",
        "    axes[-1].set_xlabel('Time (s)')",
        "    fig.suptitle(f\"{s['fname']} — {n_show/FS*1000:.0f} ms\")",
        "    plt.tight_layout(); plt.show()",
        "",
        "plot_raw_4ch(sample)",
    )
)

# ============================================================
# 6. Compare 6 classes at 30 Hz
# ============================================================
cells.append(md("## 6. So sánh 6 classes (cùng 30 Hz)"))
cells.append(
    code(
        "fig, axes = plt.subplots(6, 2, figsize=(13, 11), sharex='col')",
        "n_show = int(0.2 * FS)",
        "for i, cls in enumerate(CLASSES):",
        "    s = load_motor_file(DATA_DIR / f'{cls}_30HZ.txt')",
        "    t = s['time'][:n_show]",
        "    axes[i, 0].plot(t, s['X'][:n_show], lw=0.7, color=CLASS_COLOR[cls])",
        "    axes[i, 0].set_ylabel(f'{cls}\\n{CLASS_FULL[cls]}', fontsize=8); axes[i, 0].grid(alpha=0.3)",
        "    axes[i, 1].plot(t, s['Sound'][:n_show], lw=0.7, color=CLASS_COLOR[cls])",
        "    axes[i, 1].grid(alpha=0.3)",
        "axes[0, 0].set_title('Vibration X'); axes[0, 1].set_title('Acoustic')",
        "axes[-1, 0].set_xlabel('Time (s)'); axes[-1, 1].set_xlabel('Time (s)')",
        "fig.suptitle('6 health states @ 30 Hz — first 200 ms')",
        "plt.tight_layout(); plt.savefig(FIG_DIR / 'raw_6classes_30Hz.png'); plt.show()",
    )
)

# ============================================================
# 7. FFT
# ============================================================
cells.append(md("## 7. FFT spectra — 6 classes @ 30 Hz"))
cells.append(
    code(
        "def fft_log(x, fs):",
        "    n = len(x)",
        "    X = np.abs(np.fft.rfft(x * np.hanning(n)))",
        "    f = np.fft.rfftfreq(n, 1/fs)",
        "    return f, 20*np.log10(X + 1e-12)",
        "",
        "fig, axes = plt.subplots(6, 2, figsize=(13, 12), sharex='col', sharey='col')",
        "for i, cls in enumerate(CLASSES):",
        "    s = load_motor_file(DATA_DIR / f'{cls}_30HZ.txt')",
        "    f, X = fft_log(s['X'], FS)",
        "    axes[i, 0].plot(f, X, lw=0.6, color=CLASS_COLOR[cls])",
        "    axes[i, 0].set_xlim(0, 1500); axes[i, 0].set_ylabel(f'{cls}\\ndB', fontsize=8); axes[i, 0].grid(alpha=0.3)",
        "    for k in [1, 2, 3]: axes[i, 0].axvline(k*30, color='k', lw=0.4, ls='--', alpha=0.4)",
        "    for fL in [F_LINE, 2*F_LINE]: axes[i, 0].axvline(fL, color='r', lw=0.4, ls=':', alpha=0.4)",
        "    f, A = fft_log(s['Sound'], FS)",
        "    axes[i, 1].plot(f, A, lw=0.6, color=CLASS_COLOR[cls])",
        "    axes[i, 1].set_xlim(0, 6000); axes[i, 1].grid(alpha=0.3)",
        "axes[0, 0].set_title('Vibration X — FFT (0–1500 Hz)\\nblack: k×fr,  red: 50/100 Hz')",
        "axes[0, 1].set_title('Acoustic — FFT (0–6 kHz)')",
        "axes[-1, 0].set_xlabel('Frequency (Hz)'); axes[-1, 1].set_xlabel('Frequency (Hz)')",
        "fig.suptitle('FFT spectra — 6 classes @ 30 Hz')",
        "plt.tight_layout(); plt.savefig(FIG_DIR / 'fft_6classes_30Hz.png'); plt.show()",
    )
)

# ============================================================
# 8. Spectrogram
# ============================================================
cells.append(md("## 8. STFT Spectrogram — 6 classes @ 30 Hz"))
cells.append(
    code(
        "fig, axes = plt.subplots(2, 3, figsize=(15, 7))",
        "for ax, cls in zip(axes.flat, CLASSES):",
        "    s = load_motor_file(DATA_DIR / f'{cls}_30HZ.txt')",
        "    f, t, Sxx = stft(s['X'], fs=FS, nperseg=1024, noverlap=768)",
        "    Sxx_db = 20*np.log10(np.abs(Sxx) + 1e-12)",
        "    im = ax.pcolormesh(t, f, Sxx_db, shading='auto', cmap='magma',",
        "                       vmin=Sxx_db.max()-60, vmax=Sxx_db.max())",
        "    ax.set_title(f'{cls} — {CLASS_FULL[cls]}', fontsize=10)",
        "    ax.set_ylim(0, 6000); ax.set_ylabel('Hz'); ax.set_xlabel('Time (s)')",
        "fig.suptitle('STFT spectrogram (log power) — vibration X — 30 Hz')",
        "plt.tight_layout(); plt.savefig(FIG_DIR / 'spec_vib_6classes_30Hz.png'); plt.show()",
    )
)

# ============================================================
# 9. DEEPER SIGNAL PROCESSING
# ============================================================
cells.append(
    md(
        "## 9. Deeper Signal Processing",
        "",
        "Phần này đi sâu vào công cụ xử lý tín hiệu cho fault diagnosis:",
        "",
        "| Sub | Tool | Mục đích | Fault target |",
        "|---|---|---|---|",
        "| 9a | Spectral Kurtosis (Kurtogram) | tự động chọn resonance band | **BF** |",
        "| 9b | Cepstrum | phát hiện harmonic family / sideband | BROKEN, gear-mesh-like |",
        "| 9c | CWT (Morlet) | adaptive time-frequency | impulsive transients |",
        "| 9d | WPT energy | compact band-energy fingerprint | all (texture) |",
        "| 9e | Coherence vib↔ac | đánh giá information sharing | sanity for fusion |",
        "| 9f | Cross-condition spectrum | thấy tận mắt domain shift | DG analysis |",
        "| 9g | Order spectrum | speed-invariant view | DG mitigation |",
    )
)

# 9a Spectral Kurtosis / Kurtogram
cells.append(
    md(
        "### 9a. Spectral Kurtosis & Kurtogram",
        "",
        "**Vấn đề**: HES yêu cầu chọn bandpass quanh resonance — chọn sai band → mất signature.",
        "",
        "**Giải pháp**: Spectral Kurtosis (Antoni 2006) đo kurtosis của signal sau khi filter qua mỗi band [f, f+Δf]. Band có kurtosis cao nhất là band excited mạnh nhất bởi impulsive bearing — đó là band tối ưu cho HES.",
        "",
        "**Kurtogram**: hiển thị SK trên grid (level × center-frequency) → chọn (level\\*, fc\\*) tối ưu.",
        "",
        "Hữu dụng nhất khi BF có signature impulsive — H sẽ có SK gần 0.",
    )
)
cells.append(
    code(
        "def fast_kurtogram(x, fs, max_level=6):",
        "    \"\"\"Simplified fast kurtogram via STFT-based spectral kurtosis.",
        "    Returns 2D map (level, center_freq) of kurtosis.\"\"\"",
        "    levels = list(range(1, max_level+1))",
        "    out = []",
        "    for L in levels:",
        "        nperseg = 2 ** L * 16",
        "        if nperseg > len(x) // 4:",
        "            out.append((L, None, None)); continue",
        "        f, t, Z = stft(x, fs=fs, nperseg=nperseg, noverlap=nperseg//2,",
        "                       window='hann', return_onesided=True)",
        "        # SK per frequency bin: kurtosis across time of |Z|^2",
        "        P = np.abs(Z) ** 2",
        "        mu = P.mean(axis=1, keepdims=True)",
        "        sd = P.std(axis=1, keepdims=True) + 1e-12",
        "        sk = ((P - mu) ** 4).mean(axis=1) / (sd.squeeze() ** 4) - 3",
        "        out.append((L, f, sk))",
        "    return out",
        "",
        "def plot_kurtogram(x, fs, title=''):",
        "    kg = fast_kurtogram(x, fs)",
        "    fig, ax = plt.subplots(figsize=(10, 4))",
        "    grid = []",
        "    f_max = fs/2",
        "    for L, f, sk in kg:",
        "        if f is None: continue",
        "        ax.plot(f, sk, label=f'L={L} Δf={fs/(2**L*16):.0f}Hz', lw=0.7)",
        "    ax.set_xlim(0, f_max); ax.set_xlabel('Center frequency (Hz)')",
        "    ax.set_ylabel('Spectral kurtosis')",
        "    ax.set_title(f'Spectral kurtosis profile across STFT levels — {title}')",
        "    ax.legend(fontsize=7, loc='upper right'); ax.grid(alpha=0.3)",
        "    plt.tight_layout(); plt.show()",
        "    # find best (level, fc)",
        "    best = max(((L, f[np.argmax(sk)], sk.max()) for L, f, sk in kg if f is not None),",
        "               key=lambda x: x[2])",
        "    return best",
        "",
        "# Compare H vs BF",
        "for cls in ['H', 'BF']:",
        "    s = load_motor_file(DATA_DIR / f'{cls}_30HZ.txt')",
        "    best = plot_kurtogram(s['X'], FS, title=f\"{cls} @ 30 Hz vibration X\")",
        "    print(f'  {cls}: best level={best[0]}, fc={best[1]:.0f} Hz, SK={best[2]:.2f}')",
    )
)
cells.append(
    md(
        "**Insight**: Với BF, kurtogram thường peak rõ trong dải 2–6 kHz (resonance band của bearing housing). Với H, SK thường gần 0 toàn dải — không có impulsive component.",
    )
)

# 9b Cepstrum
cells.append(
    md(
        "### 9b. Cepstrum",
        "",
        "Cepstrum = `IFFT(log|FFT(x)|)`. Domain output là **quefrency** (đơn vị: giây).",
        "",
        "Hữu ích để:",
        "- **Phát hiện harmonic family**: harmonic series (1×, 2×, 3×, 4×, ...) trở thành **một peak duy nhất** ở quefrency = 1/fr",
        "- **Sideband detection**: 2sf₁ sideband quanh f_line (broken bar) → peak ở quefrency 1/(2sf₁)",
        "",
        "Compare 6 classes ở 30 Hz: kỳ vọng",
        "- **MISAL** sẽ có peak rõ ở 1/30 = 33.3 ms (do 1×, 2× harmonic mạnh)",
        "- **BROKEN** có peak ở 1/(2sf₁) (slip-dependent, vài chục ms)",
    )
)
cells.append(
    code(
        "def cepstrum(x):",
        "    n = len(x)",
        "    X = np.fft.rfft(x * np.hanning(n))",
        "    log_mag = np.log(np.abs(X) + 1e-12)",
        "    c = np.fft.irfft(log_mag, n=n)",
        "    return c[:n//2]",
        "",
        "fig, axes = plt.subplots(6, 1, figsize=(11, 11), sharex=True)",
        "for ax, cls in zip(axes, CLASSES):",
        "    s = load_motor_file(DATA_DIR / f'{cls}_30HZ.txt')",
        "    c = cepstrum(s['X'])",
        "    q = np.arange(len(c)) / FS  # quefrency in seconds",
        "    ax.plot(q*1000, c, lw=0.6, color=CLASS_COLOR[cls])",
        "    ax.set_xlim(2, 200)  # 2–200 ms (50–500 Hz inverse)",
        "    ax.set_ylabel(f'{cls}', fontsize=9); ax.grid(alpha=0.3)",
        "    ax.axvline(1000/30, color='k', lw=0.4, ls='--', alpha=0.5)  # 1/fr",
        "    ax.axvline(2*1000/30, color='k', lw=0.4, ls=':', alpha=0.5)  # 2/fr",
        "axes[-1].set_xlabel('Quefrency (ms)  — black: 1/fr=33.3ms, 2/fr=66.7ms')",
        "fig.suptitle('Real cepstrum — 6 classes @ 30 Hz vibration X')",
        "plt.tight_layout(); plt.savefig(FIG_DIR / 'cepstrum_6classes_30Hz.png'); plt.show()",
    )
)

# 9c CWT
cells.append(
    md(
        "### 9c. Continuous Wavelet Transform (Morlet)",
        "",
        "CWT cho **adaptive time-frequency resolution**: high-freq → narrow time window, low-freq → wide.",
        "Ideal cho impulsive transients (BF) và slow modulation (BROKEN).",
        "",
        "Dùng `pywt.cwt` với Complex Morlet wavelet. Compute trên một segment ngắn (4096 sample) để tránh memory issue.",
    )
)
cells.append(
    code(
        "def cwt_morlet(x, fs, n_scales=64, freq_range=(20, 6000)):",
        "    fc = pywt.central_frequency('cmor1.5-1.0')",
        "    f_low, f_high = freq_range",
        "    s_high = fc * fs / f_low",
        "    s_low = fc * fs / f_high",
        "    scales = np.geomspace(s_low, s_high, n_scales)",
        "    coefs, freqs = pywt.cwt(x, scales, 'cmor1.5-1.0', sampling_period=1/fs)",
        "    return np.abs(coefs), freqs",
        "",
        "# CWT for 6 classes (just 4096 samples to keep compute reasonable)",
        "fig, axes = plt.subplots(2, 3, figsize=(15, 7))",
        "for ax, cls in zip(axes.flat, CLASSES):",
        "    s = load_motor_file(DATA_DIR / f'{cls}_30HZ.txt')",
        "    seg = s['X'][:4096]",
        "    P, f = cwt_morlet(seg, FS, n_scales=80)",
        "    P_db = 20*np.log10(P + 1e-12)",
        "    t = np.arange(len(seg))/FS",
        "    im = ax.pcolormesh(t, f, P_db, shading='auto', cmap='magma',",
        "                       vmin=P_db.max()-50, vmax=P_db.max())",
        "    ax.set_yscale('log'); ax.set_ylim(20, 6000)",
        "    ax.set_title(f'{cls} — {CLASS_FULL[cls]}', fontsize=10)",
        "    ax.set_xlabel('Time (s)'); ax.set_ylabel('Hz (log)')",
        "fig.suptitle('Continuous Wavelet Transform (Morlet) — 4096 samples — 30 Hz')",
        "plt.tight_layout(); plt.savefig(FIG_DIR / 'cwt_6classes_30Hz.png'); plt.show()",
    )
)
cells.append(
    md(
        "**So sánh STFT vs CWT**: CWT có high-freq band (BF resonance) sắc nét hơn, low-freq chi tiết tốt hơn. Tradeoff là compute.",
    )
)

# 9d WPT
cells.append(
    md(
        "### 9d. Wavelet Packet Transform — Energy Distribution",
        "",
        "WPT phân chia toàn dải fs/2 thành 2^L sub-band đều. Với L=4 → 16 sub-band, mỗi band rộng fs/(2·16) = 800 Hz.",
        "",
        "Energy mỗi band = Σ(coef²). Plot energy distribution per fault → fingerprint **rất compact** cho ML/DL.",
    )
)
cells.append(
    code(
        "def wpt_energy(x, level=4, wavelet='db4'):",
        "    wp = pywt.WaveletPacket(data=x, wavelet=wavelet, mode='symmetric', maxlevel=level)",
        "    nodes = [n.path for n in wp.get_level(level, 'natural')]",
        "    energies = []",
        "    for path in nodes:",
        "        coef = wp[path].data",
        "        energies.append(np.sum(coef**2))",
        "    energies = np.array(energies)",
        "    energies = energies / (energies.sum() + 1e-12)",
        "    return energies, nodes",
        "",
        "L = 4",
        "n_bands = 2**L",
        "band_freqs = np.linspace(0, FS/2, n_bands+1)",
        "",
        "fig, ax = plt.subplots(figsize=(13, 5))",
        "x_pos = np.arange(n_bands)",
        "width = 0.13",
        "for i, cls in enumerate(CLASSES):",
        "    s = load_motor_file(DATA_DIR / f'{cls}_30HZ.txt')",
        "    e, _ = wpt_energy(s['X'][:65536], level=L)",
        "    ax.bar(x_pos + i*width, e, width, color=CLASS_COLOR[cls], label=cls, alpha=0.8)",
        "ax.set_xticks(x_pos + 2.5*width)",
        "ax.set_xticklabels([f'{int(band_freqs[i])}–{int(band_freqs[i+1])}' for i in range(n_bands)],",
        "                   rotation=45, fontsize=8)",
        "ax.set_xlabel('Frequency band (Hz)'); ax.set_ylabel('Normalized energy')",
        "ax.set_title(f'WPT level-{L} energy distribution — 6 classes @ 30 Hz vibration X')",
        "ax.legend(); ax.grid(alpha=0.3, axis='y')",
        "plt.tight_layout(); plt.savefig(FIG_DIR / f'wpt_L{L}_6classes_30Hz.png'); plt.show()",
    )
)

# 9e Coherence
cells.append(
    md(
        "### 9e. Coherence vibration ↔ acoustic",
        "",
        "**Coherence γ²(f) ∈ [0,1]** đo mức độ vibration và acoustic share thông tin tại tần số f.",
        "- γ² ≈ 1 → hai modality redundant tại f đó",
        "- γ² ≈ 0 → modality độc lập (cần fusion để bổ sung)",
        "",
        "Plot coherence của H vs BF — kỳ vọng BF sẽ có coherence cao ở high-freq band do bearing impulse phát sóng cả mechanical lẫn airborne.",
    )
)
cells.append(
    code(
        "fig, axes = plt.subplots(2, 1, figsize=(11, 6), sharex=True)",
        "for ax, cls in zip(axes, ['H', 'BF']):",
        "    s = load_motor_file(DATA_DIR / f'{cls}_30HZ.txt')",
        "    f, Cxy = coherence(s['X'], s['Sound'], fs=FS, nperseg=4096)",
        "    ax.semilogy(f, Cxy + 1e-3, lw=0.6, color=CLASS_COLOR[cls])",
        "    ax.set_xlim(0, 6000); ax.set_ylim(0.01, 1.5)",
        "    ax.set_ylabel(f'{cls}\\n$\\\\gamma^2(f)$'); ax.grid(alpha=0.3, which='both')",
        "axes[-1].set_xlabel('Frequency (Hz)')",
        "fig.suptitle('Coherence vibration X ↔ acoustic — H vs BF @ 30 Hz')",
        "plt.tight_layout(); plt.savefig(FIG_DIR / 'coherence_H_vs_BF.png'); plt.show()",
        "print('High coherence band → modality redundancy')",
        "print('Low coherence band → fusion brings genuine new info')",
    )
)

# 9f Cross-condition spectrum
cells.append(
    md(
        "### 9f. Cross-condition spectrum — same fault, 4 speeds",
        "",
        "Để **thấy tận mắt domain shift**: cùng class BF, 4 speeds khác nhau.",
        "Kỳ vọng: peaks dịch chuyển thẳng tỷ lệ với speed → đó là pain-point chính của DG.",
    )
)
cells.append(
    code(
        "fig, axes = plt.subplots(4, 1, figsize=(12, 9), sharex=True)",
        "for ax, c in zip(axes, CONDITIONS):",
        "    s = load_motor_file(DATA_DIR / f'BF_{c}HZ.txt')",
        "    f, X = fft_log(s['X'], FS)",
        "    ax.plot(f, X, lw=0.6, color='C0')",
        "    ax.set_xlim(0, 1000); ax.set_ylabel(f'BF @ {c}Hz\\ndB'); ax.grid(alpha=0.3)",
        "    for k in [1, 2, 3, 4, 5]: ax.axvline(k*c, color='r', lw=0.3, ls='--', alpha=0.5)",
        "    ax.axvline(F_LINE, color='g', lw=0.4, ls=':', alpha=0.6)",
        "    ax.text(F_LINE+5, X.max()*0.9, '50Hz', fontsize=8, color='g')",
        "axes[-1].set_xlabel('Frequency (Hz)  — red dashed = k×fr')",
        "fig.suptitle('BF — same fault, 4 working conditions — peaks shift with speed')",
        "plt.tight_layout(); plt.savefig(FIG_DIR / 'cross_condition_BF.png'); plt.show()",
    )
)

# 9g Order spectrum
cells.append(
    md(
        "### 9g. Order spectrum — speed normalization",
        "",
        "**Thay đổi trục frequency → trục order (số lần ÷ fr)**: peak tại 1× luôn ở order=1, peak tại 2× luôn ở order=2, bất kể speed.",
        "→ Đây chính là cách kill domain shift trên rotating machinery.",
        "",
        "Vì speed constant trong mỗi file, order spectrum chỉ đơn giản là FFT chia theo fr.",
    )
)
cells.append(
    code(
        "def order_spectrum(x, fs, fr, n_orders=20, n_per_order=10):",
        "    n = len(x)",
        "    X = np.abs(np.fft.rfft(x * np.hanning(n)))",
        "    f = np.fft.rfftfreq(n, 1/fs)",
        "    orders = f / fr",
        "    mask = orders <= n_orders",
        "    return orders[mask], X[mask]",
        "",
        "# Compare 4 conditions of BF in order domain — peaks should align",
        "fig, ax = plt.subplots(figsize=(12, 5))",
        "for c in CONDITIONS:",
        "    s = load_motor_file(DATA_DIR / f'BF_{c}HZ.txt')",
        "    o, X = order_spectrum(s['X'], FS, c, n_orders=20)",
        "    Xnorm = X / X.max()",
        "    ax.plot(o, 20*np.log10(Xnorm + 1e-6), lw=0.7, label=f'{c} Hz', alpha=0.85)",
        "ax.set_xlabel('Order (× fr)'); ax.set_ylabel('Normalized magnitude (dB)')",
        "ax.set_title('Order spectrum — BF across 4 working conditions (peaks align at integer orders)')",
        "ax.legend(); ax.grid(alpha=0.3)",
        "ax.set_xlim(0, 20)",
        "for k in [1, 2, 3, 4, 5]: ax.axvline(k, color='k', lw=0.3, ls=':', alpha=0.5)",
        "plt.tight_layout(); plt.savefig(FIG_DIR / 'order_spectrum_BF.png'); plt.show()",
        "print('Note: vertical lines align at integer orders k=1,2,3,...')",
        "print('Order normalization is a strong inductive bias for cross-condition DG.')",
    )
)

# ============================================================
# 10. Hilbert Envelope Spectrum (using kurtogram-selected band)
# ============================================================
cells.append(
    md(
        "## 10. Hilbert Envelope Spectrum — using kurtogram-selected band",
        "",
        "Phối hợp 9a + HES: dùng kurtogram để chọn band, rồi compute envelope spectrum.",
        "Kỳ vọng: BF có peak rõ tại f_BPFO (≈ 3.5×fr cho bearing thông dụng) và harmonics, còn H phẳng.",
    )
)
cells.append(
    code(
        "def hilbert_envelope_spectrum(x, fs, band=(2000, 6000)):",
        "    sos = butter(4, band, btype='bandpass', fs=fs, output='sos')",
        "    xf = sosfiltfilt(sos, x)",
        "    env = np.abs(hilbert(xf)); env = env - env.mean()",
        "    n = len(env)",
        "    E = np.abs(np.fft.rfft(env * np.hanning(n)))",
        "    f = np.fft.rfftfreq(n, 1/fs)",
        "    return f, E",
        "",
        "fig, axes = plt.subplots(2, 1, figsize=(11, 6), sharex=True)",
        "for ax, cls in zip(axes, ['H', 'BF']):",
        "    s = load_motor_file(DATA_DIR / f'{cls}_30HZ.txt')",
        "    f, E = hilbert_envelope_spectrum(s['X'], FS, band=(2000, 6000))",
        "    ax.plot(f, E, lw=0.7, color=CLASS_COLOR[cls])",
        "    ax.set_xlim(0, 500); ax.set_ylabel(f'{cls}\\n|env|'); ax.grid(alpha=0.3)",
        "    for k in [1, 2, 3, 4]: ax.axvline(k*30, color='k', lw=0.5, ls='--', alpha=0.4)",
        "axes[-1].set_xlabel('Frequency (Hz)  — black dashed = k × fr')",
        "fig.suptitle('Hilbert Envelope Spectrum — H vs BF (band 2–6 kHz)')",
        "plt.tight_layout(); plt.savefig(FIG_DIR / 'hes_H_vs_BF_30Hz.png'); plt.show()",
    )
)

# ============================================================
# 11. Handcrafted features
# ============================================================
cells.append(md("## 11. Handcrafted feature extraction"))
cells.append(
    code(
        "def time_features(x):",
        "    x = x.astype(np.float64)",
        "    rms = np.sqrt(np.mean(x**2))",
        "    abs_mean = np.mean(np.abs(x))",
        "    peak = np.max(np.abs(x))",
        "    return {",
        "        'mean': float(np.mean(x)), 'std': float(np.std(x)), 'rms': float(rms),",
        "        'kurt': float(kurtosis(x)), 'skew': float(skew(x)), 'p2p': float(np.ptp(x)),",
        "        'crest': float(peak/(rms+1e-12)), 'impulse': float(peak/(abs_mean+1e-12)),",
        "        'shape': float(rms/(abs_mean+1e-12)),",
        "        'margin': float(peak/(np.mean(np.sqrt(np.abs(x)))**2 + 1e-12)),",
        "    }",
        "",
        "def freq_features(x, fs, fr, f_line=F_LINE):",
        "    n = len(x); X = np.abs(np.fft.rfft(x * np.hanning(n)))",
        "    f = np.fft.rfftfreq(n, 1/fs); P = X**2; Psum = P.sum()+1e-12",
        "    p_norm = P / Psum",
        "    out = {",
        "        'sp_centroid': float((f * P).sum() / Psum),",
        "        'sp_entropy': float(-(p_norm * np.log(p_norm + 1e-12)).sum()),",
        "    }",
        "    for lo, hi in [(0,100),(100,500),(500,1000),(1000,2000),(2000,4000),(4000,6000),(6000,12000)]:",
        "        m = (f >= lo) & (f < hi)",
        "        out[f'be_{lo}_{hi}'] = float(P[m].sum() / Psum)",
        "    def peak_amp_near(t, bw=2.0):",
        "        m = (f > t-bw) & (f < t+bw)",
        "        return float(X[m].max()) if m.any() else 0.0",
        "    out.update({",
        "        'amp_1x': peak_amp_near(fr), 'amp_2x': peak_amp_near(2*fr),",
        "        'amp_3x': peak_amp_near(3*fr), 'amp_fline': peak_amp_near(f_line),",
        "        'amp_2fline': peak_amp_near(2*f_line),",
        "    })",
        "    return out",
        "",
        "def envelope_features(x, fs, fr, band=(2000, 6000)):",
        "    sos = butter(4, band, btype='bandpass', fs=fs, output='sos')",
        "    xf = sosfiltfilt(sos, x)",
        "    env = np.abs(hilbert(xf)); env = env - env.mean()",
        "    n = len(env); E = np.abs(np.fft.rfft(env * np.hanning(n)))",
        "    f = np.fft.rfftfreq(n, 1/fs)",
        "    out = {}",
        "    for k in [1, 2, 3]:",
        "        m = (f > k*fr-2) & (f < k*fr+2)",
        "        out[f'env_k{k}'] = float(E[m].max()) if m.any() else 0.0",
        "    out['env_total'] = float(E.sum())",
        "    return out",
        "",
        "def extract_features(seg, fs, fr):",
        "    f = {}",
        "    for k, v in time_features(seg).items(): f[f't_{k}'] = v",
        "    for k, v in freq_features(seg, fs, fr).items(): f[f'f_{k}'] = v",
        "    for k, v in envelope_features(seg, fs, fr).items(): f[f'e_{k}'] = v",
        "    return f",
        "",
        "feats = extract_features(sample['X'][:4096], FS, 30)",
        "print(f'{len(feats)} features extracted, e.g.:')",
        "for k in list(feats)[:8]:",
        "    print(f'  {k:15s} = {feats[k]:+.4e}')",
    )
)

# ============================================================
# 12. Build feature dataset
# ============================================================
cells.append(md("## 12. Build feature dataset for all 24 files"))
cells.append(
    code(
        "WINDOW = 4096; STEP = 2048",
        "def segment(x, w=WINDOW, s=STEP):",
        "    n = (len(x) - w) // s + 1",
        "    return np.stack([x[i*s:i*s+w] for i in range(n)], axis=0)",
        "",
        "FEAT_CSV = ROOT / 'features_per_segment.csv'",
        "if FEAT_CSV.exists():",
        "    df = pd.read_csv(FEAT_CSV)",
        "    print(f'Loaded existing: {FEAT_CSV} (rows={len(df)})')",
        "else:",
        "    rows = []",
        "    for path in list_files():",
        "        d = load_motor_file(path); fr = d['condition']",
        "        for ch in CHANNELS:",
        "            for seg_idx, seg in enumerate(segment(d[ch])):",
        "                f = extract_features(seg, FS, fr)",
        "                f.update({'file': d['fname'], 'class': d['label'], 'condition': fr,",
        "                          'channel': ch, 'channel_type': CHANNEL_TYPE[ch], 'seg_idx': seg_idx})",
        "                rows.append(f)",
        "    df = pd.DataFrame(rows); df.to_csv(FEAT_CSV, index=False)",
        "    print(f'Saved: {FEAT_CSV}')",
        "",
        "feat_cols = [c for c in df.columns if c.startswith(('t_','f_','e_'))]",
        "print(f'Feature cols ({len(feat_cols)}): {feat_cols[:10]}...')",
    )
)

# ============================================================
# 13. Quick t-SNE
# ============================================================
cells.append(md("## 13. t-SNE — feature space (vibration X)"))
cells.append(
    code(
        "sub = df[df['channel'] == 'X'].reset_index(drop=True)",
        "X_feat = sub[feat_cols].values",
        "X_scaled = StandardScaler().fit_transform(X_feat)",
        "rng = np.random.default_rng(0)",
        "idx = rng.choice(len(X_scaled), size=min(2000, len(X_scaled)), replace=False)",
        "Xs = X_scaled[idx]",
        "labels = sub['class'].values[idx]; domains = sub['condition'].values[idx]",
        "Z = TSNE(n_components=2, perplexity=30, init='pca', random_state=0).fit_transform(Xs)",
        "",
        "fig, axes = plt.subplots(1, 2, figsize=(13, 6))",
        "for cls in CLASSES:",
        "    m = labels == cls",
        "    axes[0].scatter(Z[m, 0], Z[m, 1], s=8, alpha=0.6, color=CLASS_COLOR[cls], label=cls)",
        "axes[0].legend(loc='best', fontsize=9); axes[0].set_title('t-SNE — colored by CLASS')",
        "for d, mk in zip(CONDITIONS, ['o','s','^','D']):",
        "    m = domains == d",
        "    axes[1].scatter(Z[m, 0], Z[m, 1], s=8, alpha=0.6, marker=mk, label=f'{d} Hz')",
        "axes[1].legend(loc='best', fontsize=9); axes[1].set_title('t-SNE — colored by CONDITION (domain)')",
        "fig.suptitle('Feature space (50d) — 2D t-SNE')",
        "plt.tight_layout(); plt.savefig(FIG_DIR / 'tsne_features_X.png'); plt.show()",
    )
)

# ============================================================
# 14. Per-class & cross-condition stats
# ============================================================
cells.append(md("## 14. Per-class & cross-condition stats"))
cells.append(
    code(
        "agg = df[df['channel'] == 'X'].groupby('class')[['t_kurt','t_crest','t_rms']].mean().reindex(CLASSES)",
        "print('Mean per class — vibration X:'); print(agg.round(3))",
        "fig, axes = plt.subplots(1, 3, figsize=(13, 4))",
        "for ax, col in zip(axes, ['t_kurt','t_crest','t_rms']):",
        "    ax.bar(agg.index, agg[col], color=[CLASS_COLOR[c] for c in agg.index])",
        "    ax.set_title(col); ax.tick_params(axis='x', rotation=45); ax.grid(axis='y', alpha=0.3)",
        "fig.suptitle('Mean per class — pooled across conditions')",
        "plt.tight_layout(); plt.savefig(FIG_DIR / 'per_class_stats.png'); plt.show()",
        "",
        "rms_by_cond = df[df['channel'] == 'X'].groupby(['class','condition'])['t_rms'].mean().unstack().reindex(CLASSES)",
        "print('\\nRMS scaling with speed:'); print(rms_by_cond.round(4))",
        "fig, ax = plt.subplots(figsize=(8, 5))",
        "for cls in CLASSES:",
        "    ax.plot(CONDITIONS, rms_by_cond.loc[cls].values, '-o', color=CLASS_COLOR[cls], label=cls, lw=1.5)",
        "ax.set_xscale('log'); ax.set_yscale('log')",
        "ax.set_xlabel('Working condition (Hz)'); ax.set_ylabel('Mean RMS (vib X)')",
        "ax.set_title('RMS scaling with speed — domain shift evidence')",
        "ax.legend(); ax.grid(alpha=0.3, which='both')",
        "plt.tight_layout(); plt.savefig(FIG_DIR / 'rms_vs_condition.png'); plt.show()",
    )
)

# ============================================================
# 15. Segmentation utility for downstream
# ============================================================
cells.append(
    md(
        "## 15. Segmentation utility — splits.npz",
        "",
        "Time-block split per file: train 0–70%, val 70–85%, test 85–100% → no leakage.",
        "Output `splits.npz` chứa `train/val/test_X_vib (N,4096,3)`, `_X_ac (N,4096,1)`, `_y_class`, `_y_domain`.",
    )
)
cells.append(
    code(
        "TRAIN_OVERLAP = 0.5; EVAL_OVERLAP = 0.0",
        "SPLITS = ROOT / 'splits.npz'",
        "",
        "def build_split(t0, t1, overlap):",
        "    Xv, Xa, yc, yd = [], [], [], []",
        "    for path in list_files():",
        "        d = load_motor_file(path); n = len(d['X'])",
        "        i0, i1 = int(t0*n), int(t1*n)",
        "        vib = np.stack([d['X'][i0:i1], d['Y'][i0:i1], d['Z'][i0:i1]], axis=-1)",
        "        ac = d['Sound'][i0:i1, None]",
        "        if len(vib) < WINDOW: continue",
        "        step = max(1, int(WINDOW * (1 - overlap)))",
        "        n_seg = (len(vib) - WINDOW) // step + 1",
        "        for k in range(n_seg):",
        "            a, b = k*step, k*step + WINDOW",
        "            Xv.append(vib[a:b]); Xa.append(ac[a:b])",
        "            yc.append(CLASSES.index(d['label']))",
        "            yd.append(CONDITIONS.index(d['condition']))",
        "    return (np.asarray(Xv, dtype=np.float32), np.asarray(Xa, dtype=np.float32),",
        "            np.asarray(yc, dtype=np.int64), np.asarray(yd, dtype=np.int64))",
        "",
        "if SPLITS.exists():",
        "    splits = np.load(SPLITS)",
        "    print(f'Loaded existing: {SPLITS}')",
        "else:",
        "    tr = build_split(0.0, 0.70, TRAIN_OVERLAP)",
        "    va = build_split(0.70, 0.85, EVAL_OVERLAP)",
        "    te = build_split(0.85, 1.00, EVAL_OVERLAP)",
        "    np.savez_compressed(SPLITS,",
        "        train_X_vib=tr[0], train_X_ac=tr[1], train_y_class=tr[2], train_y_domain=tr[3],",
        "        val_X_vib=va[0], val_X_ac=va[1], val_y_class=va[2], val_y_domain=va[3],",
        "        test_X_vib=te[0], test_X_ac=te[1], test_y_class=te[2], test_y_domain=te[3])",
        "    splits = np.load(SPLITS)",
        "    print(f'Saved: {SPLITS}')",
        "",
        "for name in ['train','val','test']:",
        "    print(f'  {name}: vib={splits[f\"{name}_X_vib\"].shape}  ac={splits[f\"{name}_X_ac\"].shape}')",
    )
)

# ============================================================
# 16. Baseline experiments — XGBoost
# ============================================================
cells.append(
    md(
        "## 16. Baseline experiments",
        "",
        "Baselines được chạy bởi script `_run_pipeline.py` (XGBoost + WDCNN + DualStreamCNN).",
        "Notebook này load và visualize kết quả từ `baseline_results.json`.",
        "",
        "**3 setups** được đánh giá:",
        "1. **Intra-condition**: train/test cùng 1 condition, 70/30 time-block",
        "2. **Pooled**: trộn 4 conditions, 70/30 time-block per file",
        "3. **Leave-One-Condition-Out (LOCO)**: train 3 conditions, test 1 → cross-condition DG",
    )
)
cells.append(
    code(
        "RESULTS = ROOT / 'baseline_results.json'",
        "if not RESULTS.exists():",
        "    print('Chưa có kết quả. Chạy: python _run_pipeline.py'); raise SystemExit",
        "with open(RESULTS) as f:",
        "    R = json.load(f)",
        "print('Loaded baseline_results.json'); print('keys:', list(R.keys())[:8])",
    )
)

# 16a XGBoost results
cells.append(md("### 16a. XGBoost baseline (handcrafted features)"))
cells.append(
    code(
        "rows = []",
        "for c, r in R['xgb_intra_condition'].items():",
        "    rows.append({'setup': 'Intra', 'condition': c, 'acc': r['acc'], 'f1': r['macro_f1']})",
        "rows.append({'setup': 'Pooled', 'condition': 'all', 'acc': R['xgb_pooled']['acc'], 'f1': R['xgb_pooled']['macro_f1']})",
        "for c, r in R['xgb_loco'].items():",
        "    rows.append({'setup': 'LOCO', 'condition': c.replace('test_',''), 'acc': r['acc'], 'f1': r['macro_f1']})",
        "tab_xgb = pd.DataFrame(rows)",
        "print(tab_xgb.to_string(index=False, float_format=lambda x: f'{x:.4f}'))",
        "print(f\"\\nXGB intra mean acc:  {R['xgb_intra_mean_acc']:.4f}\")",
        "print(f\"XGB pooled acc:      {R['xgb_pooled']['acc']:.4f}\")",
        "print(f\"XGB LOCO mean acc:   {R['xgb_loco_mean_acc']:.4f}\")",
        "print(f\"XGB LOCO worst acc:  {R['xgb_loco_worst_acc']:.4f}  ← real DG metric\")",
    )
)

# 16b WDCNN results
cells.append(md("### 16b. Deep baselines (WDCNN, DualStreamCNN)"))
cells.append(
    code(
        "print('=== Pooled (intra-domain training) ===')",
        "print(f\"  WDCNN vibration-only:    acc={R['wdcnn_vib_pooled']['acc']:.4f}  f1={R['wdcnn_vib_pooled']['macro_f1']:.4f}\")",
        "print(f\"  WDCNN acoustic-only:     acc={R['wdcnn_ac_pooled']['acc']:.4f}  f1={R['wdcnn_ac_pooled']['macro_f1']:.4f}\")",
        "print(f\"  DualStreamCNN multimod:  acc={R['dualstream_pooled']['acc']:.4f}  f1={R['dualstream_pooled']['macro_f1']:.4f}\")",
        "print()",
        "print('=== Leave-One-Condition-Out (cross-condition DG) ===')",
        "rows = []",
        "for c in CONDITIONS:",
        "    k = f'test_{c}Hz'",
        "    rows.append({",
        "        'test_cond': f'{c}Hz',",
        "        'WDCNN_vib_acc': R['wdcnn_vib_loco'][k]['acc'],",
        "        'DualStream_acc': R['dualstream_loco'][k]['acc'],",
        "        'WDCNN_vib_f1': R['wdcnn_vib_loco'][k]['macro_f1'],",
        "        'DualStream_f1': R['dualstream_loco'][k]['macro_f1'],",
        "    })",
        "tab_dg = pd.DataFrame(rows)",
        "print(tab_dg.to_string(index=False, float_format=lambda x: f'{x:.4f}'))",
        "print(f\"\\nWDCNN vib  LOCO   mean={R['wdcnn_vib_loco_mean_acc']:.4f}   worst={R['wdcnn_vib_loco_worst_acc']:.4f}\")",
        "print(f\"DualStream LOCO   mean={R['dualstream_loco_mean_acc']:.4f}   worst={R['dualstream_loco_worst_acc']:.4f}\")",
    )
)

# 16c visualization
cells.append(md("### 16c. Results visualization"))
cells.append(
    code(
        "fig, axes = plt.subplots(1, 2, figsize=(14, 5))",
        "",
        "# Plot 1: pooled comparison",
        "labels_p = ['XGBoost\\n(features)', 'WDCNN\\n(vib only)', 'WDCNN\\n(acoustic)', 'DualStream\\n(multi)']",
        "vals_p = [R['xgb_pooled']['acc'], R['wdcnn_vib_pooled']['acc'],",
        "          R['wdcnn_ac_pooled']['acc'], R['dualstream_pooled']['acc']]",
        "axes[0].bar(labels_p, vals_p, color=['#3a86ff', '#06d6a0', '#ffd166', '#ef476f'])",
        "axes[0].set_ylim(0.5, 1.02); axes[0].set_ylabel('Test accuracy')",
        "axes[0].set_title('Pooled (intra-domain) — all >99% except acoustic-only')",
        "axes[0].grid(axis='y', alpha=0.3)",
        "for i, v in enumerate(vals_p):",
        "    axes[0].text(i, v + 0.005, f'{v:.3f}', ha='center', fontsize=9)",
        "",
        "# Plot 2: LOCO per condition",
        "x = np.arange(len(CONDITIONS)); w = 0.27",
        "xgb_loco_v = [R['xgb_loco'][f'test_{c}Hz']['acc'] for c in CONDITIONS]",
        "wdcnn_loco_v = [R['wdcnn_vib_loco'][f'test_{c}Hz']['acc'] for c in CONDITIONS]",
        "ds_loco_v = [R['dualstream_loco'][f'test_{c}Hz']['acc'] for c in CONDITIONS]",
        "axes[1].bar(x - w, xgb_loco_v, w, label='XGBoost', color='#3a86ff')",
        "axes[1].bar(x, wdcnn_loco_v, w, label='WDCNN vib', color='#06d6a0')",
        "axes[1].bar(x + w, ds_loco_v, w, label='DualStream', color='#ef476f')",
        "axes[1].set_xticks(x); axes[1].set_xticklabels([f'{c}Hz' for c in CONDITIONS])",
        "axes[1].set_ylabel('Test accuracy on unseen domain')",
        "axes[1].set_title('Leave-One-Condition-Out — DG drops sharply (5Hz catastrophic for XGBoost)')",
        "axes[1].axhline(1/6, color='k', ls=':', lw=0.6, alpha=0.5)",
        "axes[1].text(3.4, 1/6 + 0.02, 'chance', fontsize=8)",
        "axes[1].legend(loc='lower left', fontsize=9); axes[1].grid(axis='y', alpha=0.3)",
        "axes[1].set_ylim(0, 1.02)",
        "",
        "fig.suptitle('Baseline experiments — pooled vs cross-condition DG')",
        "plt.tight_layout(); plt.savefig(FIG_DIR / 'baseline_summary.png'); plt.show()",
    )
)

# 16d Key findings
cells.append(
    md(
        "### 16d. Key findings từ baseline",
        "",
        "1. **Intra-condition đã saturate**: XGBoost 98.4%, WDCNN 99.3%. Không còn nhiều dư địa cải tiến nội-domain.",
        "",
        "2. **Pooled cũng saturate** (~100%): trộn 4 conditions vẫn dễ, vì model học mỗi condition như một feature mode riêng.",
        "",
        "3. **Cross-condition DG là vấn đề thực sự**:",
        "   - XGBoost LOCO mean = 69.7%, **worst = 21.3%** (test=5Hz, gần chance level 16.7%)",
        "   - WDCNN vib LOCO mean = 89.0%, worst = 76.9%",
        "   - DualStream LOCO mean = 82.0%, worst = 62.2%",
        "",
        "4. **Naive multimodal HURT DG**: dual-stream tệ hơn vib-only. Lý do: acoustic SNR thấp ở low-speed, model bị lệch về mode tương ứng. → cần fusion thông minh (cross-attention + modality dropout + contrastive).",
        "",
        "5. **Acoustic-only yếu** (81%) — bổ sung chứ không thay thế vibration được.",
        "",
        "6. **5 Hz là điểm chết của XGBoost** — handcrafted feature ở các condition ≥10Hz không generalize cho 5Hz vì dynamic range và spectral position quá khác. Đây là evidence cụ thể cho việc cần **order tracking** hoặc **speed-aware adapter**.",
        "",
        "→ **Hướng paper rõ ràng**: cross-condition DG + smart multimodal fusion + physics (order tracking).",
    )
)

# ============================================================
# 17. Confusion matrix demo (LOCO test=5Hz)
# ============================================================
cells.append(
    md(
        "## 17. Confusion matrix — XGBoost LOCO test=5Hz (failure case)",
        "",
        "Để hiểu **đâu là class bị confuse** khi DG fail, retrain nhanh XGBoost cho setup này và plot confusion matrix.",
    )
)
cells.append(
    code(
        "import xgboost as xgb",
        "from sklearn.metrics import confusion_matrix as cm",
        "",
        "feat_cols2 = [c for c in df.columns if c.startswith(('t_','f_','e_'))]",
        "pivot = df.pivot_table(index=['file','class','condition','seg_idx'],",
        "                       columns='channel', values=feat_cols2, aggfunc='first')",
        "pivot.columns = [f'{ch}_{ft}' for ft, ch in pivot.columns]",
        "pivot = pivot.reset_index()",
        "X_all = pivot[[c for c in pivot.columns if c not in ['file','class','condition','seg_idx']]].values",
        "y_all = pivot['class'].map(lambda c: CLASSES.index(c)).values",
        "cond_all = pivot['condition'].values",
        "",
        "# train on {10,20,30}, test on 5",
        "tr = cond_all != 5; te = cond_all == 5",
        "sc = StandardScaler(); X_tr = sc.fit_transform(X_all[tr]); X_te = sc.transform(X_all[te])",
        "clf = xgb.XGBClassifier(n_estimators=300, max_depth=6, learning_rate=0.1,",
        "    objective='multi:softprob', num_class=6, eval_metric='mlogloss',",
        "    tree_method='hist', verbosity=0, n_jobs=-1, random_state=0)",
        "clf.fit(X_tr, y_all[tr]); pred = clf.predict(X_te)",
        "cm_arr = cm(y_all[te], pred, labels=list(range(6)))",
        "",
        "fig, ax = plt.subplots(figsize=(7, 6))",
        "im = ax.imshow(cm_arr, cmap='Blues')",
        "ax.set_xticks(range(6)); ax.set_yticks(range(6))",
        "ax.set_xticklabels(CLASSES); ax.set_yticklabels(CLASSES)",
        "ax.set_xlabel('Predicted'); ax.set_ylabel('True')",
        "for i in range(6):",
        "    for j in range(6):",
        "        ax.text(j, i, cm_arr[i, j], ha='center', va='center',",
        "                color='white' if cm_arr[i, j] > cm_arr.max()/2 else 'black', fontsize=9)",
        "ax.set_title(f'XGBoost LOCO — train={{10,20,30}}Hz, test=5Hz  (acc={accuracy_score(y_all[te], pred):.3f})')",
        "plt.colorbar(im, ax=ax)",
        "plt.tight_layout(); plt.savefig(FIG_DIR / 'cm_xgb_loco_test5Hz.png'); plt.show()",
    )
)

# ============================================================
# 18. Next steps
# ============================================================
cells.append(
    md(
        "## 18. Next steps",
        "",
        "Notebook tiếp theo (`02_dg_baselines.ipynb`):",
        "1. Order tracking layer (differentiable resampler) cho deep DG",
        "2. Cross-modal attention (vib ↔ ac) thay cho concat",
        "3. DANN domain adversarial",
        "4. MixStyle augmentation",
        "5. Concept Bottleneck — features từ Section 11 làm interpretable middle layer",
        "",
        "Tham khảo `TECHNICAL_REPORT.md` cho roadmap đầy đủ.",
    )
)

# ============================================================
# Build notebook
# ============================================================
nb = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.10"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}
for i, c in enumerate(cells):
    c["id"] = f"cell-{i:03d}"

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1)

print(f"Wrote {OUT}  ({len(cells)} cells)")
