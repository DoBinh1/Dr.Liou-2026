# HUSTmotor Multimodal Dataset — Exploration & Baselines

Analysis of the HUSTmotor dataset (Zhao et al.) for **Multimodal Fault Diagnosis & Domain Generalization** research under Dr. Liou (HUST, 2026).

Source dataset: https://github.com/CHAOZHAO-1/HUSTmotor-multi-modal-dataset
- 6 health states × 4 working conditions = 24 `.txt` files
- 4 channels: 3 vibration (X/Y/Z) + 1 acoustic; fs = 25.6 kHz; 163,840 samples/file (6.4 s)

---

## Files

| File | Purpose |
|---|---|
| `TECHNICAL_REPORT.md` | Full 10-part technical report — dataset, signal processing, preprocessing, features, multimodal, baselines + actual results, DG, evaluation, research directions |
| `01_exploration.ipynb` | 58-cell notebook: visualization + deeper signal processing + baseline visualization |
| `_run_pipeline.py` | End-to-end script: load → features → splits → baselines (XGBoost + WDCNN + DualStreamCNN) |
| `_build_notebook.py` | Notebook generator (easier to edit source than JSON) |
| `baseline_results.json` | Raw baseline results |
| `analysis_outputs/` | 15 plots (waveform, FFT, STFT, CWT, cepstrum, WPT, coherence, order spectrum, t-SNE, baseline summary, confusion matrix) |

---

## Baseline results (RTX 4090, ~64 s end-to-end)

### Setups
1. **Intra-condition** — train/test on the same condition, 70/30 time-block split
2. **Pooled** — mix all 4 conditions
3. **Leave-One-Condition-Out (LOCO)** — train on 3 conditions, test on 1 → cross-condition DG

### Summary table

| Setup | XGBoost | WDCNN vib | WDCNN ac | DualStream |
|---|---|---|---|---|
| Intra-condition (mean) | 98.4% | – | – | – |
| Pooled | **100.0%** | 99.3% | 81.3% | **100.0%** |
| LOCO mean | 69.7% | **89.0%** | – | 82.0% |
| LOCO **worst** | **21.3%** (5Hz) | **76.9%** (30Hz) | – | 62.2% (30Hz) |

**DG-Score** = 0.5·mean + 0.5·worst:
- XGBoost: **0.46** | WDCNN vib: **0.83** | DualStream: **0.72**
- Target for new models: **> 0.85**

### Six key findings

1. **Intra-domain is saturated** (>99%) — no point competing here
2. **Pooled is also saturated** (~100%) — model treats each condition as a separate mode
3. **Cross-condition DG is the real pain point** — gap of 10–80 points depending on method
4. **Naive multimodal HURTS DG** — DualStream concat is worse than vib-only on **all 4** conditions (mean −7%, worst −14.7%) → motivation for cross-attention + modality dropout + contrastive
5. **Acoustic-only is weak** (81%) — supplementary, not a replacement for vibration
6. **Two opposite failure patterns**: XGBoost fails at 5Hz (low SNR), WDCNN fails at 30Hz (model used to high-energy)

→ **Paper direction**: cross-condition DG + smart multimodal fusion + physics (order tracking) + demonstrating "naive multimodal hurts DG, careful design needed"

---

## How to reproduce

```powershell
# 1) Install (if missing)
pip install numpy scipy pandas matplotlib scikit-learn xgboost pywavelets torch

# 2) Edit ROOT path in _run_pipeline.py and _build_notebook.py
#    to match the raw data location on your machine (default points to
#    "D:/[Lab] HUST/Dr Liou - Multi modal/HUST motor multimodal dataset/Raw data")

# 3) Run pipeline to build cache + features + splits + baselines
python _run_pipeline.py

# 4) (Optional) Re-generate notebook
python _build_notebook.py

# 5) Open notebook for exploration
jupyter notebook 01_exploration.ipynb
```

The pipeline auto-caches:
- `raw_cache.npz` (~44 MB)
- `features_per_segment.csv` (~3.7 MB)
- `splits.npz` (~47 MB)

These artifacts are not committed (see `.gitignore`); they can be regenerated via `_run_pipeline.py`.

---

## Next steps

| Notebook | Goal |
|---|---|
| `02_dg_baselines.ipynb` (TBD) | Order tracking + DANN + cross-attention → beat baseline DG-Score 0.83 |
| `03_ssl_pretraining.ipynb` (TBD) | Cross-dataset SSL (CWRU/Paderborn/COMFAULDA/Qatar IM) + LoRA fine-tune |
| `04_concept_bottleneck.ipynb` (TBD) | Explainable multimodal with physics dictionary as middle layer |

See `TECHNICAL_REPORT.md` — Part 10 — for the full plan.

---

*Updated: 2026-05-09*
