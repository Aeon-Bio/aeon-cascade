# healthOS Demo Flow: User Uploads → Bot Processing → INDRA Agent

## What Users Upload (Via Telegram)

Users upload **raw data files only**. The bot handles everything else.

### 3 Upload Types

1. **📍 Location** - Share via Telegram location button OR upload JSON
   - File: `sarah_chen_location_history.json` (demo)
   - Real usage: Telegram location sharing provides `latitude`/`longitude`
   - Bot enriches with PM2.5 data from air quality APIs

2. **🧬 Genetics** - Upload VCF file
   - File: `sarah_chen_genetics.vcf`
   - Standard VCF format from 23andMe, AncestryDNA, etc.
   - Bot parses variants and stores in MongoDB

3. **📋 Lab Results** - Upload text lab reports
   - Files: `sarah_chen_baseline_labs.txt`, `sarah_chen_3month_labs.txt`
   - Standard Quest/LabCorp plain text format
   - Bot extracts biomarker values and stores in MongoDB

## What Users DON'T Upload

❌ Users do **NOT** upload:
- JSON request payloads
- Biomarker JSON files (bot creates these from lab text)
- Environmental data JSON (bot fetches from APIs)
- Pre-constructed INDRA requests

## Bot Processing Flow

```
User Upload          Bot Processing              MongoDB Storage           INDRA Agent
───────────          ──────────────              ───────────────           ───────────

📍 Location      →   Parse lat/lon           →   health_location_history
(Telegram)           Reverse geocode
                     Fetch PM2.5 data

🧬 VCF File      →   Parse variants          →   health_genetics
                     Map to gene names

📋 Lab TXT       →   Regex extract           →   health_biomarkers_history
                     biomarker values             (array of entries)


User Query       →   Build INDRA Request     →   [Read all data]       →   Process Request
"How will LA         CausalDiscoveryRequest                              Entity grounding
affect my            {                                                   Path discovery
diabetes risk?"        user_context: {                                   Graph building
                         genetics: {...},                                Explanations
                         biomarkers: {...},
                         location_history: [...]
                       },
                       query: {...}
                     }

                                                                      ←   CausalDiscoveryResponse
                                                                          Causal graph
                                                                          Interventions
                     Format Response         ←
                     for Telegram

User receives    ←   Telegram message
formatted result     with graphs, insights
```

## Demo File Usage

### User Uploads These Files:

| File | Purpose | Upload Method |
|------|---------|---------------|
| `sarah_chen_genetics.vcf` | Genetic risk factors | Telegram document upload |
| `sarah_chen_baseline_labs.txt` | SF baseline biomarkers | Telegram document upload |
| `sarah_chen_3month_labs.txt` | LA 3-month biomarkers | Telegram document upload |
| `sarah_chen_location_history.json` | SF→LA relocation (demo) | Telegram document upload |

**OR** for location in real usage:
- Telegram location share button (provides lat/lon automatically)

### Bot Uses These Internally (Not User-Facing):

| File | Purpose | Usage |
|------|---------|-------|
| `sarah_chen_biomarkers.json` | Structured biomarker data | Created by bot from .txt parsing |
| `sarah_chen_environmental_data.json` | Daily PM2.5 measurements | Fetched from EPA/IQAir APIs |
| `sample_indra_request.json` | Complete INDRA request | Constructed by bot from user data |
| `sample_indra_request_3month.json` | Follow-up INDRA request | Constructed by bot from user data |

## Example Demo Session

### Step 1: Upload Genetics
```
User: [uploads sarah_chen_genetics.vcf]

Bot: 🧬 Genetic data uploaded:
     • GSTM1: null/null (impaired detoxification)
     • TCF7L2: C/T (1.4× diabetes risk)
     • TNF_alpha: G/A (increased inflammation)

     ✅ Stored in your health profile
```

**Behind the scenes:**
```python
# Bot parses VCF
genetics = parse_vcf(file_path)
# → {'GSTM1': 'null/null', 'TCF7L2': 'C/T', ...}

# Store in MongoDB
db.set_user_attribute(user_id, 'health_genetics', genetics)
```

### Step 2: Share Location
```
User: [shares location: SF (37.7599, -122.4148)]

Bot: 📍 Location saved: San Francisco, CA
     Air Quality: PM2.5 = 7.8 µg/m³ (Good)

     ✅ Added to your location history
```

