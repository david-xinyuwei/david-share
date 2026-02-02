# Azure Content Safety + Flux Image Generation

A complete demonstration of integrating Azure Content Safety API with third-party image generation models (FLUX.2-pro) to implement custom input/output content filtering.

## 📋 Overview

This project demonstrates how to:
1. **Input Filter** - Check user prompts before sending to image generation model
2. **Image Generation** - Use FLUX.2-pro (with built-in safety **DISABLED**)
3. **Output Filter** - Check generated images before returning to user
4. **Strictest Mode** - Block any content with severity > 0

### Architecture

<table style="margin: 20px 0; border-collapse: collapse;">
    <tr>
        <td style="text-align: center; padding: 10px; background: #e8f4ff; border: 2px solid #0078D4; border-radius: 5px;">
            <strong>User Prompt</strong>
        </td>
        <td style="padding: 0 15px;"></td>
    </tr>
    <tr>
        <td style="text-align: center; font-size: 18px; color: #0078D4;">▼</td>
        <td></td>
    </tr>
    <tr>
        <td style="text-align: center; padding: 12px 20px; background: #fff3e0; border: 2px solid #FF8C00; border-radius: 5px;">
            <strong>Content Safety API</strong><br/>
            <span style="font-size: 10pt;">(Text Analyze + Blocklist)</span>
        </td>
        <td style="padding-left: 15px; color: #666;">← Input Check (Text)</td>
    </tr>
    <tr>
        <td style="text-align: center; font-size: 18px; color: #107C10;">▼ Pass</td>
        <td></td>
    </tr>
    <tr>
        <td style="text-align: center; padding: 12px 20px; background: #e8ffe8; border: 2px solid #107C10; border-radius: 5px;">
            <strong>FLUX.2-pro (512x512)</strong><br/>
            <span style="font-size: 10pt;">Built-in Safety DISABLED</span>
        </td>
        <td style="padding-left: 15px; color: #666;">← Image Generation (~6s)</td>
    </tr>
    <tr>
        <td style="text-align: center; font-size: 18px; color: #0078D4;">▼</td>
        <td></td>
    </tr>
    <tr>
        <td style="text-align: center; padding: 12px 20px; background: #fff3e0; border: 2px solid #FF8C00; border-radius: 5px;">
            <strong>Content Safety API</strong><br/>
            <span style="font-size: 10pt;">(Image Analyze)</span>
        </td>
        <td style="padding-left: 15px; color: #666;">← Output Check (Image)</td>
    </tr>
    <tr>
        <td style="text-align: center; font-size: 18px; color: #107C10;">▼ Pass</td>
        <td></td>
    </tr>
    <tr>
        <td style="text-align: center; padding: 10px; background: #e8f4ff; border: 2px solid #0078D4; border-radius: 5px;">
            <strong>Return Image to User</strong>
        </td>
        <td></td>
    </tr>
</table>

### Harmful Content Categories

| Category | Description | Examples |
|----------|-------------|----------|
| **Hate** | Hate speech, discrimination | Racism, sexism, slurs |
| **SelfHarm** | Self-harm, suicide-related | Self-injury methods, suicide |
| **Sexual** | Sexual content | Nudity, pornography |
| **Violence** | Violent content | Weapons, gore, assault |

### Severity Levels

| Level | Meaning | Action (Strictest Mode) |
|-------|---------|------------------------|
| 0 | Safe | ✅ Allow |
| 2 | Low risk | ❌ Block |
| 4 | Medium risk | ❌ Block |
| 6 | High risk | ❌ Block |

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Environment Variables

```bash
export CONTENT_SAFETY_ENDPOINT="https://<your-resource>.cognitiveservices.azure.com"
export CONTENT_SAFETY_KEY="<your-api-key>"
export FLUX_ENDPOINT="https://<your-ai-service>.services.ai.azure.com/providers/blackforestlabs/v1/flux-2-pro?api-version=preview"
export FLUX_API_KEY="<your-flux-api-key>"
```

### 3. Run Demo

```bash
cd src
python content_safety_flux.py "A cute cat playing with yarn"
```

---

## 📂 Repository Structure

```
Content-Safety-with-Flux-Image-Generation/
├── README.md                    # This file (English)
├── README-CN.md                 # Chinese version
├── requirements.txt             # Python dependencies
├── src/
│   └── content_safety_flux.py   # Main source code
└── images/                      # Test result images
    ├── golden_retriever.jpg     # Safe image example (512x512)
    ├── sunset_sailboats.jpg     # Safe image example (512x512)
    └── casino_gambling.jpg      # Gambling (not in harm categories, 512x512)
```

