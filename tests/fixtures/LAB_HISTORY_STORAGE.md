# Lab History Storage Strategy for healthOS

## Overview

Users upload lab results as `.txt` files via Telegram. The bot parses biomarker values and stores them in MongoDB. Original files can optionally be retained for audit purposes.

## Storage Architecture

### Option 1: Parse-Only (Demo - Recommended)

**User uploads** → **Bot parses** → **MongoDB storage** → **File discarded**

```python
# healthos_bot/bot/bot.py

async def parse_lab_results(user_id: int, file_path: str, update: Update):
    """Parse lab results and store in MongoDB."""

    # Read file
    with open(file_path, 'r') as f:
        content = f.read()

    # Extract biomarkers (regex parsing)
    biomarkers = extract_biomarkers(content)

    # Extract metadata
    collection_date = extract_date(content)
    lab_name = extract_lab_name(content)  # "Quest Diagnostics" or "LabCorp"

    # Get existing history
    biomarker_history = db.get_user_attribute(user_id, 'health_biomarkers_history') or []

    # Add new entry
    biomarker_history.append({
        "collection_date": collection_date,
        "lab": lab_name,
        "source_filename": os.path.basename(file_path),
        "values": biomarkers
    })

    # Sort by date
    biomarker_history.sort(key=lambda x: x['collection_date'])

    # Store in MongoDB
    db.set_user_attribute(user_id, 'health_biomarkers_history', biomarker_history)

    # File is deleted after parsing (temporary /tmp storage)
    os.remove(file_path)

    # Calculate deltas if multiple entries exist
    if len(biomarker_history) > 1:
        deltas = calculate_biomarker_deltas(biomarker_history)
        await update.message.reply_text(format_deltas_message(deltas))
```

**MongoDB Document Structure**:
```javascript
{
  "user_id": 12345,
  "health_biomarkers_history": [
    {
      "collection_date": "2025-07-15",
      "lab": "Quest Diagnostics",
      "source_filename": "sarah_chen_baseline_labs.txt",
      "values": {
        "HbA1c": 5.9,
        "fasting_glucose": 105,
        "fasting_insulin": 14.2,
        "HOMA-IR": 3.7,
        "CRP": 0.7,
        "IL-6": 1.1,
        "TNF-alpha": 2.3,
        "8-OHdG": 4.2,
        "triglycerides": 142,
        "HDL": 52,
        "LDL": 118,
        "adiponectin": 8.2,
        "ALT": 32
      }
    },
    {
      "collection_date": "2025-12-15",
      "lab": "LabCorp",
      "source_filename": "sarah_chen_3month_labs.txt",
      "values": {
        "HbA1c": 6.3,
        "fasting_glucose": 119,
        "fasting_insulin": 18.6,
        "HOMA-IR": 5.4,
        "CRP": 2.1,
        "IL-6": 3.1,
        "TNF-alpha": 3.6,
        "8-OHdG": 8.6,
        "triglycerides": 168,
        "HDL": 48,
        "LDL": 128,
        "adiponectin": 6.8,
        "ALT": 41
      }
    }
  ]
}
```

---

### Option 2: Parse + Store Original Files (Production)

**User uploads** → **Bot saves file** → **Bot parses** → **MongoDB storage + file reference**

```python
async def parse_and_store_lab_results(user_id: int, file_path: str, update: Update):
    """Parse lab results and store original file."""

    # Create user lab storage directory
    user_lab_dir = f"/data/lab_results/{user_id}"
    os.makedirs(user_lab_dir, exist_ok=True)

    # Read file
    with open(file_path, 'r') as f:
        content = f.read()

    # Extract metadata
    collection_date = extract_date(content)

    # Save original file with timestamp
    stored_filename = f"{collection_date}_{os.path.basename(file_path)}"
    stored_path = os.path.join(user_lab_dir, stored_filename)
    shutil.copy(file_path, stored_path)

    # Parse biomarkers
    biomarkers = extract_biomarkers(content)

    # Get existing history
    biomarker_history = db.get_user_attribute(user_id, 'health_biomarkers_history') or []

    # Add new entry with file reference
    biomarker_history.append({
        "collection_date": collection_date,
        "lab": extract_lab_name(content),
        "original_file_path": stored_path,  # Reference to stored file
        "values": biomarkers
    })

    biomarker_history.sort(key=lambda x: x['collection_date'])
    db.set_user_attribute(user_id, 'health_biomarkers_history', biomarker_history)

    # Delete temporary upload file
    os.remove(file_path)
```

**File System Structure**:
```
/data/lab_results/
├── 12345/  (user_id)
│   ├── 2025-07-15_sarah_chen_baseline_labs.txt
│   └── 2025-12-15_sarah_chen_3month_labs.txt
├── 67890/
│   ├── 2025-06-01_john_doe_annual_physical.txt
│   └── 2025-09-15_john_doe_followup.txt
```

**MongoDB Document with File References**:
```javascript
{
  "user_id": 12345,
  "health_biomarkers_history": [
    {
      "collection_date": "2025-07-15",
      "original_file_path": "/data/lab_results/12345/2025-07-15_sarah_chen_baseline_labs.txt",
      "values": { ... }
    }
  ]
}
```

---

## Biomarker Delta Calculation

When user uploads new labs, automatically calculate changes from baseline:

