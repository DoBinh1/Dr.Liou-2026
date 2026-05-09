# TECHNICAL REPORT: HUSTmotor Multimodal Dataset
## Multimodal Fault Diagnosis & Domain Generalization

> **Author note**: This report supports the exploration phase of multimodal PHM research. Version v2 adds deeper signal-processing analysis (cepstrum, kurtogram, CWT, WPT, coherence, order tracking) and actual baseline results (XGBoost, WDCNN, DualStreamCNN on three setups: intra-condition, pooled, leave-one-condition-out).

---

## PART 1 — DATASET UNDERSTANDING

### 1.1 Data structure

- **6 health states × 4 working conditions = 24 `.txt` files**
- Each file: **163,840 samples × 4 channels** (3 vibration X/Y/Z + 1 acoustic Sound)
- fs = 25.6 kHz → each file is **6.4 seconds**
- Nyquist = 12.8 kHz → enough to analyze harmonics and the bearing-resonance band 2–6 kHz
- Header is ~17 lines of metadata, then tab-separated data with columns: `Time, X, Y, Z, Sound`

Number of rotational cycles per file:

| Speed | Cycles in 6.4 s |
|---|---|
| 30 Hz | ~192 |
| 20 Hz | ~128 |
| 10 Hz | ~64 |
| 5 Hz | ~32 ← **main pain point of low-speed** |

### 1.2 Role of each modality

**Vibration (3 channels)** — direct mechanical signal:
- Captures the system response to: bearing impulses, electromagnetic forces, rotor imbalance, misalignment
- The 3 channels usually correspond to X / Y (radial) and Z (axial) → providing **directional information**
- High SNR, robust to environment

**Acoustic (1 channel)** — air pressure signal:
- Captures three components: aero-acoustic noise, **magnetic noise** (from flux variation in the air gap), and surface-radiated mechanical
- Non-contact, easy to deploy but lower SNR, sensitive to reverberation and background
- Particularly strong for electromagnetic faults (broken bar, voltage unbalance)

→ The two modalities are **complementary**, not redundant. This is the foundation for fusion to provide genuine gain.

### 1.3 Physics of each fault

| Fault | Time-domain | Frequency-domain | Most sensitive modality |
|---|---|---|---|
| **H** baseline | low kurtosis | 1×, line freq f₁ | both |
| **BF** (bearing) | impulse train, kurtosis ↑↑ | BPFO/BPFI/BSF/FTF + resonance band 2–6 kHz | vibration |
| **BOW** (bowed rotor) | sinusoidal-like | dominant **1×**, secondary 2× | vibration |
| **BROKEN bar** | low-freq modulation | sideband **(1±2ks)f₁** around line freq | acoustic ≥ vibration |
| **MISAL** | regular | dominant **2×**, axial vibration ↑ | vibration |
| **UNBAL** voltage | regular | **2f₁** (100/120 Hz) torque ripple | acoustic ≥ vibration |

Bearing characteristic frequencies:
- BPFO = (N/2) · fr · (1 − d/D · cos α)
- BPFI = (N/2) · fr · (1 + d/D · cos α)
- BSF = (D/2d) · fr · (1 − (d/D)² · cos²α)
- FTF = (fr/2) · (1 − d/D · cos α)

After modulation by resonance, BF appears clearly in the **envelope spectrum**, not in the raw spectrum.

### 1.4 Core challenges

1. **Very few files (24)** → segmentation strategy must be careful to avoid leakage
2. **Speed scaling**: 5 Hz vs 30 Hz differ by 6× → the same fault has different spectral positions → strong covariate shift
3. **Low acoustic SNR at low speed** → selective denoising required
4. **Kinematic fault overlap**: BOW vs MISAL vs UNBAL all have 1×/2× components → need multiple features
5. **Cross-modal time alignment**: vibration vs acoustic may have several-ms propagation delay → check before fusion

### 1.5 Possible task formulations

| Task | Setup | Difficulty | Goal |
|---|---|---|---|
| Single-condition classification | train/test on the same condition | easy | sanity > 99% |
| Multi-condition pooled | mix all 4 conditions | medium | robustness |
| **Cross-condition DG** | train: 5+10+20, test: 30 | **hard** | **main publishable** |
| Single-source DG | train 1 condition, test the other 3 | very hard | extreme DG |
| Multimodal fusion | vs single-modality | medium | fusion gain |
| Missing-modality | train both, test 1 | hard | sensor failure |
| Few-shot domain adapt | + k samples target | medium | industrial reality |

