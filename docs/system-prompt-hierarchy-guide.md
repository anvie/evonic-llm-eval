# System Prompt Hierarchy Guide

## Overview

Evonic LLM Evaluator now supports **hierarchical system prompts** with three levels:

```
Domain-level (default) → Test-level (override/append)
```

This allows you to:
- Set a **default system prompt** at the domain level
- **Override** it per-test, or **append** additional instructions
- Maintain consistency while allowing flexibility

---

## Hierarchy Levels

### 1. Domain-Level System Prompt

**Location:** Domain configuration (`test_definitions/<domain>/domain.json`)

**Purpose:** Default system prompt for all tests in the domain

**Example:**
```json
{
  "id": "krasan_villa",
  "name": "Krasan Villa Reservation",
  "system_prompt": "Kamu adalah asisten reservasi untuk Krasan Omah...",
  "system_prompt_mode": "overwrite"
}
```

### 2. Test-Level System Prompt

**Location:** Individual test files (`test_definitions/<domain>/level_X/test.json`)

**Purpose:** Customize or extend domain-level prompt for specific tests

**Modes:**
- **`overwrite`**: Replace domain prompt entirely
- **`append`**: Add to domain prompt (domain + test)

**Example:**
```json
{
  "id": "check_availability",
  "name": "Check Room Availability",
  "system_prompt": "Jika tamu bertanya tentang harga, selalu sebutkan extra bed dan breakfast.",
  "system_prompt_mode": "append"
}
```

---

## How It Works

### Resolution Logic

```
IF test.system_prompt exists:
    IF mode == 'append':
        RETURN domain_prompt + "\\n\\n" + test_prompt
    ELSE (mode == 'overwrite'):
        RETURN test_prompt
ELSE:
    RETURN domain_prompt (or None if not set)
```

### Example Scenarios

#### Scenario 1: Domain Default Only
```json
// Domain: conversation
{
  "system_prompt": "Kamu adalah asisten yang ramah.",
  "system_prompt_mode": "overwrite"
}

// Test: greeting
{
  // No system_prompt
}

// Result: "Kamu adalah asisten yang ramah."
```

#### Scenario 2: Test Override (Overwrite Mode)
```json
// Domain: conversation
{
  "system_prompt": "Kamu adalah asisten yang ramah.",
  "system_prompt_mode": "overwrite"
}

// Test: formal_greeting
{
  "system_prompt": "Gunakan bahasa formal dan sopan.",
  "system_prompt_mode": "overwrite"
}

// Result: "Gunakan bahasa formal dan sopan."
```

#### Scenario 3: Test Extension (Append Mode)
```json
// Domain: krasan_villa
{
  "system_prompt": "Kamu adalah asisten reservasi untuk Krasan Omah.\n\n## PRICING\n| Kamar | Harga |\n| Bismo | Rp 400.000 |",
  "system_prompt_mode": "overwrite"
}

// Test: check_price
{
  "system_prompt": "Jika tamu tanya harga, selalu sebutkan extra bed (Rp 150.000) dan breakfast (Rp 50.000).",
  "system_prompt_mode": "append"
}

// Result:
// "Kamu adalah asisten reservasi untuk Krasan Omah.
//
// ## PRICING
// | Kamar | Harga |
// | Bismo | Rp 400.000 |
//
// Jika tamu tanya harga, selalu sebutkan extra bed (Rp 150.000) dan breakfast (Rp 50.000)."
```

---

## UI Usage

### Setting Domain-Level System Prompt

1. Go to **Settings** → **Domains** tab
2. Click **Edit** on a domain
3. Fill in **Domain System Prompt**
4. Choose **System Prompt Mode** (default for tests)
5. Save

### Setting Test-Level System Prompt

1. Go to **Settings** → Click on a domain
2. Click **Edit** on a test
3. Fill in **System Prompt** (optional)
4. Choose **System Prompt Mode**:
   - **Overwrite**: Replace domain prompt
   - **Append**: Add to domain prompt
5. Save

---

## Use Cases

### 1. Common Persona + Task-Specific Instructions

**Domain:** All customer service tests
```json
{
  "system_prompt": "Kamu adalah customer service yang ramah, profesional, dan helpful."
}
```

**Test:** Handling complaints
```json
{
  "system_prompt": "Untuk komplain, gunakan langkah: 1) Dengarkan, 2) Minta maaf, 3) Tawarkan solusi.",
  "system_prompt_mode": "append"
}
```

### 2. Base Knowledge + Test Variations

**Domain:** Krasan Villa
```json
{
  "system_prompt": "Kamu adalah asisten reservasi untuk Krasan Omah di Temanggung.\n\n## FASILITAS\n- Check-in: 14:00\n- Check-out: 12:00\n- Free WiFi, parking"
}
```

