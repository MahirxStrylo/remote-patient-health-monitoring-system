# Technical and Medical Limitations

This document explicitly defines the boundaries, technical constraints, and medical disclaimers of the Remote Patient Health Monitoring System.

---

## 1. Prototype & Regulatory Disclaimer

> [!CAUTION]
> **Educational & Research Prototype Only**:
> This software and hardware design is an academic university engineering prototype. It has **NOT** been evaluated, certified, or cleared by the US Food and Drug Administration (FDA), European Medicines Agency (EMA), CE Medical Devices Directive (MDD/MDR), or any national medical device regulatory body.
>
> **NOT FOR DIAGNOSTIC, TREATMENT, OR EMERGENCY USE**:
> The readings, metrics, visualizations, and automated outputs produced by this system must **NEVER** be used as a substitute for professional medical advice, clinical diagnosis, treatment planning, or life-critical patient monitoring.

---

## 2. Hardware & Electrical Limitations

### 2.1 Single-Lead vs. Diagnostic 12-Lead ECG
- **Single-Lead Limitation**: The AD8232 provides a single bipolar lead biopotential (typically Lead I or Lead II equivalent depending on electrode placement).
- A single-lead ECG can estimate heart rate and display basic rhythm disturbances (e.g. severe tachyarrhythmias, premature ventricular complexes), but **CANNOT** diagnose localized myocardial infarction (STEMI), ischemia, bundle branch blocks, or complex structural cardiopathies which require standard 12-lead vectorcardiography.

### 2.2 Electrical Safety & Galvanic Isolation
- The AD8232 connects conductive gel electrodes directly to patient skin.
- **Fatal Shock Hazard**: If the ESP32 is powered via USB from a mains-connected computer without an isolated power supply, leakage currents or ground faults can traverse through the electrodes across the patient's heart.
- Always operate patient-attached nodes on isolated battery power ($<5\text{V}$ DC) with proper dielectric isolation.

### 2.3 Motion Artifacts & Muscle Noise
- The AD8232 uses an analog bandpass filter ($0.5\text{ Hz}$ to $40\text{ Hz}$).
- Patient movement, deep respiration, or shivering causes significant baseline wander and electromyographic (EMG) noise that can distort the PQRST complex.

---

## 3. Cellular & Network Limitations (SIM800L / 2G)

### 3.1 2G Sunset
- While 2G remains active in many rural developing areas, major telecommunications carriers in North America, parts of Europe, and East Asia have decommissioned 2G networks.
- Verification of regional 2G (GSM 900/1800 or 850/1900 MHz) availability is mandatory before deploying SIM800L hardware.

### 3.2 Bandwidth & Latency
- GPRS maximum theoretical throughput is $\sim 40\text{--}80\text{ kbps}$ with variable round-trip latency ($500\text{ ms}$ to $3\text{,000 ms}$).
- Real-time continuous raw ECG streaming is impractical over 2G; data must be collected in discrete batches (e.g. 5–10 seconds) and uploaded periodically.

### 3.3 TLS Negotiation Constraints
- Early SIM800L baseband firmware does not support modern TLS 1.2 / TLS 1.3 cipher suites. An isolated ingestion gateway or private APN is required for public transport security.

---

## 4. Software & AI Boundaries

1. **No Automated Medical Diagnosis**:
   - The AI integration layer is explicitly architected as a non-diagnostic classification stub (`status="not_configured"`).
   - Any future AI model must be validated specifically on single-lead AD8232 datasets, must evaluate signal quality before inference, and must report an **Inconclusive / Unsupported Signal** outcome when quality is degraded.
2. **ADC Unit Integrity**:
   - The system displays raw signal in **ADC counts** ($0\text{--}4095$).
   - The platform strictly refuses to label raw ADC counts as millivolts ($\text{mV}$) without calibrated hardware calibration references.
