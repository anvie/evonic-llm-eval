# ClaimGuard LLM Evaluation — Setup Report

> Evaluasi kemampuan model LLM untuk pipeline ClaimGuard AI ICD Auto-Coding.
> Dibuat: 2026-04-13

---

## Latar Belakang

ClaimGuard AI adalah pre-submission validator klaim BPJS yang mengkode resume medis ke ICD-10 secara otomatis. Pipeline terdiri dari 3 step:

1. **Step 1 — Translate & Enrich**: Ekstraksi dan pengayaan istilah klinis dari resume medis Bahasa Indonesia ke English medical keywords
2. **Step 2 — Hybrid Multi-Path Retrieval**: Pencarian kandidat ICD-10 via BGE-M3, BM25, dan Clinical_ModernBERT
3. **Step 3 — LLM Final Judge**: Reasoning klinis untuk memilih kode ICD-10 final

Evaluasi ini fokus pada **Step 1** — menguji apakah model lokal 26B bisa menggantikan Claude API.

---

## Domain yang Dibuat

### 3 Domain Baru

| Domain ID | Nama | Bahasa | Levels | Total Tests |
|-----------|------|--------|--------|-------------|
| `clinical_translate` | Clinical Translate & Enrich | ID → EN | L1–L5 | 12 |
| `icd_coding` | ICD-10 Coding | EN | L1–L5 | 9 |
| `lab_interpretation` | Lab Interpretation | EN | L1–L5 | 9 |

### 3 Custom Hybrid Evaluators

| Evaluator ID | Dimensi Penilaian | Pass Threshold |
|---|---|---|
| `clinical_keyword_judge` | Completeness 40% + Clinical Accuracy 40% + Abbreviation Handling 20% | 70/100 |
| `icd_code_judge` | Code Accuracy 50% + Completeness 30% + Specificity 20% | 70/100 |
| `lab_interpretation_judge` | Clinical Accuracy 40% + Completeness 30% + Clinical Reasoning 30% | 70/100 |

Semua evaluator bertipe **hybrid**: mengirim `eval_prompt` ke LLM judge, lalu mengekstrak `WEIGHTED_SCORE` via regex.

---

## Sumber Data

### Handcrafted Cases
7 kasus klinis Indonesian yang dirancang manual untuk domain `clinical_translate` (L1–L3):

| Test | Level | Kondisi |
|------|-------|---------|
| Pneumonia komuniti | L1 | 1 diagnosa |
| Appendisitis akut | L1 | 1 diagnosa |
| Fraktur femur | L1 | 1 diagnosa |
| DM tipe 2 + Hipertensi | L2 | 2 diagnosa |
| Stroke iskemik akut | L2 | 2 diagnosa |
| CKD stage 5 on HD | L3 | 4 diagnosa, abbreviasi berat |
| Sepsis multiorgan | L3 | 6 diagnosa, 14+ abbreviasi |

### MIMIC-IV Demo Dataset
Dataset deidentifikasi dari Beth Israel Deaconess Medical Center (100 pasien).
Lokasi: `data-mimic-iv/physionet.org/files/mimic-iv-demo/2.2/`
Lisensi: ODbL (Open Database License)

| hadm_id | Pasien | # Dx | Use Case | Domain |
|---------|--------|------|----------|--------|
| 26321862 | M/43 | 2 | Abses hepar + Streptococcus | CT L1, ICD L1 |
| 25561728 | M/67 | 3 | Respiratory + Palpitasi + HT | ICD L2 |
| 22585261 | M/44 | 4 | Ulkus duodenum + Anemia | CT L2, ICD L2, Lab L1 |
| 26048429 | M/64 | 4 | Ca esofagus + Barrett's | CT L3, ICD L3, Lab L4 |
| 28324362 | M/28 | 4 | Mitral valve + Pneumothorax iatrogenik | ICD L3 |
| 29757856 | M/60 | 39 | Komplikasi bariatrik + CLL | ICD L4 |
| 22205327 | F/50 | 39 | Saddle PE + MOF + Psikiatri | CT L4, ICD L5, Lab L2 |
| 22987108 | M/69 ✝ | 39 | Sirosis + Sepsis E.coli + meninggal | CT L5, ICD L5, Lab L3/L5 |

---

## Struktur File