```python
def calculate_biomarker_deltas(history: list) -> dict:
    """Calculate deltas from most recent two entries."""

    if len(history) < 2:
        return {}

    baseline = history[-2]['values']  # Previous
    current = history[-1]['values']   # Current

    deltas = {}
    for marker in current.keys():
        if marker in baseline:
            old_val = baseline[marker]
            new_val = current[marker]

            delta_absolute = new_val - old_val
            delta_percent = ((new_val - old_val) / old_val) * 100 if old_val != 0 else 0

            deltas[marker] = {
                "old": old_val,
                "new": new_val,
                "delta": delta_absolute,
                "delta_percent": delta_percent,
                "trend": "↑" if delta_absolute > 0 else "↓" if delta_absolute < 0 else "→"
            }

    return deltas


def format_deltas_message(deltas: dict) -> str:
    """Format delta message for Telegram."""

    message = "📊 **Lab Results Comparison**\n\n"

    # Highlight significant changes
    significant = []
    for marker, data in deltas.items():
        if abs(data['delta_percent']) > 20:  # >20% change
            significant.append((marker, data))

    if significant:
        message += "⚠️ **Significant Changes:**\n"
        for marker, data in significant:
            message += f"• {marker}: {data['old']} → {data['new']} "
            message += f"({data['trend']} {abs(data['delta_percent']):.1f}%)\n"
        message += "\n"

    message += "📈 **All Changes:**\n"
    for marker, data in deltas.items():
        message += f"• {marker}: {data['old']} → {data['new']} "
        message += f"({data['trend']} {data['delta']:+.2f})\n"

    return message
```

---

## Demo Implementation (Recommended)

For the production demo, use **Option 1 (Parse-Only)**:

### Pros:
- ✅ Simpler implementation
- ✅ No file storage management needed
- ✅ Faster processing
- ✅ MongoDB is single source of truth

### Cons:
- ❌ Can't re-parse if extraction logic changes
- ❌ No original file for audit/verification

### Why It's Fine for Demo:
- Demo focuses on health intelligence, not lab file management
- Fixture files (`sarah_chen_*_labs.txt`) can be re-uploaded anytime
- MongoDB history provides complete biomarker timeline
- INDRA agent only needs the parsed values, not original files

---

## Example User Flow (Demo)

### 1. User Uploads Baseline Labs
```
User: [sends sarah_chen_baseline_labs.txt]

Bot: ✅ Lab results processed (2025-07-15):

📊 Biomarkers detected:
• HbA1c: 5.9%
• Glucose: 105 mg/dL
• CRP: 0.7 mg/L
• IL-6: 1.1 pg/mL
• 8-OHdG: 4.2 ng/mL

This is your first lab entry. Upload future labs to track changes!
```

### 2. User Uploads 3-Month Follow-up Labs
```
User: [sends sarah_chen_3month_labs.txt]

Bot: ✅ Lab results processed (2025-12-15):

⚠️ Significant Changes:
• HbA1c: 5.9 → 6.3% (↑ 6.8%)
• HOMA-IR: 3.7 → 5.4 (↑ 45.9%)
• CRP: 0.7 → 2.1 mg/L (↑ 200.0%)
• 8-OHdG: 4.2 → 8.6 ng/mL (↑ 104.8%)

🚨 Your biomarkers show rapid deterioration!
Running personalized health analysis...

[Bot automatically triggers INDRA analysis]
```

### 3. View Lab History
```
User: /lab_history

Bot: 📋 Lab History (2 entries):

1️⃣ 2025-07-15 (Quest Diagnostics)
   • HbA1c: 5.9%
   • CRP: 0.7 mg/L

2️⃣ 2025-12-15 (LabCorp)
   • HbA1c: 6.3% (↑ 0.4)
   • CRP: 2.1 mg/L (↑ 1.4)

📈 Trend: Worsening metabolic control
```

---

## Production Considerations (Future)

If you want to store original files in production:

1. **Cloud Storage**: Store in AWS S3, Azure Blob, or Google Cloud Storage
2. **File Encryption**: HIPAA compliance requires encrypted storage
3. **Access Controls**: User can only access their own files
4. **Retention Policy**: Delete files after X years
5. **Re-parsing**: Allow re-parsing if extraction logic improves

**Example with S3**:
```python
import boto3

s3 = boto3.client('s3')

async def store_lab_file_s3(user_id: int, file_path: str, collection_date: str):
    """Upload lab file to S3."""
    bucket = 'healthos-lab-results'
    key = f"{user_id}/{collection_date}_{os.path.basename(file_path)}"

    # Upload with encryption
    s3.upload_file(
        file_path,
        bucket,
        key,
        ExtraArgs={'ServerSideEncryption': 'AES256'}
    )

    # Return S3 URL
    return f"s3://{bucket}/{key}"
```

---

## Recommendation for Demo

**Use Option 1 (Parse-Only)** with these features:

✅ Parse `.txt` files and extract biomarker values
✅ Store history in MongoDB as array of entries
✅ Auto-calculate deltas when new labs uploaded
✅ Trigger INDRA analysis if significant deterioration detected
✅ Allow users to view history with `/lab_history` command

❌ Don't store original `.txt` files (demo simplicity)
❌ Don't worry about file encryption (not needed for demo)
❌ Don't implement re-parsing (fixture files can be re-uploaded)

This keeps the demo focused on the health intelligence value proposition rather than file management infrastructure.