**Behind the scenes:**
```python
# Bot receives Telegram location
lat, lon = update.message.location.latitude, update.message.location.longitude

# Reverse geocode
city = reverse_geocode(lat, lon)
# → "San Francisco, CA"

# Fetch air quality
pm25 = fetch_air_quality(lat, lon)
# → 7.8 µg/m³

# Store in MongoDB
location_history = [
    {
        "city": "San Francisco, CA",
        "start_date": "2025-07-15",
        "end_date": None,
        "avg_pm25": 7.8
    }
]
db.set_user_attribute(user_id, 'health_location_history', location_history)
```

### Step 3: Upload Lab Results
```
User: [uploads sarah_chen_baseline_labs.txt]

Bot: ✅ Lab results processed (2025-07-15):

     📊 Biomarkers detected:
     • HbA1c: 5.9% (prediabetes)
     • Glucose: 105 mg/dL
     • CRP: 0.7 mg/L
     • IL-6: 1.1 pg/mL
     • 8-OHdG: 4.2 ng/mL

     This is your first lab entry.
     Upload future labs to track changes!
```

**Behind the scenes:**
```python
# Bot reads file
with open(file_path, 'r') as f:
    content = f.read()

# Extract biomarkers via regex
biomarkers = extract_biomarkers(content)
# → {'HbA1c': 5.9, 'CRP': 0.7, 'IL-6': 1.1, ...}

# Store in MongoDB
biomarker_history = [
    {
        "collection_date": "2025-07-15",
        "lab": "Quest Diagnostics",
        "values": biomarkers
    }
]
db.set_user_attribute(user_id, 'health_biomarkers_history', biomarker_history)
```

### Step 4: Ask Health Question
```
User: "How will moving to LA affect my diabetes risk?"

Bot: 🧬 Running personalized health analysis...
     (takes 5-10 seconds)

     📊 Health Intelligence Report

     Your genetic profile (GSTM1 null) creates vulnerability to
     oxidative stress. Moving to LA will increase PM2.5 exposure
     by 342% (7.8 → 34.5 µg/m³).

     ⚠️ Predicted Impact (6 months):
     • HbA1c: 5.9% → 6.3% (+0.4%)
     • Risk of diabetes diagnosis: 65%

     🔬 Causal Analysis:
     Based on 312 scientific papers

     Top pathway:
     PM2.5 ⬆️ Oxidative Stress ⬆️ IL-6 ⬆️ CRP

     💡 Recommendations:
     1. NAC supplementation (compensates GSTM1 deficiency)
     2. HEPA filtration (reduces indoor PM2.5 by 70%)
     3. Monitor HbA1c monthly after move
```

**Behind the scenes:**
```python
# Bot detects health query
if is_health_query(message_text):

    # Read all user data from MongoDB
    genetics = db.get_user_attribute(user_id, 'health_genetics')
    biomarker_history = db.get_user_attribute(user_id, 'health_biomarkers_history')
    location_history = db.get_user_attribute(user_id, 'health_location_history')

    # Get most recent biomarkers
    current_biomarkers = biomarker_history[-1]['values']

    # Construct INDRA request
    request = CausalDiscoveryRequest(
        request_id=str(uuid.uuid4()),
        user_context=UserContext(
            user_id=str(user_id),
            genetics=genetics,
            current_biomarkers=current_biomarkers,
            location_history=location_history
        ),
        query=Query(text=message_text),
        options=RequestOptions()
    )

    # Call INDRA agent (direct Python import)
    response = await indra_client.process_request(request)

    # Format for Telegram
    formatted = format_indra_response(response)
    await update.message.reply_text(formatted)
```

## Summary: Three File Types Only

### ✅ What Users Upload (Demo):

1. **VCF genetics** (`sarah_chen_genetics.vcf`) - 1.5 KB
2. **Lab results TXT** (`sarah_chen_baseline_labs.txt`) - 9 KB
3. **Lab results TXT** (`sarah_chen_3month_labs.txt`) - 17 KB
4. **Location JSON** (`sarah_chen_location_history.json`) - 3 KB **OR** Telegram location share

### ❌ What Users DON'T See:

- `sarah_chen_biomarkers.json` - Bot creates this from TXT parsing
- `sarah_chen_environmental_data.json` - Bot fetches from APIs
- `sample_indra_request.json` - Bot constructs this internally
- `sample_indra_request_3month.json` - Bot constructs this internally

### 🤖 Bot Handles Everything Else:

- Parsing VCF → genetics dict
- Parsing lab TXT → biomarker values
- Reverse geocoding lat/lon → city names
- Fetching PM2.5 from air quality APIs
- Constructing INDRA requests
- Formatting INDRA responses for Telegram

**This keeps the demo simple: users just upload their raw data files, and healthOS does the rest!**