```
test_definitions/
├── evaluators/
│   ├── clinical_keyword_judge.json       ← NEW
│   ├── icd_code_judge.json               ← NEW
│   └── lab_interpretation_judge.json     ← NEW
│
├── clinical_translate/
│   ├── domain.json
│   ├── level_1/  (4 tests: pneumonia, appendisitis, fraktur_femur, liver_abscess)
│   ├── level_2/  (level.json + 3 tests: dm_hipertensi, stroke_iskemik, gi_bleed)
│   ├── level_3/  (level.json + 3 tests: ckd_on_hd, sepsis_multiorgan, esophageal_cancer)
│   ├── level_4/  (level.json + 1 test: saddle_pe)
│   └── level_5/  (level.json + 1 test: cirrhosis_sepsis)
│
├── icd_coding/
│   ├── domain.json
│   ├── level_1/  (2 tests: pneumonia_simple, liver_abscess)
│   ├── level_2/  (level.json + 2 tests: respiratory_palpitations, gi_bleed)
│   ├── level_3/  (level.json + 2 tests: esophageal_cancer, mitral_valve)
│   ├── level_4/  (level.json + 1 test: bariatric_complications)
│   └── level_5/  (level.json + 2 tests: saddle_pe_full, cirrhosis_coding)
│
└── lab_interpretation/
    ├── domain.json
    ├── level_1/  (2 tests: simple_anemia, basic_glucose)
    ├── level_2/  (level.json + 2 tests: liver_panel, renal_panel)
    ├── level_3/  (level.json + 2 tests: renal_electrolytes, coagulation_panel)
    ├── level_4/  (level.json + 2 tests: abg_interpretation, mixed_acid_base)
    └── level_5/  (level.json + 1 test: icu_full_panel)
```

---

## Detail Domain

### 1. `clinical_translate` — Clinical Translate & Enrich

**Task**: Terima resume medis Bahasa Indonesia → ekstrak dan terjemahkan ke English clinical keywords (JSON).

**Output format yang diharapkan**:
```json
{
  "diagnoses": ["diagnosis 1", "diagnosis 2"],
  "clinical_findings": ["finding 1"],
  "abbreviations_expanded": {"GGK": "chronic kidney disease"},
  "lab_results": ["result 1"],
  "risk_factors": ["factor 1"]
}
```

**Progression per level**:

| Level | Kompleksitas | Jumlah Dx | Challenge Utama |
|-------|-------------|-----------|-----------------|
| L1 | Easy | 1–2 dx | Basic ID→EN translation |
| L2 | Medium | 2–4 dx | Multiple diagnoses, common abbreviasi (DM, HT) |
| L3 | Hard | 4–6 dx | Heavy abbreviasi load (14+ singkatan), etiologi |
| L4 | Very Hard | 39 dx | Multi-organ + psikiatri, komorbid tersembunyi di labs |
| L5 | Extreme | 39 dx | Kasus terminal, seluruh cascade komplikasi |

**Level system prompt appends**:
- L2: Ingatkan multiple diagnosa harus di-capture terpisah
- L3: Ingatkan etiologi, komplikasi metabolik, semua abbreviasi
- L4: Ingatkan diagnosa tersembunyi di nilai lab
- L5: Ingatkan komplikasi terminal dan komorbid latar

---

### 2. `icd_coding` — ICD-10 Coding

**Task**: Beri informasi klinis → prediksi kode ICD-10-CM yang benar.

**Output format yang diharapkan**:
```json
{
  "codes": [
    {"code": "K75.0", "description": "Abscess of liver", "type": "PRIMARY"},
    {"code": "B95.5", "description": "Unspecified streptococcus...", "type": "SECONDARY"}
  ]
}
```

**Progression per level**:

| Level | Jumlah Kode | Challenge Utama |
|-------|-------------|-----------------|
| L1 | 1–2 kode | Kode tunggal atau etiology pairing sederhana |
| L2 | 3–4 kode | Multi-sistem, manifestation codes |
| L3 | 4 kode | Sequencing oncology, procedural complication |
| L4 | 10+ kode | Post-surgical + comorbidities, combination codes |
| L5 | 10+ kode | Sepsis sequencing rules (A41+R65.2), organ failure cascade |

**Kunci coding rules yang diuji**:
- Etiology/manifestation pairing (e.g., K75.0 + B95.5)
- Sepsis sequencing: A41.x sebagai principal dx + R65.21 sebagai secondary
- Combination codes (e.g., E11.22 = DM2 with CKD)
- Z codes untuk status conditions
- Postprocedural complications (J95.811)

---

### 3. `lab_interpretation` — Lab Interpretation

**Task**: Terima hasil lab dengan reference ranges → interpretasi klinis.