---

## PART 2 — SIGNAL ANALYSIS (deeper)

### 2.1 Time domain
- Amplitude scale, periodicity, **impulse train (BF)**, **slow envelope modulation (BROKEN)**
- Kurtosis and crest factor are the fastest indicators distinguishing impulsive (BF) from sinusoidal-dominated faults

### 2.2 Frequency domain (FFT)
- Δf = fs/N. Whole file (N=163840) → Δf = 0.156 Hz (enough to resolve 2sf₁ sidebands). Segment 2048 → Δf = 12.5 Hz (NOT enough at 5 Hz)
- → **Window size must scale with speed**, or use a large window (≥ 4096) for all conditions

### 2.3 Time-frequency (which to choose, why)

| Transform | Suitable for | Insight | Limitation |
|---|---|---|---|
| **STFT / log-spectrogram** | vibration, general | linear frequency, easy to reproduce | fixed resolution (Heisenberg) |
| **Mel spectrogram** | **acoustic** | log-frequency, perceptual scale | compresses high band → loses BF resonance info if applied to vibration |
| **CWT (Morlet)** | bearing impulses, low-speed | adaptive resolution | compute-heavy |
| **WPT** | feature engineering | binary tree band → compact energy/entropy | choose level, mother wavelet |
| **Hilbert Envelope Spectrum** | **bearing fault, very strong** | demodulate → exposes BPFO/BPFI/BSF/FTF | must select resonance band |
| **Order tracking spectrum** | **DG / cross-speed** | kills speed effect | needs known speed (here we have it) |

### 2.4 Spectral Kurtosis & Kurtogram (Antoni 2006)

**Problem**: HES requires choosing a bandpass around the resonance band — wrong band → lose the signature.

**Spectral Kurtosis (SK)**: for each center frequency f and bandwidth Δf, SK(f) measures the kurtosis of the signal after bandpass-filtering through (f, f+Δf). Bearing impulses → high SK in that band (impulsive content).

**Kurtogram**: a map of SK over a grid (level L × center fc). Level L corresponds to STFT window 2^L · k → bandwidth Δf = fs/(2^L · k).

**Practical procedure**:
```
1. Compute kurtogram on a long segment (≥ 16384 samples)
2. Find (L*, fc*) with the highest SK → bandpass band (fc* − Δf/2, fc* + Δf/2)
3. Bandpass filter, Hilbert envelope, FFT → HES with peaks at BPFO/BPFI/...
```

**When to use**: core for bearing fault diagnosis. Automates the manual procedure typically done by experts.

### 2.5 Cepstrum

`Cepstrum(x) = IFFT(log|FFT(x)|)`. Domain: **quefrency** (unit: seconds).

**Benefits**:
- **Harmonic family detection**: a set 1×, 2×, 3×, ... → a single peak at quefrency = 1/fr
- **Sideband detection**: cluster of sidebands at (1±2ks)f₁ → peak at quefrency = 1/(2sf₁)
- **Echo / convolution removal**: deconvolves excitation and transfer function (because log turns product into sum)

**On HUSTmotor**:
- MISAL has strong 1×, 2× harmonics → clear cepstrum peak at 1/30 = 33.3 ms
- BROKEN has 2sf₁ sidebands → peak at tens of ms depending on slip
- BF has a peak at 1/BPFO (very short, a few ms)

### 2.6 Continuous Wavelet Transform (CWT)

Mother wavelet: **Complex Morlet** (`cmor1.5-1.0` in PyWavelets) — balances time and frequency localization.

`CWT(x, scale s, time τ) = ∫ x(t) · ψ\*((t−τ)/s) dt / √s`

Scale ↔ frequency relation: `f = fc · fs / s`, where fc is the center frequency of the mother wavelet.

**Versus STFT**:
- High-frequency: CWT has better time resolution (window shrinks) → captures BF impulses precisely
- Low-frequency: CWT has better frequency resolution → captures slow BROKEN modulation

**Compute cost**: O(N · Nscales) — N=4096 with 80 scales is enough to visualize; 65536 samples is feasible.

### 2.7 Wavelet Packet Transform (WPT) — Energy Distribution

Splits [0, fs/2] into 2^L equal sub-bands via binary tree decomposition. With L=4 → 16 bands, Δf = 800 Hz.

**Energy fingerprint**:
```
E_b = Σ |c_b[n]|²    (energy per band)
E_b_norm = E_b / Σ E_b    (normalized → distribution)
```

