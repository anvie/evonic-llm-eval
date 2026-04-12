# ClaimGuard Step 1 — Evaluation Plan untuk evonic-llm-eval

> Dokumen ini berisi rancangan lengkap untuk menguji model LLM 26B pada Step 1 (Translate & Enrich) pipeline ClaimGuard AI ICD Auto-Coding menggunakan evonic-llm-eval.

---

## 1. Konteks

ClaimGuard AI adalah pre-submission validator klaim BPJS yang mengkode resume medis ke ICD-10 secara otomatis. Pipeline-nya terdiri dari 3 step:

- **Step 1 — Translate & Enrich**: Ekstraksi dan pengayaan istilah klinis dari resume medis Bahasa Indonesia ke English medical keywords
- **Step 2 — Hybrid Multi-Path Retrieval**: Pencarian kandidat kode ICD-10 menggunakan 3 path paralel (BGE-M3, BM25, Clinical_ModernBERT classifier)
- **Step 3 — LLM Final Judge**: Reasoning klinis untuk memilih kode ICD-10 final

Evaluasi ini fokus pada **Step 1** — menguji apakah model lokal 26B parameter bisa menggantikan Claude API untuk task translate & enrich.

---

## 2. Domain & Level Structure

### Buat domain baru: `clinical_translate`

```
test_definitions/
└── clinical_translate/
    ├── domain.json
    ├── level_1/           # Single diagnosis, istilah umum
    │   ├── pneumonia.json
    │   ├── appendisitis.json
    │   └── fraktur_femur.json
    ├── level_2/           # Multi-diagnosis sederhana (2 kondisi)
    │   ├── dm_hipertensi.json
    │   └── stroke_iskemik.json
    └── level_3/           # Kasus kompleks multi-komorbid
        ├── ckd_on_hd.json
        └── sepsis_multiorgan.json
```

### domain.json