**Test:** Weekend pricing
```json
{
  "system_prompt": "## WEEKEND PRICING (Jum-Min)\nHarga weekend 25% lebih tinggi dari weekday.",
  "system_prompt_mode": "append"
}
```

### 3. Language Switching

**Domain:** Indonesian tests
```json
{
  "system_prompt": "Selalu jawab dalam Bahasa Indonesia."
}
```

**Test:** English translation
```json
{
  "system_prompt": "Translate the response to English.",
  "system_prompt_mode": "overwrite"
}
```

---

## Training Data Generation

When you click **"Generate Training Data"**, the system now uses the **resolved system prompt** (after hierarchy resolution) instead of a hardcoded prompt.

**Before:** Always used Krasan Omah prompt
**After:** Uses test's effective system prompt

---

## Best Practices

### ✅ DO:

- Use domain-level for **common knowledge** (pricing, policies, persona)
- Use test-level with `append` for **specific variations** (special cases, exceptions)
- Use test-level with `overwrite` for **completely different contexts**
- Keep domain prompts **concise** (avoid duplicating in every test)

### ❌ DON'T:

- Don't repeat domain-level info in every test (use `append` instead)
- Don't use `overwrite` if you just want to add something
- Don't make domain prompts too long (>1000 chars)

---

## API & Database

### Database Schema

**`domains` table:**
- `system_prompt TEXT`
- `system_prompt_mode TEXT DEFAULT 'overwrite'`

**`tests` table:**
- `system_prompt TEXT`
- `system_prompt_mode TEXT DEFAULT 'overwrite'`

### Migration

Run once to add columns:
```bash
cd ~/dev/evonic-llm-eval
python3 migrate_add_system_prompt_phase2.py
```

Then sync:
```bash
python3 sync_tests.py
```

---

## Files Changed

- `models/db.py` - Database schema
- `evaluator/test_loader.py` - Hierarchy resolution logic
- `evaluator/engine.py` - Use resolved system prompt
- `templates/settings.html` - UI for domain/test prompts
- `static/js/training-data.js` - Use resolved prompt (no hardcoded)
- `migrate_add_system_prompt_phase2.py` - Migration script

---

## Troubleshooting

### System prompt not showing in evaluation

1. Check if test has `system_prompt` field
2. Check if domain has `system_prompt` field
3. Run migration: `python3 migrate_add_system_prompt_phase2.py`
4. Sync tests: `python3 sync_tests.py`

### Training data still using old prompt

1. Make sure test has `system_prompt` set
2. The modal should receive `system_prompt` from API
3. Check browser console for errors

### Mode not working as expected

- `overwrite` = test prompt completely replaces domain
- `append` = domain + "\\n\\n" + test
- Check the mode setting in test configuration

---

## Example JSON Files

### Domain with System Prompt
```json
{
  "id": "krasan_villa",
  "name": "Krasan Villa",
  "description": "Reservation assistant for Krasan Omah",
  "system_prompt": "Kamu adalah asisten reservasi untuk Krasan Omah, sebuah penginapan di Temanggung, Jawa Tengah.\n\n## PRICING (per malam)\n| Kamar | Weekday (Sen-Kam) | Weekend (Jum-Min) |\n| Bismo | Rp 400.000 | Rp 500.000 |\n| Sindoro | Rp 400.000 | Rp 500.000 |\n| Sumbing | Rp 450.000 | Rp 550.000 |\n| Joglo | Rp 550.000 | Rp 700.000 |",
  "system_prompt_mode": "overwrite",
  "icon": "chat",
  "color": "#3B82F6"
}
```

### Test with Append Mode
```json
{
  "id": "check_availability",
  "name": "Check Room Availability",
  "description": "Guest asks about room availability for specific dates",
  "prompt": "Apakah kamar Bismo tersedia untuk tanggal 10-12 April 2026?",
  "system_prompt": "## EXTRAS\n- Extra bed: Rp 150.000/malam\n- Extra breakfast: Rp 50.000/orang\n\nSelalu tawarkan extra bed dan breakfast jika tamu bertanya tentang harga.",
  "system_prompt_mode": "append",
  "evaluator_id": "keyword"
}
```

---

## Testing

Run unit tests:
```bash
cd ~/dev/evonic-llm-eval
python3 -m pytest unit_tests/ -v -k system_prompt
```

Manual test:
1. Set domain system prompt
2. Create test with `append` mode
3. Run evaluation
4. Check logs for `[SYSTEM]` message showing resolved prompt

---

## See Also

- Regex Evaluator Guide: `docs/regex-evaluator-guide.md`
- Custom Evaluators: `evaluator/custom_evaluator.py`
- Test Loader: `evaluator/test_loader.py`
