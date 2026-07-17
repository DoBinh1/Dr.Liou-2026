# Time-Domain Signal Analysis Report
## 10 Files × 3 Sensor Groups (Accelerometer · Current · Voltage)

> **Data Collection Specifications:**  
> $f_s$ = **50,000 Hz (50 kHz)** · Duration = **~20 seconds/file**  
> Units: Acceleration **(g)** · Current **(A)** · Voltage **(V)**  
>
> **General Observation:** All data files exhibit **two distinct phases**:
> - **Pre-start Idle Phase (~0–8 s):** The motor is not yet powered. All signals are flat (current = 0 A, voltage = 0 V, acceleration = static gravity of 1.0 g on the Z-axis).
> - **Running Phase (~8–20 s):** The motor starts and runs. A large inrush startup current (~2–3 A) occurs for 1–2 seconds, followed by steady-state operation.
>
> **Important Note:** When training diagnostic models, the pre-start idle phase (~0–8 s) and the startup transient (~8–10 s) should be cropped out. Only the **steady-state phase (~10–20 s)** should be used for feature extraction.

---

## FILE 1 — 🟢 Healthy · Normal Operation (No Load)

### 1. Accelerometer (x, y, Z)
* **Baseline State:** Healthy motor under no load.
* **Idle Period (0–8 s):** x and y are flat (~0 g); Z ≈ 1.0 g (static gravity).
* **Running Period (>8 s):** x oscillates ±0.03 g, y ±0.04 g, Z fluctuates between 0.95 and 1.05 g.
* **Observation:** The signals are stable with no abnormal impulses, indicating normal baseline operation.

![File 1 – Accelerometer](27216219/File%201_acc.png)

### 2. Current (I1, I2, I3)
* **Idle Period (0–8 s):** All three phases are 0 A.
* **Startup Transient (~8 s):** Inrush current peaks at ~2 A and decays exponentially within 1 s.
* **Running Period (>8 s):** Sinusoidal waves with small amplitude (~0.1 A peak) as the motor runs without mechanical load.
* **Observation:** The three phases are well-balanced with equal peak values.

![File 1 – Current](27216219/File%201_cur.png)

### 3. Voltage (V1, V2, V3)
* **Idle Period (0–8 s):** Voltage is 0 V.
* **Running Period (>8 s):** Balanced three-phase sinusoidal voltage at ±380 V peak, shifted by 120°.
* **Observation:** The voltage remains extremely stable throughout the running phase, indicating a clean power supply.

![File 1 – Voltage](27216219/File%201_voltage.png)

---

## FILE 2 — 🟢 Healthy · Phase Removal During Operation (No Load)

### 1. Accelerometer (x, y, Z)
* **Observation:** Vibration levels are identical to File 1 before the phase removal event. Once a phase is disconnected during operation, vibration amplitudes increase due to the unbalanced magnetic pull (UMP) causing rotating asymmetry.

![File 2 – Accelerometer](27216219/File%202_acc.png)

### 2. Current (I1, I2, I3)
* **Observation:** Normal startup at ~8 s. When one phase is disconnected during operation, the current in the disconnected phase drops to 0 A, while the remaining two phases experience a sharp increase in current to compensate for the load, showing severe asymmetry and waveform distortion.

![File 2 – Current](27216219/File%202_cur.png)

### 3. Voltage (V1, V2, V3)
* **Observation:** Shows the exact moment of the phase disconnection. The disconnected phase's voltage drops or distorts, while the other two phases maintain grid voltage.

![File 2 – Voltage](27216219/File%202_voltage.png)

---

## FILE 3 — 🟢 Healthy · 0.4 Nm Mechanical Load

### 1. Accelerometer (x, y, Z)
* **Observation:** Vibration amplitudes are slightly larger than File 1 due to the mechanical load: x oscillates ±0.05 g, y ±0.07 g. The signal remains stable and periodic, characteristic of a healthy motor under load.

![File 3 – Accelerometer](27216219/File%203_acc.png)

### 2. Current (I1, I2, I3)
* **Observation:** Startup transient is visible at ~8 s. The steady-state current is higher than File 1 (~0.44 A peak), reflecting the active mechanical torque. The phases remain balanced.

![File 3 – Current](27216219/File%203_cur.png)