```json
{
  "name": "clinical_translate",
  "display_name": "Clinical Translate & Enrich",
  "description": "Evaluasi kemampuan model mengekstrak dan menerjemahkan istilah klinis dari resume medis Bahasa Indonesia ke English medical keywords untuk keperluan ICD-10 coding.",
  "system_prompt": "Kamu adalah clinical NLP extractor. Tugasmu:\n1. Terima resume medis dalam Bahasa Indonesia\n2. Ekstrak SEMUA kondisi klinis, temuan pemeriksaan, dan diagnosa\n3. Terjemahkan ke terminologi medis Inggris yang standar (sesuai ICD-10)\n4. Kenali dan expand abbreviasi medis Indonesia (GGK, HT, DM, HD, Ur, Cr, dll)\n5. Enrich dengan istilah klinis yang lebih spesifik jika konteks mendukung\n\nOutput dalam format JSON:\n```json\n{\n  \"diagnoses\": [\"English diagnosis 1\", \"English diagnosis 2\"],\n  \"clinical_findings\": [\"finding 1\", \"finding 2\"],\n  \"abbreviations_expanded\": {\"GGK\": \"chronic kidney disease\", ...},\n  \"lab_results\": [\"result 1\", ...],\n  \"risk_factors\": [\"factor 1\", ...]\n}\n```\nPastikan SEMUA kondisi tercapture, jangan lewatkan diagnosa apapun.",
  "system_prompt_mode": "overwrite"
}
```

### Level system prompts (opsional, mode append)

Level 1 tidak perlu tambahan. Level 2 dan 3 bisa ditambah instruksi:

**Level 2** — append:
```
Perhatikan: resume ini mengandung MULTIPLE diagnosa. Pastikan semua diagnosa tercapture sebagai item terpisah di field "diagnoses".
```

**Level 3** — append:
```
Perhatikan: ini kasus kompleks dengan multiple komorbid. Perhatikan:
- Etiologi/penyebab dasar (mis: "GGK ec nefropati diabetik" → CKD + diabetic nephropathy)
- Komplikasi metabolik (hiperkalemia, hipoalbuminemia, dll)
- Semua abbreviasi harus di-expand
```

---

## 3. Test Definitions

### Level 1: Single Diagnosis

#### `pneumonia.json`

```json
{
  "name": "pneumonia_komuniti",
  "prompt": "Pasien laki-laki 58 tahun datang dengan keluhan sesak napas dan batuk berdahak kuning sejak 5 hari. Demam tinggi 39.2°C. Pemeriksaan fisik: ronkhi basah kasar pada paru kanan bawah. Foto thorax: infiltrat pada lobus kanan bawah. Diagnosa kerja: Pneumonia komuniti.",
  "expected": "{\"diagnoses\":[\"community-acquired pneumonia\"],\"clinical_findings\":[\"dyspnea\",\"productive cough\",\"purulent sputum\",\"fever 39.2°C\",\"coarse crackles right lower lobe\",\"chest X-ray infiltrate right lower lobe\"],\"abbreviations_expanded\":{},\"lab_results\":[],\"risk_factors\":[]}",
  "evaluator": "clinical_keyword_judge",
  "icd_target": ["J18.9"],
  "difficulty": "easy",
  "eval_checklist": [
    "sesak napas → dyspnea",
    "batuk berdahak kuning → productive cough + purulent sputum",
    "ronkhi basah kasar → coarse crackles",
    "lokasi anatomis ter-extract (right lower lobe)"
  ]
}
```

#### `appendisitis.json`

```json
{
  "name": "appendisitis_akut",
  "prompt": "Pasien perempuan 25 tahun datang dengan nyeri perut kanan bawah sejak 2 hari, awalnya di ulu hati lalu berpindah. Mual, muntah 3x, demam 38.5°C. Pemeriksaan fisik: nyeri tekan McBurney (+), Rovsing sign (+), defans muskuler (+). Leukosit 16.500. USG abdomen: appendix diameter 12mm, non-compressible. Diagnosa: Appendisitis akut.",
  "expected": "{\"diagnoses\":[\"acute appendicitis\"],\"clinical_findings\":[\"right lower quadrant pain\",\"migrating pain from epigastrium\",\"nausea\",\"vomiting\",\"fever 38.5°C\",\"McBurney point tenderness positive\",\"Rovsing sign positive\",\"guarding / muscle rigidity\",\"leukocytosis 16500\",\"appendix diameter 12mm non-compressible on ultrasound\"],\"abbreviations_expanded\":{\"USG\":\"ultrasound\"},\"lab_results\":[\"WBC 16500\"],\"risk_factors\":[]}",
  "evaluator": "clinical_keyword_judge",
  "icd_target": ["K35.89"],
  "difficulty": "easy"
}
```

#### `fraktur_femur.json`

```json
{
  "name": "fraktur_femur",
  "prompt": "Pasien laki-laki 35 tahun datang pasca kecelakaan lalu lintas. Nyeri hebat pada paha kiri, tidak bisa menggerakkan kaki kiri. Pemeriksaan fisik: deformitas pada 1/3 tengah femur kiri, edema (+), krepitasi (+). Rontgen: fraktur transversal os femur sinistra 1/3 media. NVD distal baik. Diagnosa: Closed fracture femur sinistra.",
  "expected": "{\"diagnoses\":[\"closed fracture of left femur shaft\"],\"clinical_findings\":[\"severe left thigh pain\",\"inability to move left leg\",\"deformity at mid-shaft left femur\",\"edema\",\"crepitus\",\"transverse fracture mid-shaft left femur on X-ray\",\"intact distal neurovascular status\"],\"abbreviations_expanded\":{\"NVD\":\"neurovascular distal\"},\"lab_results\":[],\"risk_factors\":[\"motor vehicle accident\"]}",
  "evaluator": "clinical_keyword_judge",
  "icd_target": ["S72.001A"],
  "difficulty": "easy"
}
```

### Level 2: Multi-Diagnosis

#### `dm_hipertensi.json`

```json
{
  "name": "dm_tipe2_hipertensi",
  "prompt": "Pasien perempuan 62 tahun, kontrol rutin. Riwayat DM tipe 2 sejak 10 tahun, HT stage 2. Keluhan: kesemutan pada kedua kaki, pandangan mulai kabur. GDS: 285 mg/dL. TD: 170/100 mmHg. HbA1c: 9.2%. Terapi: Metformin 2x500mg, Glimepiride 1x2mg, Amlodipin 1x10mg. Diagnosa: DM tipe 2 tidak terkontrol, Hipertensi esensial.",
  "expected": "{\"diagnoses\":[\"type 2 diabetes mellitus uncontrolled\",\"essential hypertension\"],\"clinical_findings\":[\"peripheral neuropathy\",\"tingling both feet\",\"blurred vision\",\"suspected diabetic retinopathy\"],\"abbreviations_expanded\":{\"DM\":\"diabetes mellitus\",\"HT\":\"hypertension\",\"GDS\":\"random blood glucose\",\"TD\":\"blood pressure\",\"HbA1c\":\"glycated hemoglobin\"},\"lab_results\":[\"random blood glucose 285 mg/dL\",\"blood pressure 170/100 mmHg\",\"HbA1c 9.2%\"],\"risk_factors\":[\"10-year diabetes history\"]}",
  "evaluator": "clinical_keyword_judge",
  "icd_target": ["E11.9", "I10"],
  "difficulty": "medium",
  "eval_checklist": [
    "DM dan HT di-expand dari abbreviasi",
    "kesemutan → peripheral neuropathy (enrichment)",
    "pandangan kabur → blurred vision + suspected diabetic retinopathy (enrichment)",
    "tidak terkontrol → uncontrolled",
    "kedua diagnosa tercapture terpisah"
  ]
}
```

#### `stroke_iskemik.json`

```json
{
  "name": "stroke_iskemik_akut",
  "prompt": "Pasien laki-laki 67 tahun dibawa ke IGD dengan kelemahan anggota gerak kanan mendadak onset 3 jam, bicara pelo, mulut mencong ke kiri. Riwayat: HT tidak terkontrol, merokok 30 tahun. CT scan kepala: tidak tampak perdarahan. NIHSS: 12. Diagnosa: Stroke iskemik akut, Hipertensi grade II.",
  "expected": "{\"diagnoses\":[\"acute ischemic stroke\",\"hypertension grade II\"],\"clinical_findings\":[\"right-sided hemiparesis\",\"acute onset 3 hours\",\"dysarthria\",\"facial palsy left deviation\",\"CT scan no hemorrhage\",\"NIHSS score 12\"],\"abbreviations_expanded\":{\"IGD\":\"emergency department\",\"HT\":\"hypertension\",\"NIHSS\":\"National Institutes of Health Stroke Scale\"},\"lab_results\":[],\"risk_factors\":[\"uncontrolled hypertension\",\"smoking 30 years\"]}",
  "evaluator": "clinical_keyword_judge",
  "icd_target": ["I63.9", "I10"],
  "difficulty": "medium",
  "eval_checklist": [
    "bicara pelo → dysarthria",
    "mulut mencong → facial palsy dengan lateralisasi",
    "kelemahan anggota gerak kanan → right-sided hemiparesis",
    "onset dan NIHSS ter-extract",
    "faktor risiko (HT, merokok) tercapture"
  ]
}
```

### Level 3: Kasus Kompleks

#### `ckd_on_hd.json`

```json
{
  "name": "ckd_on_hd_multikomorbid",
  "prompt": "Laki-laki 50 tahun, pasien HD rutin 2x/minggu sejak 2 tahun. Datang dengan keluhan bengkak pada kedua tungkai, mual, dan lemas. Riwayat: GGK ec nefropati diabetik. Lab: Ur 180, Cr 12.5, Hb 8.2, albumin 2.8. Elektrolit: K 5.8 mEq/L. Diagnosa: CKD stage 5 on HD, anemia renal, hiperkalemia, hipoalbuminemia.",
  "expected": "{\"diagnoses\":[\"chronic kidney disease stage 5\",\"renal anemia\",\"hyperkalemia\",\"hypoalbuminemia\"],\"clinical_findings\":[\"bilateral lower extremity edema\",\"nausea\",\"fatigue / malaise\",\"on regular hemodialysis 2x/week for 2 years\"],\"abbreviations_expanded\":{\"HD\":\"hemodialysis\",\"GGK\":\"chronic kidney disease\",\"CKD\":\"chronic kidney disease\",\"Ur\":\"blood urea nitrogen / urea\",\"Cr\":\"creatinine\",\"Hb\":\"hemoglobin\",\"K\":\"potassium\"},\"lab_results\":[\"BUN/urea 180\",\"creatinine 12.5\",\"hemoglobin 8.2\",\"albumin 2.8\",\"potassium 5.8 mEq/L\"],\"risk_factors\":[\"diabetic nephropathy as underlying cause\"]}",
  "evaluator": "clinical_keyword_judge",
  "icd_target": ["N18.5", "D63.1", "E87.5"],
  "difficulty": "hard",
  "eval_checklist": [
    "GGK → chronic kidney disease (bukan gagal ginjal kronik)",
    "HD → hemodialysis",
    "Ur dan Cr → BUN/urea dan creatinine",
    "ec nefropati diabetik → diabetic nephropathy sebagai etiologi",
    "semua 4 diagnosa tercapture (CKD, anemia, hiperkalemia, hipoalbuminemia)",
    "bengkak kedua tungkai → bilateral lower extremity edema"
  ]
}
```

#### `sepsis_multiorgan.json`

```json
{
  "name": "sepsis_disfungsi_multiorgan",
  "prompt": "Perempuan 70 tahun datang dengan penurunan kesadaran, GCS E2V3M4. Demam tinggi 40.1°C sejak 3 hari pasca operasi TURP. Riwayat: ISK berulang, DM tipe 2, HT. TD: 80/50 mmHg, nadi 130x/mnt, RR 28x/mnt. Lab: Leukosit 22.000, prokalsitonin 15.2, laktat 5.1, trombosit 65.000, SGOT 250, SGPT 180, Ur 120, Cr 4.5. Kultur urin: E. coli ESBL (+). Diagnosa: Sepsis ec ISK, syok septik, AKI stage 3, DIC, gangguan fungsi hepar, trombositopenia.",
  "expected": "{\"diagnoses\":[\"sepsis due to urinary tract infection\",\"septic shock\",\"acute kidney injury stage 3\",\"disseminated intravascular coagulation\",\"hepatic dysfunction\",\"thrombocytopenia\"],\"clinical_findings\":[\"decreased consciousness GCS 9 (E2V3M4)\",\"high fever 40.1°C\",\"post-operative TURP\",\"hypotension 80/50 mmHg\",\"tachycardia 130 bpm\",\"tachypnea 28 breaths/min\"],\"abbreviations_expanded\":{\"GCS\":\"Glasgow Coma Scale\",\"ISK\":\"urinary tract infection\",\"DM\":\"diabetes mellitus\",\"HT\":\"hypertension\",\"TD\":\"blood pressure\",\"RR\":\"respiratory rate\",\"SGOT\":\"AST / aspartate aminotransferase\",\"SGPT\":\"ALT / alanine aminotransferase\",\"Ur\":\"urea\",\"Cr\":\"creatinine\",\"TURP\":\"transurethral resection of prostate\",\"DIC\":\"disseminated intravascular coagulation\",\"AKI\":\"acute kidney injury\",\"ESBL\":\"extended-spectrum beta-lactamase\"},\"lab_results\":[\"WBC 22000\",\"procalcitonin 15.2\",\"lactate 5.1\",\"platelets 65000\",\"AST 250\",\"ALT 180\",\"urea 120\",\"creatinine 4.5\",\"urine culture E. coli ESBL positive\"],\"risk_factors\":[\"recurrent UTI\",\"type 2 diabetes mellitus\",\"hypertension\",\"post-surgical (TURP)\"]}",
  "evaluator": "clinical_keyword_judge",
  "icd_target": ["A41.9", "R65.21"],
  "difficulty": "hard",
  "eval_checklist": [
    "ISK → urinary tract infection",
    "TURP → transurethral resection of prostate",
    "SGOT/SGPT → AST/ALT",
    "DIC → disseminated intravascular coagulation",
    "AKI → acute kidney injury",
    "GCS E2V3M4 → GCS 9 dengan breakdown",
    "ESBL → extended-spectrum beta-lactamase",
    "semua 6 diagnosa tercapture",
    "kultur urin ter-extract sebagai lab result"
  ]
}
```

---

## 4. Custom Evaluator: `clinical_keyword_judge`

### Tipe: Hybrid (LLM judge + scoring)

Evaluator ini menggunakan 2-pass LLM-as-judge yang sudah ada di evonic-llm-eval, dengan custom eval prompt yang menilai 3 dimensi.

### Eval Prompt

```
Kamu adalah clinical NLP quality assessor. Tugasmu menilai kualitas output translate & enrich dari resume medis Indonesia ke English clinical keywords.