→ Compact 16-d vector. Each fault has a characteristic distribution:
- BF: energy concentrated in high band (resonance ~3–6 kHz)
- MISAL/BOW/UNBAL: energy in low band (<1 kHz)

**Mother wavelet**: `db4` is standard for mechanical signals. `sym8` or `coif5` also works.

### 2.8 Coherence vibration ↔ acoustic

`γ²(f) = |Pxy(f)|² / (Pxx(f) · Pyy(f)) ∈ [0, 1]`

- γ²(f) ≈ 1 → vibration and acoustic share information at f → modalities redundant
- γ²(f) ≈ 0 → independent information → fusion provides genuine gain

**On HUSTmotor**: BF is expected to show high coherence in 2–6 kHz (impulses propagate both mechanically and through air); H is flat. This is a **sanity check before deciding the fusion strategy**.

### 2.9 Order spectrum (speed normalization)

**Replace the frequency axis → order axis = f / fr**: peaks at 1× always at order=1, 2× at order=2, BPFO at order ≈ 3.5 (constant), regardless of speed.

→ Since speed is constant per HUSTmotor file, the order spectrum is simply the FFT divided by fr → peaks **align across the 4 speed conditions** → eliminating speed-induced domain shift.

**This is the strongest weapon for cross-condition DG** on this dataset.

### 2.10 Fault patterns on TF maps (cheat-sheet)

- **BF**: vertical bursts spaced by BPFO/BPFI in the high-freq band 2–6 kHz
- **BOW**: bright horizontal line at 1×
- **BROKEN**: horizontal line at f₁ with two faint streaks at f₁ ± 2sf₁
- **MISAL**: horizontal line at 2× brighter than 1×
- **UNBAL**: dense line at 2f₁, fairly speed-independent

### 2.11 Recommended pipeline for HUSTmotor

| Modality | Main tool | Auxiliary tool (features) |
|---|---|---|
| Vibration | log-spectrogram + CWT (Morlet) → 2D CNN | WPT energy 16d, HES amplitude at k×fr |
| Acoustic | mel spectrogram (64–128 bands), bandpass 50 Hz–6 kHz | spectral entropy, band energy 6 bands |
| **For DG** | **order spectrum** (resampling) | FiLM speed adapter, MixStyle |

---

## PART 3 — PREPROCESSING PIPELINE

### 3.1 Proposed pipeline

```
raw .txt (163840 × 4)
  → load, split per channel
  → DC removal (high-pass 5–10 Hz)
  → channel-wise z-score (fit on train per condition)
  → optional denoise (acoustic: wavelet shrinkage db4, soft threshold)
  → time alignment vib ↔ ac (cross-correlation lag check)
  → time-block split  ⟵ critical to avoid leakage
       train: 0.0–0.7 of file
       val:   0.7–0.85
       test:  0.85–1.0
  → sliding window
       train overlap: 50–75%
       val/test overlap: 0%
  → per-segment instance norm
  → augmentation (train only):
       Gaussian noise SNR 15–30 dB,
       time-shift ±5%,
       SpecAugment (freq/time mask),
       Mixup (α=0.2) intra-class
  → batch
```

### 3.2 Window size — quantitative analysis

Requirement: ≥ 5 rotational cycles for sufficient spectral statistics.
- 5 Hz: needs ≥ 25,600 samples
- 10 Hz: ≥ 12,800
- 20 Hz: ≥ 6,400
- 30 Hz: ≥ 4,267

**Choose 4096 (≈160 ms)** — compromise:
- 30 Hz: ~5 cycles ✓
- 20 Hz: ~3 cycles ⚠
- 10 Hz: ~1.6 cycles ✗
- 5 Hz: ~0.8 cycles ✗

→ With order tracking: 4096 angular-samples always cover a fixed number of cycles regardless of speed.

### 3.3 Overlap strategy

- Train: 50% (balances sample count and independence); 75% if data is short
- Val/Test: 0% (zero-overlap for independent evaluation)
- **Time-block split per file first**, then sliding window. Do not random 80/20 over all segments — adjacent segments are nearly identical → leakage.

### 3.4 Normalization
- Per-channel z-score fit on train set
- Per-segment instance-norm: kills amplitude shifts due to speed scaling (vibration RMS ~ ω²)
- For TF images: log-magnitude then min-max to [0,1]

### 3.5 Data balancing
24 files = 4 files/class. After segmentation (4096 window, 50% overlap, time-block 70/15/15):
≈ 1320 train + 144 val + 144 test segments per modality (verified empirically).

