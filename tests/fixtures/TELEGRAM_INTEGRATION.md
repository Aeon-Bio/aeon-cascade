# Telegram Bot Integration Guide for healthOS

This document describes how location data and lab results are collected from users via the Telegram bot and integrated into the INDRA health intelligence system.

## Telegram Location Data Format

### Location Object Structure

When a user shares their location via Telegram, the bot receives a `telegram.Location` object:

```python
# healthos_bot/bot/bot.py - Location handler example

async def location_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle location sharing from users."""
    user_location = update.message.location

    # Access location data
    latitude = user_location.latitude      # float (e.g., 37.7599)
    longitude = user_location.longitude    # float (e.g., -122.4148)

    # Optional fields (may be None)
    horizontal_accuracy = user_location.horizontal_accuracy  # Radius in meters (0-1500)
    live_period = user_location.live_period                  # Seconds for live location
    heading = user_location.heading                          # Direction in degrees (1-360)
    proximity_alert_radius = user_location.proximity_alert_radius  # Meters
```

### Real-World Example Data

**San Francisco Mission District** (Sarah's baseline):
```python
{
    "latitude": 37.7599,
    "longitude": -122.4148,
    "horizontal_accuracy": 15.5  # meters
}
```

**Los Angeles Westwood** (Sarah's relocation):
```python
{
    "latitude": 34.0633,
    "longitude": -118.4456,
    "horizontal_accuracy": 12.3
}
```

### Storing Location History in MongoDB

```python
# healthos_bot/bot/bot.py

async def location_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_location = update.message.location

    # Get current location history from DB
    location_history = db.get_user_attribute(user_id, 'health_location_history') or []

    # Reverse geocode to get city name (using geopy or similar)
    city_name = await reverse_geocode(user_location.latitude, user_location.longitude)

    # Get air quality data for location (using IQAir API or similar)
    air_quality = await fetch_air_quality(user_location.latitude, user_location.longitude)

    # Create new location entry
    new_location = {
        "city": city_name,
        "latitude": user_location.latitude,
        "longitude": user_location.longitude,
        "start_date": datetime.now().strftime("%Y-%m-%d"),
        "end_date": None,  # Open-ended until next location
        "avg_pm25": air_quality.get('pm25', 0.0),
        "avg_pm10": air_quality.get('pm10', 0.0),
        "avg_ozone": air_quality.get('ozone', 0.0),
        "horizontal_accuracy": user_location.horizontal_accuracy
    }

    # Close previous location's end_date if exists
    if location_history:
        location_history[-1]['end_date'] = datetime.now().strftime("%Y-%m-%d")

    # Append new location
    location_history.append(new_location)

    # Save to MongoDB
    db.set_user_attribute(user_id, 'health_location_history', location_history)

    # Confirm to user
    await update.message.reply_text(
        f"📍 Location saved: {city_name}\n"
        f"Air Quality: PM2.5 = {air_quality['pm25']:.1f} µg/m³\n"
        f"This will be used for personalized health analysis."
    )
```

### Temporary JSON Format (Demo)

For the demo, location history can be uploaded as JSON:

```json
{
  "location_history": [
    {
      "city": "San Francisco, CA",
      "latitude": 37.7599,
      "longitude": -122.4148,
      "start_date": "2020-01-15",
      "end_date": "2025-08-31",
      "avg_pm25": 7.8,
      "avg_pm10": 18.2,
      "avg_ozone": 0.042
    },
    {
      "city": "Los Angeles, CA",
      "latitude": 34.0633,
      "longitude": -118.4456,
      "start_date": "2025-09-01",
      "end_date": null,
      "avg_pm25": 34.5,
      "avg_pm10": 58.1,
      "avg_ozone": 0.089
    }
  ]
}
```

**How to upload via Telegram**:
```
/upload_location
[User sends JSON file as document]
Bot: "✅ Location history uploaded! 2 locations added to your profile."
```

## Lab Results Integration

### Supported Formats

The bot accepts lab results in **plain text format** (Quest Diagnostics, LabCorp standard output):

**File formats accepted**:
- `.txt` (preferred - Quest/LabCorp text reports)
- `.pdf` (future - requires OCR parsing)

### Text File Upload Flow

```python
# healthos_bot/bot/bot.py - Document handler

async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle file uploads (lab results, location data, VCF genetics)."""
    user_id = update.message.from_user.id
    document = update.message.document

    # Download file
    file = await context.bot.get_file(document.file_id)
    file_path = f"/tmp/{document.file_name}"
    await file.download_to_drive(file_path)

    # Detect file type
    if document.file_name.endswith('.txt'):
        # Parse lab results
        if 'lab' in document.file_name.lower() or 'quest' in document.file_name.lower():
            await parse_lab_results(user_id, file_path, update)
        else:
            await update.message.reply_text("❓ Unknown text file type.")

    elif document.file_name.endswith('.vcf'):
        # Parse genetic data
        await parse_vcf_genetics(user_id, file_path, update)

    elif document.file_name.endswith('.json'):
        # Parse JSON (location history or other structured data)
        await parse_json_data(user_id, file_path, update)

    else:
        await update.message.reply_text(
            "❌ Unsupported file format.\n"
            "Accepted: .txt (lab results), .vcf (genetics), .json (location data)"
        )
```

### Lab Results Parsing

```python
async def parse_lab_results(user_id: int, file_path: str, update: Update):
    """Parse Quest/LabCorp text lab results."""

    with open(file_path, 'r') as f:
        content = f.read()

    # Extract key biomarkers using regex patterns
    biomarkers = {}

    # HbA1c pattern: "Hemoglobin A1c    5.9    %"
    hba1c_match = re.search(r'Hemoglobin A1c\s+(\d+\.\d+)\s*%', content)
    if hba1c_match:
        biomarkers['HbA1c'] = float(hba1c_match.group(1))

    # Glucose pattern: "Glucose, Fasting    105    mg/dL"
    glucose_match = re.search(r'Glucose,?\s+Fasting\s+(\d+)\s*mg/dL', content)
    if glucose_match:
        biomarkers['fasting_glucose'] = float(glucose_match.group(1))

    # CRP pattern: "C-Reactive Protein (hs)    0.7    mg/L"
    crp_match = re.search(r'C-Reactive Protein.*?\s+(\d+\.\d+)\s*mg/L', content)
    if crp_match:
        biomarkers['CRP'] = float(crp_match.group(1))

    # IL-6 pattern: "Interleukin-6 (IL-6)    1.1    pg/mL"
    il6_match = re.search(r'Interleukin-6.*?\s+(\d+\.\d+)\s*pg/mL', content)
    if il6_match:
        biomarkers['IL-6'] = float(il6_match.group(1))

    # 8-OHdG pattern: "8-OHdG (Urine)    4.2    ng/mL"
    ohdg_match = re.search(r'8-OHdG.*?\s+(\d+\.\d+)\s*ng/mL', content)
    if ohdg_match:
        biomarkers['8-OHdG'] = float(ohdg_match.group(1))

    # Extract collection date
    date_match = re.search(r'Collection Date:\s+(\d{4}-\d{2}-\d{2})', content)
    collection_date = date_match.group(1) if date_match else None

    # Store in MongoDB
    db.set_user_attribute(user_id, 'health_biomarkers', biomarkers)
    db.set_user_attribute(user_id, 'health_biomarkers_date', collection_date)

    # Confirm to user with summary
    summary = f"✅ Lab results processed ({collection_date}):\n\n"
    for marker, value in biomarkers.items():
        summary += f"• {marker}: {value}\n"

    await update.message.reply_text(summary)

    # Auto-trigger health analysis if location history exists
    location_history = db.get_user_attribute(user_id, 'health_location_history')
    if location_history:
        await update.message.reply_text(
            "🧬 Running personalized health analysis with your data...\n"
            "This may take a few seconds."
        )
        # Trigger INDRA analysis automatically
        await trigger_indra_analysis(user_id, update)
```

### Genetic Data (VCF) Parsing

```python
async def parse_vcf_genetics(user_id: int, file_path: str, update: Update):
    """Parse VCF genetic variant file."""

    genetics = {}

    with open(file_path, 'r') as f:
        for line in f:
            if line.startswith('#'):
                continue  # Skip header lines

            fields = line.strip().split('\t')
            if len(fields) < 10:
                continue

            variant_id = fields[2]  # rsID or variant name
            genotype = fields[9].split(':')[0]  # GT field (e.g., "0/1", "1/1")

            # Map specific variants to gene names
            if variant_id == 'GSTM1_DEL' and genotype == '1/1':
                genetics['GSTM1'] = 'null/null'
            elif variant_id == 'rs1695' and genotype == '1/1':
                genetics['GSTP1'] = 'Val/Val'
            elif variant_id == 'rs1800629' and genotype == '0/1':
                genetics['TNF_alpha'] = 'G/A'
            elif variant_id == 'rs4880' and genotype == '1/1':
                genetics['SOD2'] = 'Ala/Ala'
            elif variant_id == 'rs7903146' and genotype == '0/1':
                genetics['TCF7L2'] = 'C/T'
            elif variant_id == 'rs1801133' and genotype == '0/1':
                genetics['MTHFR'] = 'C/T'

    # Store in MongoDB
    db.set_user_attribute(user_id, 'health_genetics', genetics)

    # Confirm to user
    summary = f"🧬 Genetic data uploaded:\n\n"
    for gene, variant in genetics.items():
        summary += f"• {gene}: {variant}\n"

    await update.message.reply_text(summary)
```

## User Commands for Health Data

### Available Commands

```
/health_upload - Upload health data (lab results, genetics, location)
/health_status - View your stored health profile
/health_analyze - Run INDRA health analysis with your data
/health_clear - Clear all health data from your profile
```

### Command Implementations

```python
async def health_upload_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Initiate health data upload."""
    await update.message.reply_text(
        "📤 **Upload Health Data**\n\n"
        "Send me one of the following:\n\n"
        "📋 **Lab Results** (.txt file from Quest/LabCorp)\n"
        "🧬 **Genetic Data** (.vcf file from 23andMe, AncestryDNA, etc.)\n"
        "📍 **Location** (Share location button OR .json file)\n\n"
        "Example files available at:\n"
        "tests/fixtures/sarah_chen_*.txt|vcf|json",
        parse_mode=ParseMode.MARKDOWN
    )

async def health_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's stored health profile."""
    user_id = update.message.from_user.id

    genetics = db.get_user_attribute(user_id, 'health_genetics') or {}
    biomarkers = db.get_user_attribute(user_id, 'health_biomarkers') or {}
    location_history = db.get_user_attribute(user_id, 'health_location_history') or []

    status = "👤 **Your Health Profile**\n\n"

    if genetics:
        status += "🧬 **Genetics:**\n"
        for gene, variant in genetics.items():
            status += f"  • {gene}: {variant}\n"
        status += "\n"
    else:
        status += "🧬 Genetics: _Not uploaded_\n\n"

    if biomarkers:
        status += "📊 **Current Biomarkers:**\n"
        for marker, value in biomarkers.items():
            status += f"  • {marker}: {value}\n"
        date = db.get_user_attribute(user_id, 'health_biomarkers_date')
        if date:
            status += f"  📅 Collection Date: {date}\n"
        status += "\n"
    else:
        status += "📊 Biomarkers: _Not uploaded_\n\n"

    if location_history:
        status += "📍 **Location History:**\n"
        for loc in location_history:
            period = f"{loc['start_date']} to {loc['end_date'] or 'present'}"
            status += f"  • {loc['city']} ({period})\n"
            status += f"    PM2.5: {loc['avg_pm25']} µg/m³\n"
        status += "\n"
    else:
        status += "📍 Location History: _Not uploaded_\n\n"

    if not (genetics or biomarkers or location_history):
        status += "ℹ️ _No health data uploaded yet._\n"
        status += "Use /health_upload to get started!"
    else:
        status += "✅ Ready for personalized health analysis!\n"
        status += "Use /health_analyze to run INDRA analysis."

    await update.message.reply_text(status, parse_mode=ParseMode.MARKDOWN)

async def health_analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Trigger INDRA health analysis with user's data."""
    user_id = update.message.from_user.id

    # Check if user has sufficient data
    genetics = db.get_user_attribute(user_id, 'health_genetics')
    biomarkers = db.get_user_attribute(user_id, 'health_biomarkers')
    location_history = db.get_user_attribute(user_id, 'health_location_history')

    if not (genetics or biomarkers or location_history):
        await update.message.reply_text(
            "❌ No health data found.\n"
            "Please upload your data first using /health_upload"
        )
        return

    await update.message.reply_text(
        "🧬 **Running Personalized Health Analysis**\n\n"
        "Analyzing your genetics, biomarkers, and environmental exposures...\n"
        "This may take 10-20 seconds."
    )

    # Trigger INDRA analysis
    await trigger_indra_analysis(user_id, update)
```

## Data Flow Summary

```
User Action                  Telegram Bot                  MongoDB                 INDRA Agent
───────────                  ────────────                  ───────                 ───────────

1. Share Location      →     location_handler()      →     health_location_history
                             - Reverse geocode
                             - Fetch air quality

2. Upload Lab (.txt)   →     document_handler()      →     health_biomarkers
                             - Parse text                   health_biomarkers_date
                             - Extract values

3. Upload Genetics     →     document_handler()      →     health_genetics
   (.vcf)                    - Parse VCF
                             - Map variants

4. /health_analyze     →     health_analyze_cmd()    →     [Read all data]      →  INDRA Query
                             - Build request                                       - Entity grounding
                             - Call INDRA client                                   - Path discovery
                                                                                   - Graph building

5. Receive Response    ←     format_indra_response() ←                          ←  CausalDiscoveryResponse
                             - Format for Telegram                                 - Causal graph
                             - Send to user                                        - Explanations
```

## Example User Journey

### Sarah Chen Demo Flow

1. **Upload Genetics** (via VCF file):
```
User: [sends sarah_chen_genetics.vcf]
Bot: 🧬 Genetic data uploaded:
     • GSTM1: null/null
     • GSTP1: Val/Val
     • TNF_alpha: G/A
     • SOD2: Ala/Ala
     • TCF7L2: C/T
     • MTHFR: C/T
```

2. **Upload Baseline Labs** (via text file):
```
User: [sends sarah_chen_baseline_labs.txt]
Bot: ✅ Lab results processed (2025-07-15):
     • HbA1c: 5.9
     • fasting_glucose: 105
     • CRP: 0.7
     • IL-6: 1.1
     • 8-OHdG: 4.2
```

3. **Share Location** (San Francisco):
```
User: [shares location via Telegram]
Bot: 📍 Location saved: San Francisco, CA
     Air Quality: PM2.5 = 7.8 µg/m³
     This will be used for personalized health analysis.
```

4. **User Asks Health Question**:
```
User: "How will moving to LA affect my diabetes risk?"

Bot: [Detects health query, calls INDRA]

🧬 Health Intelligence Report

📊 Key Insights:
1. Your genetic profile (GSTM1 null) creates vulnerability to oxidative stress
2. Moving to LA will increase PM2.5 exposure by 342% (7.8 → 34.5 µg/m³)
3. Predicted HbA1c increase: 5.9% → 6.3% within 3 months
4. Diabetes risk increases from 40% to 65% without intervention

🔬 Causal Analysis:
Based on 312 scientific papers analyzing PM2.5 → inflammation → metabolic dysfunction

🔗 Top Causal Pathways:
  PM2.5 ⬆️ Oxidative Stress
  Effect: 0.82, Evidence: 47 papers, Lag: 2h

  Oxidative Stress ⬆️ IL-6
  Effect: 0.87, Evidence: 89 papers, Lag: 12h

  IL-6 ⬆️ CRP
  Effect: 0.98, Evidence: 312 papers, Lag: 6h

💡 Personalized Recommendations:
1. NAC supplementation (1200mg/day) - compensates GSTM1 deficiency
2. HEPA filtration (reduces indoor PM2.5 by 70%)
3. Monitor HbA1c monthly after relocation
```

5. **3 Months Later** - Upload Follow-up Labs:
```
User: [sends sarah_chen_3month_labs.txt]
Bot: ✅ Lab results processed (2025-12-15):
     • HbA1c: 6.3 (+0.4 from baseline) ⚠️
     • CRP: 2.1 (+200% increase) ⚠️
     • 8-OHdG: 8.6 (DOUBLED) ⚠️

⚠️ Your biomarkers have deteriorated as predicted.
Running updated analysis...

[Triggers automatic INDRA analysis showing intervention recommendations]
```

## File Structure for Demo

```
tests/fixtures/
├── sarah_chen_genetics.vcf              # Upload via Telegram
├── sarah_chen_baseline_labs.txt         # Upload via Telegram (July 2025)
├── sarah_chen_3month_labs.txt           # Upload via Telegram (Dec 2025)
├── sarah_chen_location_history.json     # Upload OR share location live
└── sarah_chen_environmental_data.json   # Backend reference (not user-facing)
```

## Technical Implementation Notes

### MongoDB Schema

```javascript
// User health data structure
{
  "user_id": 12345,
  "health_genetics": {
    "GSTM1": "null/null",
    "TCF7L2": "C/T"
  },
  "health_biomarkers": {
    "HbA1c": 5.9,
    "CRP": 0.7,
    "IL-6": 1.1,
    "8-OHdG": 4.2
  },
  "health_biomarkers_date": "2025-07-15",
  "health_location_history": [
    {
      "city": "San Francisco, CA",
      "latitude": 37.7599,
      "longitude": -122.4148,
      "start_date": "2020-01-15",
      "end_date": "2025-08-31",
      "avg_pm25": 7.8
    },
    {
      "city": "Los Angeles, CA",
      "latitude": 34.0633,
      "longitude": -118.4456,
      "start_date": "2025-09-01",
      "end_date": null,
      "avg_pm25": 34.5
    }
  ]
}
```

### Air Quality API Integration

For real-time PM2.5 data from coordinates:

```python
import aiohttp

async def fetch_air_quality(lat: float, lon: float) -> dict:
    """Fetch air quality data from IQAir API."""
    api_key = os.getenv('IQAIR_API_KEY')
    url = f"http://api.airvisual.com/v2/nearest_city?lat={lat}&lon={lon}&key={api_key}"

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()

            if data['status'] == 'success':
                pollution = data['data']['current']['pollution']
                return {
                    'pm25': pollution['aqius'],  # US AQI
                    'pm10': pollution.get('aqicn', 0),
                    'timestamp': pollution['ts']
                }

    return {'pm25': 0.0, 'pm10': 0.0, 'ozone': 0.0}
```

---

## Demo Testing Checklist

- [ ] Test location sharing via Telegram (manual)
- [ ] Test lab results upload (.txt file)
- [ ] Test VCF genetics upload (.vcf file)
- [ ] Test JSON location history upload (.json file)
- [ ] Test `/health_status` command shows all data
- [ ] Test `/health_analyze` triggers INDRA with personalized context
- [ ] Test automatic analysis trigger after lab upload
- [ ] Verify MongoDB stores all data correctly
- [ ] Verify INDRA receives complete UserContext with genetics, biomarkers, location

---

**Last Updated**: 2025-10-17
**Integration Status**: healthOS Telegram bot with INDRA agent (direct Python import)