**Output format yang diharapkan**:
```json
{
  "abnormal_values": [
    {"test": "Hemoglobin", "value": "7.2 g/dL", "reference": "12-16", "direction": "LOW", "severity": "CRITICAL", "significance": "..."}
  ],
  "interpretation": "Overall clinical interpretation",
  "pattern_recognition": "Identified patterns across panels",
  "differential_considerations": ["Condition 1", "Condition 2"]
}
```

**Progression per level**:

| Level | Panel Type | Challenge Utama |
|-------|-----------|-----------------|
| L1 | Single panel | Identifikasi dan interpretasi abnormalitas tunggal |
| L2 | Related panel | Pattern recognition (anemia, liver, renal) |
| L3 | Multi-system | Korelasi lintas organ, cascade patofisiologi |
| L4 | ABG / mixed | Stepwise acid-base analysis, compensatory mechanisms |
| L5 | Full ICU | 163 lab types, MODS assessment, prognostic implications |

**Kasus khusus yang diuji**:
- Ischemic hepatitis pattern (AST/ALT >8000x ULN dari shock)
- DIC pattern (low fibrinogen + high D-dimer + thrombocytopenia + schistocytes)
- Mixed acid-base disorder (pH tampak normal tapi ada 2 primary disorders)
- Hepatorenal syndrome (urine SG 1.047 + Cr tinggi + oliguria)
- MODS scoring dalam decompensated cirrhosis

---

## Cara Menjalankan Evaluasi

### Via Web UI

```
http://localhost:8080
```

Pilih domain dari daftar, kemudian klik "Start Evaluation".

### Via Headless CLI

```bash
# Semua domain sekaligus
python3 run_headless.py --endpoint http://localhost:8080/v1 --model default

# Domain spesifik
python3 run_headless.py --endpoint http://localhost:8080/v1 --model default --domain clinical_translate
python3 run_headless.py --endpoint http://localhost:8080/v1 --model default --domain icd_coding
python3 run_headless.py --endpoint http://localhost:8080/v1 --model default --domain lab_interpretation
```

### Baseline Comparison (Model 26B vs Claude API)

**Run 1: Model 26B lokal**
```env
LLM_BASE_URL=http://localhost:8080/v1
LLM_MODEL=model-26b
```

**Run 2: Claude via OpenRouter (baseline)**
```env
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_API_KEY=your-key
LLM_MODEL=anthropic/claude-3.5-haiku
```

Target: model 26B harus mencapai minimal **80% dari skor Claude API** untuk lulus.

---

## Cara Evaluator Bekerja

Semua 3 evaluator berjenis **hybrid** (lihat `evaluator/custom_evaluator.py`):

1. Engine mengirim response model + expected ke `eval_prompt` (dengan placeholder `{response}` dan `{expected}`)
2. LLM judge mengembalikan skor dalam format terstruktur
3. Regex `WEIGHTED_SCORE:\s*(\d+(?:\.\d+)?)` mengekstrak nilai numerik 0–100
4. Score > 1.0 auto-dinormalisasi ke 0–1 (dibagi 100)
5. Pass jika skor ≥ 70

**Contoh output LLM judge** (`clinical_keyword_judge`):
```
COMPLETENESS: 4
ACCURACY: 5
ABBREVIATION: 5
WEIGHTED_SCORE: 92.0
REASONING: Semua diagnosa utama tercapture. Terjemahan terminologi medis akurat.
Semua abbreviasi medis Indonesia ter-expand dengan benar.
```

---

## Catatan Implementasi

- **No code changes**: Semua implementasi via JSON files saja
- **Extra fields** (`icd_target`, `difficulty`, `source`) disimpan sebagai metadata, tidak mempengaruhi evaluasi
- **Timeout**: L1–L3 = 60000ms, L4–L5 = 120000ms
- **MIMIC data**: Prompt untuk MIMIC cases dibuat dari data terstruktur (diagnoses, labs, prescriptions); tidak ada free-text clinical notes di demo dataset
- **ICD versioning**: MIMIC hadm 26321862–28324362 menggunakan ICD-9; converted ke ICD-10-CM equivalent untuk expected values di domain `icd_coding`

---

## Rencana Downstream Evaluation (Opsional)

Setelah model 26B lolos evaluasi keyword, langkah berikutnya adalah **downstream eval**:

1. Buat tool `icd_retrieval_check` di `backend/tools/`
2. Tool menerima output JSON dari Step 1
3. Memanggil Step 2 retrieval API (BGE-M3 + BM25)
4. Mengecek apakah `icd_target` ada di top-10 hasil retrieval
5. Return hit/miss

Field `icd_target` sudah tersimpan di semua test definitions untuk keperluan ini.