### 3. Voltage (V1, V2, V3)
* **Observation:** Stable three-phase sinusoidal voltage at ±380 V peak, unaffected by the mechanical load.

![File 3 – Voltage](27216219/File%203_voltage.png)

---

## FILE 4 — 🟢 Healthy · 0.8 Nm Mechanical Load

### 1. Accelerometer (x, y, Z)
* **Observation:** Displays the largest vibration in the Healthy group: x ±0.06 g, y ±0.07 g. The amplitude increases proportionally with the load. The signal remains periodic and stable.

![File 4 – Accelerometer](27216219/File%204_acc.png)

### 2. Current (I1, I2, I3)
* **Observation:** Steady-state current peaks at ~0.7 A, which is the highest in the Healthy group. The startup transient peaks at ~2.5 A. Waveforms are sinusoidal and balanced.

![File 4 – Current](27216219/File%204_cur.png)

### 3. Voltage (V1, V2, V3)
* **Observation:** Unaffected by the heavy load, demonstrating a stiff grid supply.

![File 4 – Voltage](27216219/File%204_voltage.png)

---

## FILE 5 — 🟢 Healthy · One Phase Disconnected from Startup

### 1. Accelerometer (x, y, Z)
* **Observation:** Signals are flat (~0 g) before and after the startup command. Because one phase is missing from the start, the motor cannot generate a rotating magnetic field and fails to rotate, resulting in no mechanical vibration.

![File 5 – Accelerometer](27216219/File%205_acc.png)

### 2. Current (I1, I2, I3)
* **Observation:** No startup current inrush is observed. The disconnected phase carries 0 A, and the remaining two phases carry a very small, distorted current (~0.05 A). The motor stands still.

![File 5 – Current](27216219/File%205_cur.png)

### 3. Voltage (V1, V2, V3)
* **Observation:** Two phases show normal voltage, while the disconnected phase stays at ~0 V, confirming a pre-start open-circuit fault on phase B.

![File 5 – Voltage](27216219/File%205_voltage.png)

---

## FILE 6 — 🔴 Faulty · Normal Operation (No Load)

### 1. Accelerometer (x, y, Z)
* **Comparison with File 1 (Healthy No-Load):** The vibration amplitude is visibly larger: x oscillates ±0.05 g (compared to ±0.03 g in File 1), representing a ~68% increase. A dense high-frequency noise is present in the steady-state, which is an early mechanical signature of the rotor fault.

![File 6 – Accelerometer](27216219/File%206_acc.png)

### 2. Current (I1, I2, I3)
* **Observation:** Inrush transient occurs at ~8 s, but takes longer to settle compared to File 1. The steady-state current is slightly higher than File 1, and subtle amplitude modulations are visible—a characteristic signature of broken rotor bars (BRB).

![File 6 – Current](27216219/File%206_cur.png)

### 3. Voltage (V1, V2, V3)
* **Observation:** Identical to File 1, indicating that the rotor fault does not distort the grid voltage.

![File 6 – Voltage](27216219/File%206_voltage.png)

---

## FILE 7 — 🔴 Faulty · Phase Removal During Operation (No Load)

### 1. Accelerometer (x, y, Z)
* **Observation:** The combined effect of the rotor fault and phase removal produces significantly higher vibration levels than File 2 (Healthy phase removal). After the disconnection, the vibration becomes highly irregular and intense.

![File 7 – Accelerometer](27216219/File%207_acc.png)

### 2. Current (I1, I2, I3)
* **Observation:** The current amplitude is higher than in File 2. Phase asymmetry is more pronounced, and the waveforms show prominent high-frequency harmonic distortion after the phase removal event.

![File 7 – Current](27216219/File%207_cur.png)

### 3. Voltage (V1, V2, V3)
* **Observation:** Identical to File 2; clearly marks the phase disconnection event.

![File 7 – Voltage](27216219/File%207_voltage.png)

---

## FILE 8 — 🔴 Faulty · 0.4 Nm Mechanical Load

### 1. Accelerometer (x, y, Z)
* **Comparison with File 3 (Healthy 0.4 Nm):** Vibration is ~60% larger. The rotor fault modulates the vibration envelope at the slip frequency, creating a non-periodic, modulated waveform with dense high-frequency content.