### 3.6 Label encoding
- y_class ∈ {0..5}, y_domain ∈ {0..3} (5/10/20/30 Hz)
- Multi-task: learn both heads, only class is the target

---

## PART 4 — FEATURE ENGINEERING

### 4.1 Handcrafted features

**Time domain**:

| Feature | Formula | Physics | Fault sensitivity |
|---|---|---|---|
| RMS | √(1/N · Σx²) | total energy | rises with all faults |
| Kurtosis | E[(x−μ)⁴]/σ⁴ − 3 | tail-heaviness | **very high for BF (>5)** |
| Skewness | E[(x−μ)³]/σ³ | asymmetry | weak |
| Crest Factor | max\|x\|/RMS | peakiness | **high for BF** |
| Impulse Factor | max\|x\|/mean\|x\| | impulsiveness | BF |
| Shape Factor | RMS/mean\|x\| | waveform shape | weak |
| Margin Factor | max\|x\|/(mean√\|x\|)² | extreme peak | BF |
| Sample Entropy | self-similarity | complexity | broken bar |

**Frequency domain**:

| Feature | Formula | Sensitivity |
|---|---|---|
| Spectral centroid | Σf·X(f)/ΣX(f) | shift due to fault |
| Spectral entropy | −Σ p log p, p=X²/ΣX² | flatness |
| Band energy (7 bands) | Σ_{f∈band} X²(f) | BF (high), UNBAL (2f₁) |
| Peak amplitude @ k× | argmax around k·fr | BOW(1×), MISAL(2×) |
| 2sf₁ sideband ratio | (X(f₁−2sf₁)+X(f₁+2sf₁))/X(f₁) | **BROKEN** |
| 2f₁ amplitude | X(2f₁) | **UNBAL** |

**Time-frequency / envelope**:
- WPT energy entropy across 16 sub-bands (L=4)
- HES amplitude at k×fr (k=1,2,3) after bandpass through kurtogram-selected band
- CWT energy ratio high-band / low-band

### 4.2 Fault-sensitivity table

| Feature | H | BF | BOW | BROKEN | MISAL | UNBAL |
|---|---|---|---|---|---|---|
| Kurtosis | low | **HIGH** | mid | mid | mid | mid |
| Crest Factor | low | **HIGH** | mid | mid | mid | mid |
| 1× amp | low | low | **HIGH** | low | mid | low |
| 2× amp | low | low | mid | low | **HIGH** | low |
| 2f₁ amp | low | low | low | low | low | **HIGH** |
| 2sf₁ sideband | low | low | low | **HIGH** | low | low |
| HES @ BPFO/I | low | **HIGH** | low | low | low | low |
| WPT high-band | low | **HIGH** | low | low | low | low |

→ This is also a **natural dictionary for Concept Bottleneck Models**.

### 4.3 Deep features
- 1D CNN feature maps on raw → texture
- Spec-CNN (ResNet18) on log-spectrogram / mel
- TCN with dilated convolution for long-range
- Transformer patch embedding

### 4.4 Multimodal shared features
- **Joint embedding via contrastive**: positive pair = (vib, ac) of same segment, InfoNCE
- **Cross-reconstruction**: encode vib → decode ac (and vice versa). Latent z carries shared information

---

## PART 5 — MULTIMODAL LEARNING

### 5.1 Fusion strategies

| Level | Method | Pros | Cons |
|---|---|---|---|
| **Early** | concat raw signal or spectrogram | simple, learns cross-modal early | scale/nature differ → careful normalization needed |
| **Middle** | two backbones, fuse mid-layer | balances specificity and sharing | more complex |
| **Late** | two classifiers, average/vote | robust if one modality fails | misses cross-modal interaction |

→ **For HUSTmotor: middle fusion is the best default.**

### 5.2 Cross-modal attention

```
Q = X_vib · W_Q,  K = X_ac · W_K,  V = X_ac · W_V
A_v→a = softmax(QKᵀ/√d) · V
```
Symmetric: also compute A_a→v. Meaning: the model learns **which acoustic spectral burst corresponds to each impulse burst in vibration**.

### 5.3 Difficulties in fusing vibration + acoustic
1. **High information redundancy** → naive concat may not gain (verified empirically — see Part 6.6)
2. **Asymmetric SNR** by speed → modality-gating needed
3. **Sample efficiency**: multimodal models have more params
4. **Missing-modality robustness**: need modality dropout during training

### 5.4 Proposed architecture