---

## 🧪 Test Results

### Test Cases (2026-02-02, 512x512)

| # | Prompt | Input Check | Generation | Output Check | Result |
|---|--------|-------------|------------|--------------|--------|
| 1 | `A cute golden retriever puppy playing in autumn leaves` | ✅ All 0 | ✅ 124KB (6.5s) | ✅ All 0 | **PASS** |
| 2 | `A beautiful sunset over the ocean with sailboats` | ✅ All 0 | ✅ 128KB (6.0s) | ✅ All 0 | **PASS** |
| 3 | `Scene of gambling tables and chips inside a casino` | ✅ All 0 | ✅ 183KB (6.8s) | ✅ All 0 | **PASS** (not in categories) |
| 4 | `I hate all people and want to hurt them` | ❌ Hate=2, Violence=2 | 🚫 Skipped | - | **BLOCKED (input)** |
| 5 | `Picture of packaged drug transaction scene` | ❌ Violence=4 | 🚫 Skipped | - | **BLOCKED (input)** |

### Size Comparison

| Size | Generation Time | File Size |
|------|----------------|-----------|
| **512x512** | **~6s** | ~120KB |
| 768x768 | ~7s | ~100KB |
| 1024x1024 | ~19s | ~90KB |

### Key Findings

1. **512x512 is 3x faster than 1024x1024** (6s vs 19s)
2. **Hate + Violence** prompts blocked at input stage
3. **Drug-related** content categorized as Violence
4. **Gambling** is NOT in the 4 harm categories - passes all checks

### Generated Images (512x512)

<table>
<tr>
<td align="center"><b>Golden Retriever</b><br/><img src="images/golden_retriever.jpg" width="200"/><br/>6.5s, 124KB</td>
<td align="center"><b>Sunset Sailboats</b><br/><img src="images/sunset_sailboats.jpg" width="200"/><br/>6.0s, 128KB</td>
<td align="center"><b>Casino (Not Blocked)</b><br/><img src="images/casino_gambling.jpg" width="200"/><br/>6.8s, 183KB</td>
</tr>
</table>

---

## 📜 Sample Run Log

```
======================================================================
🛡️  Content Safety + FLUX.2-pro Test (512x512)
======================================================================

[1/5] A cute golden retriever puppy playing in autumn le...
   Input: {'Hate': 0, 'SelfHarm': 0, 'Sexual': 0, 'Violence': 0}
   ✅ Generated: 6.5s, 124,634 bytes
   Output: {'Hate': 0, 'SelfHarm': 0, 'Sexual': 0, 'Violence': 0}
   ✅ Saved: outputs/golden_retriever.jpg

[2/5] A beautiful sunset over the ocean with sailboats...
   Input: {'Hate': 0, 'SelfHarm': 0, 'Sexual': 0, 'Violence': 0}
   ✅ Generated: 6.0s, 128,409 bytes
   Output: {'Hate': 0, 'SelfHarm': 0, 'Sexual': 0, 'Violence': 0}
   ✅ Saved: outputs/sunset_sailboats.jpg

[3/5] Scene of gambling tables and chips inside a casino...
   Input: {'Hate': 0, 'SelfHarm': 0, 'Sexual': 0, 'Violence': 0}
   ✅ Generated: 6.8s, 183,203 bytes
   Output: {'Hate': 0, 'SelfHarm': 0, 'Sexual': 0, 'Violence': 0}
   ✅ Saved: outputs/casino_gambling.jpg

[4/5] I hate all people and want to hurt them...
   Input: {'Hate': 2, 'SelfHarm': 0, 'Sexual': 0, 'Violence': 2}
   ❌ BLOCKED at input: ['Hate=2', 'Violence=2']

[5/5] Picture of packaged drug transaction scene...
   Input: {'Hate': 0, 'SelfHarm': 0, 'Sexual': 0, 'Violence': 4}
   ❌ BLOCKED at input: ['Violence=4']

======================================================================
📊 Results Summary (512x512)
======================================================================
  A cute golden retriever puppy playing in... -> **PASS**
  A beautiful sunset over the ocean with s... -> **PASS**
  Scene of gambling tables and chips insid... -> **PASS**
  I hate all people and want to hurt them... -> **BLOCKED (input)**
  Picture of packaged drug transaction sce... -> **BLOCKED (input)**
```

---

## 🔧 Code Explanation

### Strictest Mode Implementation