![File 8 – Accelerometer](27216219/File%208_acc.png)

### 2. Current (I1, I2, I3)
* **Observation:** RMS current is ~47% higher than File 3. The rotor fault degrades efficiency, requiring more current to produce the same torque. Visible low-frequency beating (amplitude modulation) is present, which is the classic broken rotor bar signature.

![File 8 – Current](27216219/File%208_cur.png)

### 3. Voltage (V1, V2, V3)
* **Observation:** Normal balanced ±380 V grid voltage.

![File 8 – Voltage](27216219/File%208_voltage.png)

---

## FILE 9 — 🔴 Faulty · 0.8 Nm Mechanical Load

### 1. Accelerometer (x, y, Z)
* **Observation:** Exhibits the highest vibration level in the entire dataset: x ±0.07 g, y ±0.06 g (nearly 95% higher than File 4). The signal contains multiple overlapping frequency components, and the startup transient is prolonged.

![File 9 – Accelerometer](27216219/File%209_acc.png)

### 2. Current (I1, I2, I3)
* **Observation:** Peak steady-state current reaches ~1.0 A (compared to ~0.7 A in File 4). The startup inrush reaches ~3 A and takes 3–4 seconds to stabilize. Strong amplitude modulation is visible, showing that the broken rotor bar fault is highly aggravated under heavy loads.

![File 9 – Current](27216219/File%209_cur.png)

### 3. Voltage (V1, V2, V3)
* **Observation:** The voltage remains stable at ±380 V, proving that the high current and prolonged startup are caused by the motor fault rather than a voltage sag.

![File 9 – Voltage](27216219/File%209_voltage.png)

---

## FILE 10 — 🔴 Faulty · One Phase Disconnected from Startup

### 1. Accelerometer (x, y, Z)
* **Observation:** Similar to File 5, the vibration is mostly flat since the motor cannot rotate. However, tiny fluctuations are slightly larger than File 5 due to the broken rotor bars reacting to the single-phase field.

![File 10 – Accelerometer](27216219/File%2010_acc.png)

### 2. Current (I1, I2, I3)
* **Observation:** Phase B carries 0 A. The other two phases carry unbalanced currents. The asymmetry is more severe than File 5 due to the combined effect of the rotor fault and the disconnected phase. The motor stands still and acts as a pure inductive load.

![File 10 – Current](27216219/File%2010_cur.png)

### 3. Voltage (V1, V2, V3)
* **Observation:** Identical to File 5; confirms phase B is disconnected from startup.

![File 10 – Voltage](27216219/File%2010_voltage.png)

---

## Summary of Diagnostic Insights

### 1. Startup Transient and Pre-start Idle
All files contain a **pre-start idle phase (~0–8 s)**. The motor is only energized after 8 seconds. This is critical for data preprocessing:
* **Recommendation:** Crop the first 10 seconds of each file to discard the idle state and the startup inrush transient. Perform steady-state diagnostics on the ~10–20 s window.

### 2. Modality Sensitivity
* **Current Signature:** Extremely effective for load estimation (RMS) and broken rotor bar detection (amplitude modulation and sidebands).
* **Vibration Signature:** Highly sensitive to rotor imbalance and mechanical faults, especially under load (vibration increases by 60–95% under load when a fault is present).
* **Voltage Signature:** Primarily useful for identifying supply-side faults (phase disconnection) but carries little information about rotor health.

### 3. Healthy vs. Faulty Comparison Table (Steady-State)

| Case | Vibration Level (x_std) | Current Level (I1_rms) | Primary Diagnostic Marker |
|:---:|------------------------|------------------------|---------------------------|
| **F1 vs F6** (No Load) | Increases by ~68% | Almost identical | Vibration amplitude & high-frequency noise |
| **F2 vs F7** (Phase Rem.)| Increases significantly | Increases by ~61% | Post-event current asymmetry and distortion |
| **F3 vs F8** (0.4 Nm) | Increases by ~60% | Increases by ~47% | Current amplitude modulation & vibration slip frequency |
| **F4 vs F9** (0.8 Nm) | Increases by ~95% | Increases by ~38% | Intense current modulation & very high vibration levels |
| **F5 vs F10** (1-Ph Disc)| Low (no rotation) | Distortion present | Current asymmetry (phase B = 0 A) |