Kamu akan menerima:
- EXPECTED: ground truth keywords (JSON)
- RESPONSE: output model yang dievaluasi (JSON)

Nilai berdasarkan 3 dimensi (skor 1-5 per dimensi):

## 1. COMPLETENESS (bobot 40%)
Apakah SEMUA kondisi klinis dari expected ada di response?
- 5: Semua diagnosa dan temuan klinis tercapture
- 4: 1 item minor terlewat (mis: risk factor)
- 3: 1 diagnosa atau 2+ temuan terlewat
- 2: Multiple diagnosa terlewat
- 1: Mayoritas terlewat

## 2. CLINICAL ACCURACY (bobot 40%)
Apakah terjemahan medisnya benar secara terminologi?
- 5: Semua terjemahan menggunakan terminologi medis standar yang benar
- 4: Minor: penggunaan sinonim yang kurang presisi tapi masih benar (mis: "shortness of breath" vs "dyspnea")
- 3: 1-2 terjemahan yang kurang tepat tapi tidak salah arah
- 2: Ada terjemahan yang salah secara klinis
- 1: Banyak terjemahan yang salah

## 3. ABBREVIATION HANDLING (bobot 20%)
Apakah abbreviasi medis Indonesia dikenali dan di-expand dengan benar?
- 5: Semua abbreviasi ter-expand benar (GGK→CKD, HD→hemodialysis, Ur→urea/BUN, dll)
- 4: 1 abbreviasi minor tidak ter-expand
- 3: 1-2 abbreviasi penting tidak ter-expand
- 2: Banyak abbreviasi tidak dikenali
- 1: Tidak ada penanganan abbreviasi