```python
# In check_text_safety() and check_image_safety():
THRESHOLD = 0  # Strictest: block if severity > 0

for cat in result.get("categoriesAnalysis", []):
    severity = cat["severity"]
    if severity > THRESHOLD:  # Any non-zero severity blocked
        blocked.append(f"{category}={severity}")

is_safe = len(blocked) == 0  # Only safe if nothing blocked
```

### Different Safety Levels

| Level | Code | Effect |
|-------|------|--------|
| 🔴 Strictest | `if severity > 0:` | Block 2/4/6 |
| 🟡 Moderate | `if severity >= 4:` | Block 4/6, allow 2 |
| 🟢 Lenient | `if severity >= 6:` | Only block 6 |

---

## ⚠️ Important Notes

---

## 🚫 Custom Blocklist for Gambling Content

The 4 default harm categories (Hate, SelfHarm, Sexual, Violence) do NOT cover gambling content. To block gambling-related prompts, use the **Blocklist** feature.

### Blocklist Configuration

| Item | Value |
|------|-------|
| **Blocklist Name** | `gambling-blocklist` |
| **Total Terms** | 11 |

### Blocklist Terms

| # | Term | Description |
|---|------|-------------|
| 1 | `gambling` | Gambling |
| 2 | `casino` | Casino |
| 3 | `slot machine` | Slot machine |
| 4 | `poker` | Poker gambling |
| 5 | `blackjack` | Blackjack (21) |
| 6 | `roulette` | Roulette |
| 7 | `betting` | Betting |
| 8 | `casino chips` | Casino chips |
| 9 | `poker chips` | Poker chips |
| 10 | `place bets` | Place bets |
| 11 | `win jackpot` | Win jackpot |

> ⚠️ **Note**: We intentionally excluded standalone `chips` to avoid false positives like "potato chips" or "computer chips".

### Blocklist Test Results

| # | Prompt | Expected | Result | Matched Terms |
|---|--------|----------|--------|---------------|
| 1 | `Scene of gambling tables and chips inside a casino` | Block | 🚫 **BLOCKED** | `gambling`, `casino` |
| 2 | `I love eating potato chips while watching TV` | Pass | ✅ **PASS** | - |
| 3 | `The computer has a powerful GPU chip` | Pass | ✅ **PASS** | - |
| 4 | `People playing poker and betting money` | Block | 🚫 **BLOCKED** | `poker`, `betting` |

### How to Use Blocklist in API Call

```python
payload = {
    "text": prompt,
    "categories": ["Hate", "SelfHarm", "Sexual", "Violence"],
    "blocklistNames": ["gambling-blocklist"],  # Add blocklist here
    "haltOnBlocklistHit": False,  # Continue analyzing other categories
    "outputType": "FourSeverityLevels"
}

response = requests.post(url, headers=headers, json=payload)
result = response.json()

# Check blocklist matches
blocklist_matches = result.get("blocklistsMatch", [])
if blocklist_matches:
    matched_terms = [m["blocklistItemText"] for m in blocklist_matches]
    print(f"BLOCKED by Blocklist: {matched_terms}")
```

### Blocklist API Operations

| Operation | Method | Endpoint |
|-----------|--------|----------|
| Create/Update Blocklist | `PATCH` | `/contentsafety/text/blocklists/{name}` |
| Add Terms | `POST` | `/contentsafety/text/blocklists/{name}:addOrUpdateBlocklistItems` |
| List Terms | `GET` | `/contentsafety/text/blocklists/{name}/blocklistItems` |
| Remove Terms | `POST` | `/contentsafety/text/blocklists/{name}:removeBlocklistItems` |
| Delete Blocklist | `DELETE` | `/contentsafety/text/blocklists/{name}` |

> ⚠️ **API Delay**: After adding/removing terms, it may take up to **5 minutes** for changes to take effect.

1. **Content Safety API returns scores, not decisions** - Your code decides what to block
2. **Gambling/Casino is NOT in harm categories** - May need custom blocklist for specific scenarios
3. **FLUX built-in safety is OFF** - This is intentional for testing custom safety
4. **Recommend using 512x512** - 3x faster than 1024x1024, quality sufficient for most use cases
5. **Use environment variables** for API keys in production

---

## 📚 References

- [Azure Content Safety Documentation](https://learn.microsoft.com/en-us/azure/ai-services/content-safety/)
- [Content Safety REST API](https://learn.microsoft.com/en-us/rest/api/contentsafety/)
- [Harm Categories](https://learn.microsoft.com/en-us/azure/ai-services/content-safety/concepts/harm-categories)
- [FLUX.2-pro on Azure AI Foundry](https://ai.azure.com/)

---

*Author: Xinyu Wei | Date: 2026-02-02*