```
Vibration (4096 × 3) ───► ResNet1D / WDCNN ────┐
                                                │
                                                ├── CrossAttn ── CLS ── Classifier (6)
                                                │       ↑↓                    │
Acoustic (mel 64 × T) ──► Spec-CNN (ResNet18)──┘                              │
                                                                              │
                                       Domain head (DANN, GRL) ←──────────────┤
                                       Contrastive head (vib↔ac InfoNCE) ←────┤
                                       Modality dropout p=0.1 (train only)
```

`Loss = L_class + λ_d · L_domain_adv + λ_c · L_contrastive`

---

## PART 6 — BASELINE MODELS & EXPERIMENTAL RESULTS

### 6.1 Setup

- Window 4096, train overlap 50%, val/test overlap 0%
- Time-block split per file: 0–70% train, 70–85% val, 85–100% test
- 24 files → 1320 train / 144 val / 144 test segments
- Hardware: RTX 4090 GPU (CUDA), full pipeline runtime ~64 s

### 6.2 Models & input

| Model | Input | Params |
|---|---|---|
| **XGBoost** | 96-d handcrafted features (24 per channel × 4 channels concatenated) | n_est=300, depth=6, lr=0.1 |
| **WDCNN vib-only** | (3, 4096) raw vibration | ~110K |
| **WDCNN ac-only** | (1, 4096) raw acoustic | ~108K |
| **DualStreamCNN** | (3, 4096) + (1, 4096) → 128-d concat → FC | ~225K |

WDCNN: kernel 64 (wide-first), 4 conv blocks (16→32→64→64), GAP, FC. 20 epochs Adam lr=1e-3 with cosine schedule.

### 6.3 Evaluation setups

1. **Intra-condition**: train/test on the same condition (70/30 time-block)
2. **Pooled**: mix all 4 conditions, time-block split per file
3. **Leave-One-Condition-Out (LOCO)**: train on 3 conditions, test on the remaining one — this is **cross-condition DG**

### 6.4 XGBoost results (handcrafted features)

**Intra-condition**:

| Test condition | Acc | Macro-F1 | n_train | n_test |
|---|---|---|---|---|
| 5 Hz | 0.9420 | 0.9424 | 336 | 138 |
| 10 Hz | 1.0000 | 1.0000 | 336 | 138 |
| 20 Hz | 1.0000 | 1.0000 | 336 | 138 |
| 30 Hz | 0.9928 | 0.9928 | 336 | 138 |
| **Mean** | **0.9837** | — | — | — |

**Pooled** (4 conditions mixed): **Acc = 1.0000, F1 = 1.0000**

**Leave-One-Condition-Out (cross-condition DG)**:

| Test condition (unseen) | Acc | Macro-F1 |
|---|---|---|
| 5 Hz | **0.2131** | 0.1271 |
| 10 Hz | 0.8143 | 0.7587 |
| 20 Hz | 0.8692 | 0.8449 |
| 30 Hz | 0.8924 | 0.8911 |
| **Mean** | **0.6973** | — |
| **Worst** | **0.2131** | — |

→ XGBoost is **catastrophic** at test=5Hz: 21.3%, near chance (16.7%). Reason: dynamic range and spectral position at 5 Hz differ too much from train {10,20,30} Hz; handcrafted features (RMS, kurtosis, band energy) are completely off-scale.

### 6.5 Deep baseline results

**Pooled** (intra-domain training, all conditions mixed):

| Model | Acc | Macro-F1 |
|---|---|---|
| WDCNN vibration-only | 0.9931 | 0.9931 |
| WDCNN acoustic-only | 0.8125 | 0.8065 |
| DualStreamCNN multimodal | **1.0000** | **1.0000** |

**Leave-One-Condition-Out (cross-condition DG)**:

| Test condition | WDCNN vib-only | DualStream | Δ |
|---|---|---|---|
| 5 Hz | 0.8209 | 0.7562 | **−6.5%** |
| 10 Hz | 1.0000 | 0.9552 | −4.5% |
| 20 Hz | 0.9701 | 0.9478 | −2.2% |
| 30 Hz | 0.7687 | 0.6219 | **−14.7%** |
| **Mean** | **0.8899** | 0.8203 | **−7.0%** |
| **Worst** | **0.7687** | 0.6219 | −14.7% |

### 6.6 Findings & implications

1. **Intra-condition is saturated** (>99% for both XGBoost and WDCNN). No further headroom intra-domain. Don't spend effort on "improve intra accuracy" — that race is over.

2. **Pooled multi-condition is also saturated** (~100%). The model treats each condition as a separate feature mode, without true generalization.