Berikan output PERSIS dalam format ini:
```
COMPLETENESS: [1-5]
ACCURACY: [1-5]
ABBREVIATION: [1-5]
WEIGHTED_SCORE: [hitung: (completeness*0.4 + accuracy*0.4 + abbreviation*0.2) / 5 * 100]
PASS: [YES jika weighted_score >= 70, NO jika < 70]
REASONING: [penjelasan singkat max 3 kalimat]
```
```

### Regex Pattern untuk extract skor

```
WEIGHTED_SCORE:\s*(\d+(?:\.\d+)?)
```

### Scoring Config

```json
{
  "type": "hybrid",
  "eval_prompt": "<prompt di atas>",
  "regex_pattern": "WEIGHTED_SCORE:\\s*(\\d+(?:\\.\\d+)?)",
  "score_type": "numeric",
  "max_score": 100,
  "pass_threshold": 70
}
```

---

## 5. Baseline Comparison Setup

Untuk membandingkan model 26B vs Claude API, jalankan eval 2x dengan endpoint berbeda:

### Run 1: Model 26B (lokal)

```env
LLM_BASE_URL=http://localhost:8080/v1
LLM_MODEL=model-26b
```

### Run 2: Claude API (baseline via OpenRouter atau langsung)

```env
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_API_KEY=your-key
LLM_MODEL=anthropic/claude-3.5-haiku
```

Bandingkan skor weighted_score antara kedua run di history. Target: model 26B harus mencapai minimal 80% dari skor Claude API.

---

## 6. Downstream Evaluation (Opsional, Tahap Berikutnya)

Setelah model 26B lolos evaluasi keyword di atas, langkah berikutnya adalah downstream eval — menguji apakah output Step 1 menghasilkan retrieval ICD-10 yang benar di Step 2.

### Pendekatan

Buat tool di evonic-llm-eval (`/backend/tools/`) yang:
1. Menerima output JSON dari Step 1
2. Memanggil Step 2 retrieval API (BGE-M3 + BM25)
3. Mengecek apakah `icd_target` ada di top-10 hasil retrieval
4. Return hit/miss

Ini memanfaatkan unified tool system yang sudah ada — di eval mode pakai mock, di production pakai real retrieval endpoint.

### Tool Definition

```json
{
  "name": "icd_retrieval_check",
  "description": "Feed translated keywords ke Step 2 retrieval dan cek apakah target ICD codes muncul di hasil",
  "parameters": {
    "type": "object",
    "properties": {
      "keywords_json": {
        "type": "string",
        "description": "JSON output dari Step 1"
      },
      "icd_targets": {
        "type": "array",
        "items": {"type": "string"},
        "description": "Kode ICD-10 yang diharapkan muncul"
      }
    }
  }
}
```

---

## 7. Ringkasan Action Items

| # | Task | Priority | Detail |
|---|------|----------|--------|
| 1 | Buat domain `clinical_translate` | Tinggi | `domain.json` + folder level_1/2/3 |
| 2 | Buat test definition files | Tinggi | 7 file JSON (3 easy, 2 medium, 2 hard) |
| 3 | Buat custom evaluator `clinical_keyword_judge` | Tinggi | Hybrid evaluator via Settings page |
| 4 | Run eval model 26B | Tinggi | Pakai headless mode atau web UI |
| 5 | Run eval Claude API (baseline) | Sedang | Bandingkan skor di history |
| 6 | Analisis gap | Sedang | Identifikasi pola error untuk optimasi prompt |
| 7 | Downstream eval tool | Rendah | `/backend/tools/icd_retrieval_check.py` |

---

## 8. Catatan Penting

- **Format output JSON harus konsisten** — system prompt harus cukup tegas agar model selalu output valid JSON. Jika model 26B kesulitan, pertimbangkan pakai constrained decoding / JSON mode jika server LLM mendukung.
- **Evaluator menilai secara semantik, bukan exact match** — "shortness of breath" dan "dyspnea" keduanya dianggap benar oleh LLM judge, tapi "dyspnea" mendapat skor accuracy lebih tinggi karena lebih spesifik secara terminologi.
- **Field `icd_target` di test definition** bukan untuk evaluator keyword — itu untuk downstream eval di tahap berikutnya. Simpan sekarang supaya tidak perlu menambahkan nanti.
- **Mulai dari level 1** — jika model 26B sudah bagus di level 1, lanjut ke level 2 dan 3. Jika gagal di level 1, fokus optimasi prompt dulu sebelum lanjut.

