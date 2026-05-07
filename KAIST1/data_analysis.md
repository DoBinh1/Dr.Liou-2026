# Initial Analysis Report — KAIST1 (NOVIC+ Motor Compound Fault) Dataset

**Date:** 2026-05-07
**Author:** ai@aladintech.co (HUST – Dr. Liou Lab, Multi-modal PHM research)
**Data directory:** `d:\[Lab] HUST\Dr Liou - Multi modal\KAIST1\`

**Attached deliverables:**
- Python scripts: [analyze_kaist1.py](analyze_kaist1.py), [analyze_bearing_freqs.py](analyze_bearing_freqs.py), [analyze_envelope.py](analyze_envelope.py)
- Interactive notebook: [KAIST1_visualize.ipynb](KAIST1_visualize.ipynb)
- All figures: [analysis_outputs/](analysis_outputs/)
- Statistics summary (JSON): [analysis_outputs/summary.json](analysis_outputs/summary.json)
- Original paper: [paper.txt](paper.txt) (2505.24001v4.pdf)

---

## 1. Background & 3-part Zenodo structure

The dataset's full name is **NOVIC+ Motor Compound Fault Dataset**, released alongside the paper *“Multi-output Classification using a Cross-talk Architecture for Compound Fault Diagnosis of Motors in Partially Labeled Condition”* (Wonjun Yi et al., KAIST, arXiv 2505.24001v4). The test rig itself is described in detail in reference [34] — Wonho Jung et al., *“Vibration, acoustic, temperature, and motor current dataset of rotating machine under varying operating conditions for fault diagnosis”*, **Data in Brief 48 (2023) 109049**.

The authors split the dataset into 3 Zenodo records (confirmed via the public descriptions):

| Part | Zenodo ID | Total size | Contents |
|---:|---|---:|---|
| **Part 1** | [15743425](https://zenodo.org/records/15743425) | 28.0 GB | `train_data_4s_clf_subsetA.npy` + 4 `test_data_4s_clf_subset{A,B,C,E}.npy` files + **all label files `*_npy_name_4s_clf_subset*.npy`** |
| **Part 2** | [15743009](https://zenodo.org/records/15743009) | 47.6 GB | `train_data_4s_clf_subset{B,C}.npy` + `valid_data_4s_clf_subset{A,B,C,E}.npy` |
| **Part 3** | [15743374](https://zenodo.org/records/15743374) | 5.9 GB | `train_data_4s_clf_subsetE.npy` |

> **Download status** (compared with the 3 zips in your folder):
> - `15743009.zip` ≈ 47 GB → **fully downloaded**, the `.npy` files have already been extracted (by you or someone before) → these are the 6 `.npy` files in the folder.
> - `15743425.zip` 1.67 GB → **does not match** the 28 GB expected for Part 1 → the download is **incomplete or truncated** (Python `zipfile` reports "File is not a zip file" because the central directory is missing).
> - `15743374.zip` 374 MB → **does not match** the 5.9 GB of Part 3 → also a broken download.
>
> In short: you have **Part 2 fully** in extracted form. Part 1 (which contains the labels!) and Part 3 still need to be re-downloaded.

### Test-rig setup (per paper §5.1)
- 3-phase induction motor, SIEMENS, 3 HP, 4-pole; chain: **motor → torque meter → gearbox (gear ratio 2.07) → bearing housing A → rotor → bearing housing B → hysteresis brake (AHB-3A)**.
- Measurement bearing: **NSK 6205** (n = 9 balls, ball diameter d = 7.90 mm, pitch diameter D = 38.5 mm, contact angle α = 0).
- Sampling: **fs = 25.6 kHz**, 4-second segments → 102 400 samples/segment, units = g (= 9.8 m/s²).
- 4 fault components: IRF (2 levels) × ORF (2 levels) × Misalignment (3 levels) × Unbalance (3 levels) = **36 combinations**.

### 4 operating-condition subsets (per paper §5.1 + Zenodo)

| Subset | RPM pattern | Torque load | Role |
|---|---|---|---|
| **A** | Sinusoidal, base 3000 RPM, period 10 s | Random current to hysteresis brake | Source/target in DA |
| **B** | Triangular, base 4000 RPM, period 5 s | 0 (no-load) | Source/target in DA |
| **C** | 5 constant RPM levels: 1800, 2100, 2400, 2700, 3000 | 0 (no-load) | Source/target in DA |
| **E** | **Mix of all conditions above** (A+B+C) | Mixed | Generalisation evaluation |

Subset E is described on Zenodo as: *“Dataset composed of all operation conditions written above”* — this subset does not appear in the paper but is part of the official dataset (presumably added in v4 for generalisation evaluation).

---

## 2. 9-channel structure — CONFIRMED by Zenodo

Every `.npy` file has shape `(N, 102 400, 9)` float64. **The 9 channels have been officially documented by Zenodo:**

| Index | Sensor | Unit | Notes |
|---:|---|---|---|
| 0 | Vibration **Bearing A — perpendicular to ground** | g | |
| 1 | Vibration **Bearing A — parallel to ground** | g | |
| 2 | Vibration **Bearing B — perpendicular to ground** | g | |
| 3 | Vibration **Bearing B — parallel to ground** | g | |
| 4 | **Temperature Bearing housing A** | °C | Very slowly varying |
| 5 | **Temperature Bearing housing B** | °C | |
| 6 | **Torque load** | (device unit) | A: random; B,C: ≈ 0; E: mixed |
| 7 | **Shaft RPM after gearbox** (rotor side, **slower**) | RPM | Bearings rotate at this frequency |
| 8 | **Shaft RPM before gearbox** (motor side, **faster**) | RPM | `ch8/ch7 = 2.054 ± 0.010 ≈ 2.07` (gear ratio) |

> Important correction vs. my earlier guess: the 4 vibration channels are not 4 independent accelerometers but rather **2 locations (Bearing A, Bearing B) × 2 directions (perpendicular, parallel)**. This is highly meaningful for orientation-aware analysis — perpendicular (transverse) is best for capturing BPFO/IRF since it lies in the load zone, while parallel (axial) is best for misalignment.

### 2.1 Label encoding (OFFICIAL, per Zenodo)
Original file paths on the test rig follow the format:

```
subsetA/anomaly/inner02_outer02_misalign0_unbalance10034/13_49.npy
```

Decoded:
- `subsetA` → operating-condition subset
- `anomaly` (vs. `normal`) → faulty
- `inner02` → IRF severity **0.2 mm**
- `outer02` → ORF severity **0.2 mm**
- `misalign0` → no misalignment (0 mm)
- `unbalance10034` → unbalance **10.034 g**
- `13_49.npy` → segment index 49 of recording 13

These paths are stored in companion files `*_npy_name_4s_clf_subset*.npy` (in the same order as `*_data_*.npy`). **The label files live entirely in Part 1** — you do not have it yet, so all of my analysis below is **unsupervised**.

---

## 3. Current state of the `.npy` files (what you actually have)

| File | Size | Shape | Samples | Train/Valid |
|---|---:|---|---:|---|
| `valid_data_4s_clf_subsetA.npy` | 2.477 GB | (336, 102 400, 9) | 336 | valid |
| `valid_data_4s_clf_subsetB.npy` | 2.477 GB | (336, 102 400, 9) | 336 | valid |
| `valid_data_4s_clf_subsetC.npy` | 2.455 GB | (333, 102 400, 9) | 333 | valid |
| `valid_data_4s_clf_subsetE.npy` | 0.737 GB | (100, 102 400, 9) | 100 | valid |
| `train_data_4s_clf_subsetB.npy` | 19.83 GB | (2 690, 102 400, 9) | 2 690 | train |
| `train_data_4s_clf_subsetC.npy` | 19.66 GB | (2 667, 102 400, 9) | 2 667 | train |
| **Missing**: `train_data_4s_clf_subsetA.npy` (Part 1) | – | – | – | train |
| **Missing**: `train_data_4s_clf_subsetE.npy` (Part 3) | – | – | – | train |
| **Missing**: 8 `*_npy_name_*` files (Part 1) | – | – | – | labels |
| **Missing**: 4 `test_data_*` files (Part 1) | – | – | – | test |

→ You currently have roughly **35 % of the full dataset's samples** — enough for qualitative analysis but not enough to train and evaluate the full 6 DA scenarios from the paper.

---

## 4. Per-channel summary statistics (over 30 random samples per subset)

| Subset | std Vib BA-perp | std Vib BB-para | Range Temp BA (°C) | Mean Torque | Range motor RPM (per sample) |
|---|---:|---:|---|---:|---|
| A | 0.565 | 0.981 | 28.7 – 35.9 | −3.05 (random) | 1 482 – 2 552 |
| B | 0.806 | 1.351 | 29.7 – 39.2 | −0.65 | 2 503 – 2 789 (near-constant) |
| C | 0.645 | 1.222 | 31.9 – 39.5 | −0.47 | 1 860 – 3 111 (5 discrete levels) |
| E | 0.670 | 1.183 | 28.6 – 38.4 | −0.76 | 1 498 – 3 111 (mixed) |

Observations:
- Vibration amplitude: **B > C ≈ E > A** on every channel — consistent with B running at the highest mean RPM (≈ 2 600).
- Temperature: A → E → C → B = 32.8 → 34.6 → 35.0 → 34.9 °C; the >6 °C span makes **temperature a meaningful domain-drift source** that can be exploited for multimodal fusion.
- The torque load splits cleanly into 3 clusters: A (random, mean ≈ −3) and B/C/E (near zero).
- All measurements taken with `mmap_mode='r'`, peak RAM < 4 GB.

---

## 5. PSD & STFT — fundamental spectral analysis (paper preprocessing)

Figures [03_stft_*.png](analysis_outputs/) apply **the exact preprocessing used by the paper**: STFT with window 4096, hop 2048, frequency range cropped to 20–520 Hz, dB scale.

NSK 6205 bearing characteristic frequencies (reference for reading the PSD):

| Frequency | Ratio to f_r | Example: subset C, sample 0 (f_r = 20.13 Hz) |
|---|---:|---:|
| FTF (cage) | 0.3974 | 8.0 Hz |
| BSF (ball spin) | 2.3341 | 47.0 Hz |
| BPFO (outer race) | 3.5766 | **72.0 Hz** |
| BPFI (inner race) | 5.4234 | **109.2 Hz** |

Figure [09_bearing_freqs_subsetC.png](analysis_outputs/09_bearing_freqs_subsetC.png) annotates these lines on the raw PSD — clear peaks at 1×fr and 2×fr appear, with a noticeable rise around 2×BPFO.

---

## 6. **Envelope analysis (Hilbert demodulation) — newly added**

This is the gold-standard technique for bearing-fault diagnosis: repeated impacts from a bearing defect get **amplitude-modulated onto a high-frequency structural-resonance band**. They cannot be seen directly on the raw PSD, but they emerge clearly after demodulation.

### 6.1 Procedure (Randall & Antoni 2011, ref [18] in the paper)
1. **Mini-kurtogram** — scan 8 high-frequency bandpass candidates (1–12.5 kHz) and pick the one whose envelope has the highest **excess kurtosis** (`scipy.stats.kurtosis(env, fisher=True)`). Bands below 1 kHz are deliberately excluded because shaft / gear harmonics dominate there (very tonal, high kurtosis but unrelated to bearing impacts).
2. **Bandpass + Hilbert** — Butterworth, 4th order, zero-phase (`sosfiltfilt`) → `env = |hilbert(y)|` → DC-removed.
3. **Envelope FFT** with a Hann window → look for peaks at `1×fr, 2×fr, FTF, BSF, BPFO, BPFI` and their harmonics.

Code: [analyze_envelope.py](analyze_envelope.py); interactive cells in notebook §9.

### 6.2 Results across the 4 subsets (sample 0, ch0 = Bearing A perpendicular)

| Subset | Best band (Hz) | Excess kurtosis | Top-3 alternatives |
|---|---|---:|---|
| valid_subsetA | 8000–10500 | **14.39** | 6000–8000 (4.08); 4000–6000 (3.17) |
| valid_subsetB | 4000–6000 | 6.02 | 3000–7000 (2.28); 6000–8000 (2.24) |
| valid_subsetC | 10500–12500 | 6.67 | 3000–7000 (6.25); 4000–6000 (5.08) |
| **valid_subsetE** | **3000–7000** | **21.94** | 4000–6000 (15.51); 8000–10500 (12.59) |

→ The subset E sample 0 has envelope kurtosis = 22, **abnormally high** → this sample very likely contains a **bearing fault**. This is exactly how envelope analysis can be used to *unsupervised pre-screen* faulty samples without any labels.

### 6.3 Generated figures

| File | Content |
|---|---|
| [10_envelope_<subset>_ch0_sample0.png](analysis_outputs/) | 3-panel: raw / bandpass+envelope / envelope spectrum (annotated with 1×fr, FTF, BSF, BPFO×3, BPFI×2) |
| [11_kurtogram_<subset>_ch0_sample0.png](analysis_outputs/) | Bar chart of envelope kurtosis for the 8 candidate bands |
| [12_envelope_compare_subsets_ch0.png](analysis_outputs/12_envelope_compare_subsets_ch0.png) | Overlay of envelope spectra across all 4 subsets (band 1.5–5 kHz) |
| [13_envelope_grid_valid_subsetC_ch0.png](analysis_outputs/13_envelope_grid_valid_subsetC_ch0.png) | Grid of 9 subset-C samples — envelope patterns differ visibly across fault combinations |
| [13_envelope_grid_valid_subsetC_ch2.png](analysis_outputs/13_envelope_grid_valid_subsetC_ch2.png) | Same grid for ch2 = Bearing B perpendicular |

### 6.4 Key findings from envelope analysis
1. **The subset-C grid reveals natural clustering**: some samples (0, 41, 207, 332) have an almost smooth envelope → likely *normal* or pure misalignment / unbalance (rotor faults that do not generate impacts). Others (124, 166, 290) have rich peak structure → strong IRF/ORF content.
2. **Perpendicular channels (ch0, ch2)** consistently produce higher kurtogram scores than parallel channels (ch1, ch3) — consistent with theory: BPFO/BPFI fault energy is strongest in the load zone, perpendicular to the shaft. When training a deep model, **keep all 4 channels** rather than collapsing to one.
3. **When RPM varies (subsets A, E)** the BPFO/BPFI lines slide along the frequency axis → *order tracking* (resampling with respect to angle rather than time) becomes necessary before reliable envelope analysis. This is a notable angle for proposing something different from the paper: the paper uses FLN to compensate, but we could use direct order tracking.

---

## 7. Overall dataset assessment for the multimodal research direction

**Strengths**
1. **fs = 25.6 kHz**, ≈ 12.5 kHz Nyquist — wide enough to cover every bearing fault frequency and many resonance bands.
2. **Truly multimodal with 9 native channels**: 4 vibration (2 locations × 2 directions) + 2 temperature + torque + 2 RPM. Compared with the other 3 datasets you've collected (HUSTmotor / COMFAULDA / Qatar), this is unusually rich — temperature, torque, and RPM are all synchronously recorded, making it ideal for *multi-modal PHM* under Dr. Liou.
3. **36 compound fault classes** + 4 domains (A/B/C/E) → richer than most public benchmarks.
4. Data already pre-segmented at 4 s, ready to be plugged into an ML pipeline.

**Limitations / open questions**
1. **Part 1 (containing the labels) is missing** → all supervised analysis is blocked until `*_npy_name_*` is available. Recommendation: re-download `15743425.zip` and `15743374.zip` using `wget --continue` or the Zenodo Python client (`pip install zenodo_get`) and verify the checksums.
2. **dtype = float64** doubles RAM usage unnecessarily. For training, cast to float32 and store as chunked HDF5/Zarr.
3. **Unclear whether Part 1 also contains `valid_npy_name_*`** — needs to be verified once downloaded.
4. **`train_subsetA` and `train_subsetE` are missing** → none of the 6 paper DA scenarios can be run end-to-end yet.

---

## 8. Suggested next steps

### Short term (before training)
1. **Re-download Part 1 and Part 3** from Zenodo (`zenodo_get 10.5281/zenodo.15743425` and `15743374`); verify md5 against the Zenodo checksums.
2. Once `*_npy_name_*.npy` is available: write a loader that builds a label CSV `(sample_idx, subset, IRF, ORF, Misalign, Unbalance)` for train/valid/test.
3. Re-export to **float32 chunked HDF5** (saves 50 % storage and RAM, enables faster random-access than mmap when sampling segments).
4. Add a notebook cell for **unsupervised clustering of envelope features** (PCA / UMAP on peak amplitudes at BPFO/BPFI/1×fr/...) — this can *infer pseudo-labels* for the 6 unlabelled `.npy` files.

### Medium term (research direction vs. MUGTN)
1. **Propose a cross-modal architecture**: use RPM (ch7/ch8) as a **conditioning vector** for normalisation (replace FLN with RPM-conditional FiLM), Temp (ch4/ch5) as a **global context**, and Torque (ch6) as a **drift-aware modulation**. KAIST1 already provides all 4 modalities, so this is a clear differentiator from MUGTN (vibration-only on HUSTmotor).
2. **Order-tracking pipeline** (using ch7 directly) as a preprocessing step → fully exploit the raw RPM signal. Yi et al. *do not* use the RPM channel and rely on FLN to compensate indirectly; we could show that simple order tracking is sufficient.
3. **Cross-dataset fusion with HUSTmotor / COMFAULDA**: all three are motor + bearing + multimodal → propose *cross-dataset transfer* to demonstrate generality.
4. **Envelope as auxiliary head**: add a head that predicts the envelope-domain BPFO/BPFI peak amplitudes as an auxiliary task — forcing the encoder to learn a representation that respects the physics.

### Long term
- Build a **unified data-loader library** for the 4 collected datasets (HUSTmotor, COMFAULDA, Qatar 3-phase IM, KAIST1) for consistent benchmarking — a prerequisite for the thesis / TST paper.

---

## 9. How to reproduce

```powershell
cd "d:\[Lab] HUST\Dr Liou - Multi modal\KAIST1"

# Statistics + waveform + PSD + STFT + RPM + correlation (figs 01-08)
python analyze_kaist1.py

# Bearing fault frequencies annotated on PSD (fig 09)
python analyze_bearing_freqs.py

# Envelope analysis with mini-kurtogram (figs 10-13)
python analyze_envelope.py

# Or open the interactive notebook
# code KAIST1_visualize.ipynb
```

All `.npy` files are opened with `mmap_mode='r'`, so peak RAM only grows when the indexed data is actually touched — safe for a 16 GB machine.