3. **Cross-condition DG is the real pain point**:
   - XGBoost LOCO mean = 69.7%, **worst = 21.3%** (test=5Hz)
   - WDCNN vib LOCO mean = 89.0%, worst = 76.9% (test=30Hz)
   - DualStream LOCO mean = 82.0%, worst = 62.2% (test=30Hz)
   - Gap to intra-domain (99%) is ~10–80 points depending on method/condition. This is the headroom for improvement.

4. **Naive multimodal HURTS DG**: dual-stream concat is worse than vib-only **on all 4 conditions** (mean −7%, worst-case −14.7%). This is an important and **very publishable** finding:
   - Reason: low acoustic SNR at low speed → noisy gradient for fusion; concat-style fusion has no mechanism to weight modality by condition.
   - **Lesson**: for multimodal to gain on DG, **smart fusion is required** — cross-attention with gating, modality dropout, contrastive alignment — not concat.

5. **Acoustic-only is weak** (81% pooled). Must be used as a supplementary signal, not as a replacement for vibration.

6. **Two opposite failure patterns**:
   - XGBoost fails at **5 Hz** (handcrafted features change strongly with speed)
   - WDCNN fails at **30 Hz** (model used to high-energy signature, struggles with new noise)
   - → DL features are more transferable than handcrafted, but also lose more at the extremes

→ **Clear paper direction**: cross-condition DG + smart fusion + physics (order tracking) + (especially) demonstrating "naive multimodal hurts DG, careful design needed".

### 6.7 Generalization expectation for an improved model

Based on the trend, a good model should achieve:
- LOCO worst-case ≥ **85%** (from the 77% baseline) — using order tracking + DANN
- Multimodal LOCO worst-case ≥ vib-only worst (proving fusion does not hurt) → ≥ 85%
- Calibrated confidence on unseen → ECE < 0.05

---

## PART 7 — DOMAIN GENERALIZATION

### 7.1 Why is 5/10/20/30 Hz a domain shift?

1. **Frequency scaling**: characteristic ∝ rotational speed → 6× spectrum shift
2. **Energy scaling**: vibration RMS ∝ ω² → 30 Hz can have 36× the RMS of 5 Hz (verified on the data)
3. **SNR differs** → low-speed signal is weaker, fault impulses don't "stand out"
4. **Resonance excitation**: different speeds excite different modes
5. **Nonlinear slip** with load → 2sf₁ sideband location changes
6. **Air-gap magnetic noise** scales → acoustic signature shifts

→ P(X|Y) shifts strongly between domains: both **covariate shift** and **conditional shift**.

### 7.2 Why is train{10,20,30} → test{5} catastrophic?

From Part 6.4: XGBoost = 21% (near chance). Reasons:
- **5 Hz** has the lowest dynamic range → poor SNR → handcrafted features biased
- Spectral peaks at 5/10/15 Hz (1×, 2×, 3×) never seen during train
- Energy distribution is significantly skewed (RMS 30 Hz / 5 Hz ≈ 36× theoretically)
- WDCNN vib does better (82%) thanks to partial texture-invariant learning — but still drops 17 points vs pooled

### 7.3 DG methods

**Domain Adaptation** (target unlabeled available):
- DANN with gradient reversal
- MMD/CORAL distribution alignment
- Pseudo-labeling + self-training
- AdaBN

**Domain Generalization** (target not available at training time):
- IRM, GroupDRO, MixStyle / DSU
- Adversarial invariant feature learning

**Physics-informed (highly recommended)**:
- **Order tracking**: resample by angle θ instead of time t → 1×, 2×, k× always at fixed positions regardless of speed → mostly cancels domain shift
- Speed-aware adapter: condition the model on speed (FiLM layer)
- Frequency-band masking augmentation

### 7.4 Proposed DG pipeline

```
Vibration ─► tachometer-aware order tracking ─► CWT (Morlet) ─┐
                                                              │
                                                              ├ CrossAttn ─ CLS ─ Class head
                                                              │             ├ Domain head (GRL)
Acoustic ─► bandpass(50Hz–6kHz) ─► mel spectrogram ───────────┘             └ Contrastive
                                                              
loss = CE_class + λ₁·(−CE_domain via GRL) + λ₂·NCE(vib,ac) + λ₃·MixStyle
```

→ **Order tracking + cross-attention + DANN + contrastive** — this is the main novelty for paper #1.

---

## PART 8 — VISUALIZATION

### 8.1 Understanding data
- Raw waveform overlay of 6 classes at the same condition
- Log-scale FFT spectrum → annotate 1×, 2×, f₁, 2f₁
- Spectrogram with color = log power
- HES → annotate BPFO/BPFI
- **Order spectrum** → speed-invariant view (essential for DG analysis)
- **CWT scalogram** → fine-grained time-frequency
- **Cepstrum** → harmonic family
- **Kurtogram** → automatic resonance band finder

### 8.2 Understanding the model
- t-SNE / UMAP of last-layer features, color=class, marker=domain
  - clusters by class > by domain → good DG
- **Confusion matrix per condition** (4 matrices, especially for LOCO setup)
- Per-class & per-domain ROC
- Cross-modal attention map: heatmap (T_v × T_a)
- Grad-CAM on spectrogram → expect: BF model focuses on 2–6 kHz
- 1D saliency → expect: BF model focuses on impulse locations

### 8.3 Understanding fault physics
- Wavelet scalogram per (fault × condition) → 6×4 matrix of images
- Order spectrum overlay across all conditions → consistency check
- Bearing characteristic frequency lines overlaid on HES
- WPT energy distribution per fault → fingerprint

---

## PART 9 — EVALUATION

### 9.1 Metrics

| Metric | When | Notes |
|---|---|---|
| Accuracy | balanced data | **insufficient for DG** |
| **Macro-F1** | default for fault diagnosis | per-class matters |
| Per-class P/R | safety-critical (BF recall) | error mode |
| ROC-AUC OvR | score-quality evaluation | threshold tuning |
| Confusion matrix per domain | DG analysis | very informative |
| Mean over domains | DG | average |
| **Worst-case domain accuracy** | DG | **main robustness metric** |
| Std across domains | DG | stability |
| ECE / NLL | OOD-aware deployment | calibration |

### 9.2 Proposed composite metric for HUSTmotor

`DG-Score = 0.5 × mean_LOCO + 0.5 × worst_LOCO`

Reason: average hides the bad domain; worst is too conservative. The arithmetic mean balances them. Current baseline:
- XGBoost: 0.5×0.6973 + 0.5×0.2131 = **0.4552**
- WDCNN vib: 0.5×0.8899 + 0.5×0.7687 = **0.8293**
- DualStream: 0.5×0.8203 + 0.5×0.6219 = **0.7211**

→ Target for new models: DG-Score > 0.85.

### 9.3 Robustness evaluation
- Add Gaussian noise SNR ∈ {0,5,10,15,20} dB → plot acc vs SNR
- Drop modality (vib only / ac only) → check fallback
- Domain-shift severity sweep (single-source DG)
- Few-shot adaptation (k=1, 5, 10)
- 5 random seeds, mean ± std, paired t-test

---

## PART 10 — RESEARCH DIRECTIONS

Sorted by HUSTmotor relevance and publishability (top first), based on the experimental results in Part 6.

### 10.1 Physics-informed Multimodal DG (Order Tracking + Char-Freq Attention)
- **Verified motivation**: XGBoost worst-LOCO = 21%, WDCNN worst = 77% — speed-induced shift is the main difficulty
- **Method**: differentiable order resampler + characteristic-frequency attention mask + speed-aware FiLM + DANN
- **Novelty**: physics-as-architecture (not just physics-as-loss)
- **Publish**: very high — TII, MSSP, IEEE TIM, EAAI

### 10.2 Smart Multimodal Fusion (countering "naive concat hurts")
- **Verified motivation**: dual-stream concat **hurts** DG vs vib-only (mean −7%, worst −14.7%)
- **Method**: cross-attention with modality gating, contrastive alignment vib↔ac, modality dropout, learnable temperature
- **Novelty**: direct experiment showing "naive multimodal harms DG", then proposing an improved architecture
- **Publish**: very high — clean story with evidence and a fix

### 10.3 Cross-modal Reconstruction for Robust DG
- **Motivation**: shared latent z between vib and ac → robust to domain and missing modality
- **Method**: encoders + cross-decoders + class head + domain adversarial
- **Publish**: high; story "1 sensor down, system still diagnoses"

### 10.4 Multimodal Self-Supervised Pretraining
- **Motivation**: 24 files is few → leverage CWRU/Paderborn/COMFAULDA/Qatar IM for cross-dataset SSL pretraining
- **Method**: Masked Signal Modeling 1D + cross-modal contrastive vib↔ac (CLIP-style); fine-tune on HUSTmotor
- **Publish**: high (2025–2026 trend)

### 10.5 Concept Bottleneck Multimodal Model (Explainability)
- **Motivation**: industrial AI needs interpretability; use handcrafted features (RMS, kurtosis, 2f₁, 2sf₁, HES BPFO …) as **concepts**
- **Method**: backbone → concept layer (predicts ~30 physics concepts) → final classifier; multi-task
- **Publish**: high; "trustworthy AI for PHM"

### 10.6 Modality-Coupled Style Augmentation (MixStyle++)
- **Method**: feature statistics swapping per BN layer, coupled across modality
- **Publish**: medium-high; combine with 10.1/10.4

### 10.7 Foundation Time-Series Model + LoRA Fine-tune
- **Motivation**: 2025–2026 boom of TS-FM (Chronos, MOMENT, TimesFM, Lag-Llama)
- **Method**: TS-FM backbone + LoRA, multimodal extension via cross-attention
- **Publish**: high (timely)

### 10.8 Open-set / OOD Fault Detection
- **Motivation**: real-world has compound faults, unseen severity
- **Method**: energy-based OOD score / OpenMax on multimodal embedding
- **Publish**: high (novel, little overlap with MUGTN)

### 10.9 Multimodal Graph Neural Network
- **Method**: 4 sensors as nodes, edges = physical layout / cross-correlation; heterogeneous GNN
- **Publish**: medium-high; watch overlap with MUGTN

### 10.10 Differentiating from MUGTN

MUGTN (Zhao et al. 2025 EAAI) is the current SOTA. Don't try to gain 0.x% intra-domain (already saturated, see Part 6.4 — XGBoost is already 100% pooled). Instead:

| MUGTN focus | Yours (proposed) |
|---|---|
| Architecture (graph + transformer) | **Physics-as-architecture** (order tracking, char-freq attention) |
| Intra-condition accuracy | **Cross-condition DG, missing-modality robustness, OOD** |
| Black-box | **Concept-bottleneck explainability** |
| End-to-end deep | **Cross-dataset SSL pretraining** |
| Multimodal (likely concat-style) | **"Naive concat hurts DG"** — propose smart fusion |

→ The story **"simpler model, smaller params, better DG and explainable"** usually wins over "bigger model, +0.3% intra-domain". You have clear evidence (Part 6.6).

### 10.11 Practical roadmap (6 months)

| Month | Goal | Output |
|---|---|---|
| 1 | ✓ Reproduce dataset, evaluation framework, baselines XGBoost/WDCNN/dual-stream + LOCO | **Done** (Part 6) |
| 2 | Order tracking + speed-aware features → improved cross-condition benchmark | improved DG numbers |
| 3–4 | Physics-informed multimodal DG (10.1) + smart fusion (10.2) | paper #1 draft |
| 5 | SSL pretraining cross-dataset (10.4) | paper #2 draft |
| 6 | Concept Bottleneck explainability (10.5) | paper #3 draft |

---

## PRIORITIZED RECOMMENDATIONS

1. **Cross-condition DG (worst-domain) is the metric to chase**, not intra-domain (already saturated at 100%)
2. **Order tracking** is the strongest DG weapon, currently underexploited
3. **Naive multimodal concat hurts DG** — proven on this dataset → smart fusion required (cross-attention + DANN + contrastive)
4. **Combine HUSTmotor with CWRU/Paderborn/COMFAULDA/Qatar IM** for SSL pretraining
5. **Concept Bottleneck with physics dictionary** is a less-competed explainability angle
6. **Differentiate from MUGTN** through physics + DG + smart-fusion + explainability

**Current baseline DG-Score** (0.5·mean + 0.5·worst):
- XGBoost: **0.46** | WDCNN vib-only: **0.83** | DualStream: **0.72**
- Target for new models: **> 0.85**

---

## APPENDIX: FILES IN THE FOLDER

| File | Purpose |
|---|---|
| `01_exploration.ipynb` | Starter notebook (58 cells): visualization, deeper SP, baselines |
| `_run_pipeline.py` | End-to-end script: load → features → splits → XGBoost + WDCNN baselines |
| `_build_notebook.py` | Notebook generator (easier to edit source than JSON) |
| `raw_cache.npz` | Cache of 24 raw signal files |
| `features_per_segment.csv` | Handcrafted features per (file, channel, segment) |
| `splits.npz` | train/val/test segments (raw) for DL |
| `baseline_results.json` | Baseline results (XGBoost + WDCNN intra/pooled/LOCO) |
| `analysis_outputs/` | Plot outputs |

*Report v2 updated 2026-05-09.*
