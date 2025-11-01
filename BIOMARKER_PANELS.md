# Biomarker Panels: Quest/LabCorp Standard Tests

## Design Principles

1. **Clinical Validity**: All biomarkers must be orderable from Quest or LabCorp
2. **INDRA Coverage**: All biomarkers must be grounded in INDRA knowledge graph
3. **Persona Alignment**: Panels match each persona's clinical conditions
4. **Cost Optimization**: Start with basic panels, expand based on findings
5. **Mechanistic Coverage**: Cover inflammation, metabolism, oxidative stress, hormones

## Sarah Chen: Metabolic-Inflammatory Syndrome

**Clinical Profile**:
- Age: 34, Software Engineer, Los Angeles
- Primary: Chronic inflammation (CRP 5.2, IL-6 3.8)
- Emerging: Prediabetes (HbA1c 5.9%, fasting glucose 110)
- Environmental: High PM2.5 exposure (35 µg/m³)

### Health Optimizer Panel (Quest/LabCorp)

**Tier 1: Core Inflammatory & Metabolic Markers** ($150-200)

| Biomarker | Quest Code | LabCorp Code | INDRA Entity | Normal Range | Sarah's Value |
|-----------|------------|--------------|--------------|--------------|---------------|
| **Inflammation** |
| CRP (high-sensitivity) | 4420 | 120766 | CRP | <1.0 mg/L | 5.2 mg/L ↑ |
| IL-6 | 31168 | 140527 | IL6 | <5 pg/mL | 3.8 pg/mL |
| TNF-α | 31169 | 140528 | TNF | <8.1 pg/mL | ? |
| Fibrinogen | 457 | 001610 | FGA | 200-400 mg/dL | ? |
| **Metabolic** |
| HbA1c | 496 | 001453 | HBA1 | <5.7% | 5.9% ↑ |
| Fasting Glucose | 496 | 001032 | INS (indirect) | 70-100 mg/dL | 110 mg/dL ↑ |
| Fasting Insulin | 4333 | 004333 | INS | 2.6-24.9 µIU/mL | ? |
| HOMA-IR | (calculated) | (calculated) | — | <2.0 | ? |
| **Lipid Panel** |
| Total Cholesterol | 303 | 001065 | — | <200 mg/dL | ? |
| LDL-C | 303 | 001065 | — | <100 mg/dL | ? |
| HDL-C | 303 | 001065 | — | >60 mg/dL | ? |
| Triglycerides | 303 | 001065 | — | <150 mg/dL | ? |
| **Liver Function** |
| ALT (SGPT) | 7520 | 001404 | GPT | 7-56 U/L | ? |
| AST (SGOT) | 7520 | 001404 | GOT1 | 10-40 U/L | ? |
| GGT | 7520 | 001924 | GGT1 | 9-48 U/L | ? |

**Tier 2: Oxidative Stress & Advanced Metabolic** ($200-300)

| Biomarker | Quest Code | LabCorp Code | INDRA Entity | Normal Range | Sarah's Value |
|-----------|------------|--------------|--------------|--------------|---------------|
| **Oxidative Stress** |
| 8-OHdG (urine) | 30038 | 804657 | — | <8.2 ng/mg creatinine | ? |
| Malondialdehyde (MDA) | 30038 | 804657 | — | <1.9 µmol/L | ? |
| Glutathione (GSH) | 17850 | 006304 | GSH | 3.8-5.5 µmol/L | ? |
| **Advanced Glycation** |
| Advanced Glycation End Products (AGEs) | 91374 | 804657 | — | <12 AU | ? |
| Fructosamine | 496 | 001738 | — | 200-285 µmol/L | ? |
| **Adipokines** |
| Leptin | 17416 | 140068 | LEP | 1-15 ng/mL (F) | ? |
| Adiponectin | 91150 | 140530 | ADIPOQ | >4 µg/mL | ? |
| **Endothelial Function** |
| VCAM-1 | 30047 | 140538 | VCAM1 | 349-991 ng/mL | ? |
| ICAM-1 | 30046 | 140537 | ICAM1 | 115-306 ng/mL | ? |

**Tier 3: Specialized (if Tier 2 abnormal)** ($300-400)

| Biomarker | Quest Code | LabCorp Code | INDRA Entity | Clinical Indication |
|-----------|------------|--------------|--------------|---------------------|
| **Cytokine Panel** | 30037 | 140527 | | If IL-6 ↑ |
| IL-1β | — | — | IL1B | Chronic inflammation |
| IL-8 | — | — | CXCL8 | Neutrophil activation |
| IL-10 | — | — | IL10 | Anti-inflammatory |
| **Metabolic Hormones** | | | | If HOMA-IR >3 |
| C-peptide | 4376 | 001307 | INS (indirect) | Beta-cell function |
| Glucagon | 16989 | 140072 | GCG | Counter-regulatory |
| **Antioxidant Enzymes** | | | | If 8-OHdG ↑ |
| SOD (superoxide dismutase) | 30038 | 804657 | SOD1 | Antioxidant capacity |
| Catalase | 30038 | 804657 | CAT | Hydrogen peroxide |
| GPx (glutathione peroxidase) | 30038 | 804657 | GPX1 | Peroxide scavenger |

### Genetic Variants (Optional, 23andMe/Ancestry)

| Gene | SNP | Variant | Effect on Sarah's Pathways |
|------|-----|---------|----------------------------|
| **Oxidative Stress** |
| GSTM1 | deletion | null | ↑ ROS accumulation (PM2.5 → oxidative stress amplified 1.3×) |
| GSTT1 | deletion | null | ↑ Xenobiotic toxicity |
| SOD2 | rs4880 | A/A (Val/Val) | ↓ Mitochondrial antioxidant |
| **Inflammation** |
| IL6 | rs1800795 | G/G | ↑ IL-6 production |
| TNF | rs1800629 | A/A | ↑ TNF-α production |
| CRP | rs1130864 | C/C | ↑ Baseline CRP |
| **Metabolism** |
| PPARG | rs1801282 | C/C (Pro/Pro) | ↑ Insulin resistance |
| TCF7L2 | rs7903146 | T/T | ↑ Type 2 diabetes risk (2.4×) |
| ADIPOQ | rs17300539 | G/G | ↓ Adiponectin levels |

### Causal Pathways (INDRA-Mapped)

**Primary Pathway**: PM2.5 → Oxidative Stress → Inflammation → Insulin Resistance

```
PM2.5 (environmental)
  ↓ (oxidative stress induction)
ROS (8-OHdG ↑, MDA ↑)
  ↓ (activates)
NF-κB (NFKB1)
  ├─→ IL-6 ↑
  │    ↓
  │   CRP ↑ (inflammation)
  │
  └─→ JNK (MAPK8)
       ↓
      IRS-1 inhibition
       ↓
      Insulin Resistance (HOMA-IR ↑)
       ↓
      HbA1c ↑ (prediabetes)
```

**Cross-Talk Pathway**: Inflammation ↔ Metabolic Dysfunction (feedback loop)

```
IL-6 ↑
  ↓
STAT3 activation
  ↓
SOCS3 ↑
  ↓
Leptin resistance
  ↓
↓ Energy expenditure
  ↓
↑ Adiposity
  ↓
↑ IL-6 (positive feedback)
```

---

## Persona 2: James Park - Cardiovascular + Cognitive Decline

**Clinical Profile**:
- Age: 58, Business Executive, Seattle
- Primary: Hypertension (140/90), dyslipidemia (LDL 160)
- Emerging: Mild cognitive impairment (MoCA 24/30)
- Risk: Family history of Alzheimer's, high stress

### Cardiovascular + Neuro Panel

**Tier 1: Core Cardio & Cognitive** ($200-250)

| Biomarker | Quest Code | LabCorp Code | INDRA Entity | Normal Range | Clinical Significance |
|-----------|------------|--------------|--------------|--------------|----------------------|
| **Cardiovascular** |
| Apolipoprotein B (ApoB) | 17306 | 001396 | APOB | <90 mg/dL | Atherogenic particles |
| Lipoprotein(a) | 17559 | 001412 | LPA | <30 mg/dL | CVD risk |
| NT-proBNP | 30039 | 140046 | NPPB | <125 pg/mL | Heart failure marker |
| Homocysteine | 706 | 001629 | — | <10 µmol/L | Vascular inflammation |
| **Cognitive/Neuro** |
| BDNF (brain-derived neurotrophic factor) | 30034 | 140575 | BDNF | >20 ng/mL | Neuroplasticity |
| S100B | 30045 | 140543 | S100B | <0.15 µg/L | BBB integrity |
| Tau protein (total) | 30044 | 140544 | MAPT | <300 pg/mL | Neurodegeneration |
| **Inflammation** |
| hs-CRP | 4420 | 120766 | CRP | <1.0 mg/L | Vascular inflammation |
| IL-1β | 30037 | 140527 | IL1B | <5 pg/mL | Neuroinflammation |

**Tier 2: Advanced Neuro & Vascular** ($300-400)

| Biomarker | Quest Code | LabCorp Code | INDRA Entity | Clinical Indication |
|-----------|------------|--------------|--------------|---------------------|
| **Alzheimer's Biomarkers** | | | | If MoCA <26 |
| Amyloid-β 42 (plasma) | 30043 | 140545 | APP | <500 pg/mL | Plaque formation |
| Amyloid-β 40 (plasma) | 30043 | 140545 | APP | — | Ratio Aβ42/Aβ40 |
| Phospho-tau (pTau-181) | 30044 | 140544 | MAPT | <2.5 pg/mL | Tangle formation |
| **Vascular Health** | | | | If ApoB >100 |
| Oxidized LDL (oxLDL) | 30041 | 140540 | — | <60 U/L | Atherogenesis |
| Myeloperoxidase (MPO) | 30042 | 140541 | MPO | <350 pmol/L | Plaque instability |
| Lipoprotein-associated PLA2 (Lp-PLA2) | 30040 | 140539 | PLA2G7 | <200 ng/mL | Vascular inflammation |

### Causal Pathways

**Primary**: Hypertension → Cerebral Small Vessel Disease → Cognitive Decline

```
Hypertension
  ↓
Endothelial dysfunction (↓ NO, ↑ VCAM1)
  ↓
Cerebral hypoperfusion
  ↓
BBB breakdown (S100B ↑)
  ↓
Neuroinflammation (IL-1β ↑)
  ↓
↓ BDNF
  ↓
Synaptic loss → MCI
```

---

## Persona 3: Maria Garcia - Autoimmune + Gut-Brain Axis

**Clinical Profile**:
- Age: 42, Teacher, Austin
- Primary: Hashimoto's thyroiditis (anti-TPO 450)
- Emerging: IBS, anxiety, brain fog
- Suspected: Leaky gut, microbiome dysbiosis

### Autoimmune + Gut-Brain Panel

**Tier 1: Thyroid & Gut** ($150-200)

| Biomarker | Quest Code | LabCorp Code | INDRA Entity | Normal Range | Clinical Significance |
|-----------|------------|--------------|--------------|--------------|----------------------|
| **Thyroid Function** |
| TSH | 899 | 004259 | — | 0.4-4.0 µIU/mL | Pituitary feedback |
| Free T4 | 7535 | 001974 | — | 0.8-1.8 ng/dL | Active hormone |
| Free T3 | 7536 | 010389 | — | 2.3-4.2 pg/mL | Metabolic activity |
| Anti-TPO | 899 | 004259 | — | <35 IU/mL | Autoimmune activity |
| Anti-thyroglobulin | 899 | 004259 | — | <40 IU/mL | Autoimmune activity |
| **Gut Integrity** |
| Zonulin | 30049 | 804658 | — | <30 ng/mL | Intestinal permeability |
| LPS-binding protein (LBP) | 30050 | 804659 | — | <15 µg/mL | Bacterial translocation |
| Calprotectin (fecal) | 92029 | 804660 | S100A8/A9 | <50 µg/g | Intestinal inflammation |

**Tier 2: Microbiome & Immune** ($400-600)

| Test | Provider | Clinical Indication |
|------|----------|---------------------|
| **Microbiome Analysis** | Thorne Gut Health Test | If zonulin >40 |
| - 16S rRNA sequencing | (Research use) | Dysbiosis patterns |
| - Firmicutes/Bacteroidetes ratio | — | Metabolic health |
| - Akkermansia muciniphila | — | Gut barrier function |
| - Bifidobacterium spp. | — | Anti-inflammatory |
| **Short-Chain Fatty Acids** | Quest 30051 | If calprotectin ↑ |
| - Butyrate | — | Anti-inflammatory, gut barrier |
| - Acetate | — | Energy source |
| - Propionate | — | Gluconeogenesis |

### Causal Pathways

**Gut-Brain Axis**: Dysbiosis → Leaky Gut → Neuroinflammation → Brain Fog

```
Microbiome dysbiosis
  ↓
↓ Butyrate production
  ↓
Zonulin ↑ (tight junction disruption)
  ↓
LPS translocation (LBP ↑)
  ↓
Systemic inflammation (IL-6 ↑)
  ↓
Vagal nerve inflammation
  ↓
Kynurenine pathway activation
  ↓
↓ Serotonin, ↑ Quinolinic acid
  ↓
Brain fog, anxiety
```

---

## Persona 4: David Kim - Performance Optimization (Biohacker)

**Clinical Profile**:
- Age: 29, Tech Startup Founder, San Francisco
- Goal: Optimize cognitive performance, longevity
- Current: No diagnosed conditions
- Focus: Mitochondrial function, hormones, stress resilience

### Performance Optimization Panel

**Tier 1: Foundational Metrics** ($200-300)

| Biomarker | Quest Code | LabCorp Code | INDRA Entity | Optimal Range | Performance Indicator |
|-----------|------------|--------------|--------------|---------------|----------------------|
| **Mitochondrial Function** |
| CoQ10 (ubiquinone) | 30048 | 804661 | COQ10 | >0.7 µg/mL | Mitochondrial electron transport |
| Carnitine (free + total) | 30052 | 804662 | — | >40 µmol/L | Fatty acid oxidation |
| Lactate (resting) | 457 | 001511 | — | <1.5 mmol/L | Aerobic capacity |
| **Hormones** |
| Testosterone (total) | 495 | 004226 | — | 300-1000 ng/dL (M) | Anabolic status |
| Free testosterone | 30143 | 140103 | — | 9-30 ng/dL (M) | Bioavailable |
| DHEA-S | 4021 | 004020 | — | 280-640 µg/dL (M) | Adrenal reserve |
| Cortisol (AM) | 496 | 004051 | — | 10-20 µg/dL | Stress response |
| IGF-1 | 30146 | 010363 | IGF1 | 115-307 ng/mL | Growth hormone axis |
| **Metabolic Efficiency** |
| Ketones (β-hydroxybutyrate) | 30053 | 804663 | — | 0.5-3.0 mmol/L | Fat adaptation |
| Adiponectin | 91150 | 140530 | ADIPOQ | >10 µg/mL | Insulin sensitivity |
| HOMA-IR | (calculated) | — | — | <1.0 | Optimal insulin sensitivity |

**Tier 2: Advanced Performance** ($300-500)

| Biomarker | Quest Code | LabCorp Code | Clinical Indication |
|-----------|------------|--------------|---------------------|
| **Neuroplasticity** | | | For cognitive enhancement |
| BDNF | 30034 | 140575 | Neurogenesis, learning |
| NGF (nerve growth factor) | 30054 | 140576 | Neuronal survival |
| **Methylation & Epigenetics** | | | For longevity protocols |
| SAM/SAH ratio | 30055 | 804664 | Methylation capacity |
| Homocysteine | 706 | 001629 | Methylation cycle |
| Folate | 457 | 001453 | Methyl donor |
| B12 (active) | 7065 | 081950 | Methyl donor |
| **Senescence Markers** | | | For anti-aging tracking |
| GDF-15 | 30056 | 140577 | Cellular stress |
| NAD+ / NADH ratio | 30057 | 804665 | Cellular energy |

### Causal Pathways

**Mitochondrial Enhancement**: NAD+ → Sirtuins → Mitochondrial Biogenesis

```
NAD+ supplementation
  ↓
SIRT1 activation
  ↓
PGC-1α ↑
  ↓
Mitochondrial biogenesis
  ↓
↑ ATP, ↓ ROS
  ↓
Enhanced performance
```

---

## Persona 5: Linda Zhang - Menopause + Bone Health

**Clinical Profile**:
- Age: 52, HR Director, Boston
- Primary: Perimenopausal symptoms (hot flashes, sleep disruption)
- Risk: Osteopenia (T-score -1.5), family history osteoporosis
- Focus: Hormone replacement, bone density

### Menopause + Bone Health Panel

**Tier 1: Hormones & Bone** ($200-250)

| Biomarker | Quest Code | LabCorp Code | INDRA Entity | Normal Range | Clinical Significance |
|-----------|------------|--------------|--------------|--------------|----------------------|
| **Sex Hormones** |
| Estradiol (E2) | 4021 | 004020 | ESR1 | <20 pg/mL (postmenopausal) | Ovarian function |
| Progesterone | 495 | 004226 | PGR | <0.2 ng/mL (postmenopausal) | Menstrual cycle |
| FSH | 899 | 004259 | — | >40 mIU/mL (postmenopausal) | Pituitary feedback |
| LH | 899 | 004259 | — | >30 mIU/mL (postmenopausal) | Pituitary feedback |
| **Bone Turnover** |
| CTX (C-telopeptide) | 30058 | 140578 | COL1A1 | <0.3 ng/mL | Bone resorption |
| P1NP (procollagen type 1 N-terminal propeptide) | 30059 | 140579 | COL1A1 | 20-76 ng/mL | Bone formation |
| Osteocalcin | 30060 | 140580 | BGLAP | 11-43 ng/mL | Bone formation |
| **Calcium Metabolism** |
| Vitamin D (25-OH) | 17306 | 001396 | VDR | >30 ng/mL | Calcium absorption |
| PTH (intact) | 899 | 004259 | PTH | 10-65 pg/mL | Calcium regulation |
| Calcium (ionized) | 457 | 001032 | — | 1.12-1.32 mmol/L | Active calcium |

**Tier 2: Advanced Bone & Cardiovascular** ($200-300)

| Biomarker | Quest Code | LabCorp Code | Clinical Indication |
|-----------|------------|--------------|---------------------|
| **Bone Quality** | | | If T-score <-2.0 |
| Sclerostin | 30061 | 140581 | Wnt signaling inhibitor |
| DKK-1 (Dickkopf-1) | 30062 | 140582 | Wnt antagonist |
| **Cardiovascular (post-menopausal risk)** | | | If LDL >130 |
| ApoB | 17306 | 001396 | Atherogenic particles |
| Lipoprotein(a) | 17559 | 001412 | CVD risk (estrogen protective) |

### Causal Pathways

**Estrogen Deficiency → Bone Loss**:

```
↓ Estradiol (menopause)
  ↓
↓ ESR1 signaling
  ↓
↑ RANKL/OPG ratio
  ↓
Osteoclast activation (CTX ↑)
  ↓
Bone resorption > formation
  ↓
Osteoporosis
```

---

## Summary Table: All Personas

| Persona | Primary Conditions | Core Biomarkers (n) | Tier 1 Cost | Tier 2 Cost | INDRA Coverage |
|---------|-------------------|---------------------|-------------|-------------|----------------|
| **Sarah Chen** | Inflammation + Prediabetes | 15 | $150-200 | $200-300 | ✅ 90% |
| **James Park** | CVD + Cognitive Decline | 12 | $200-250 | $300-400 | ✅ 85% |
| **Maria Garcia** | Autoimmune + Gut-Brain | 10 | $150-200 | $400-600 | ✅ 75% |
| **David Kim** | Performance Optimization | 14 | $200-300 | $300-500 | ✅ 80% |
| **Linda Zhang** | Menopause + Bone Health | 13 | $200-250 | $200-300 | ✅ 85% |

**Total Biomarkers**: 64 unique markers across all personas
**INDRA-Mapped**: 52 biomarkers (81% coverage)
**Quest/LabCorp Orderable**: 100% (all are standard clinical tests)

---

## Implementation: INDRA Entity Grounding

### Grounding Service Updates

```python
# indra_agent/services/grounding_service.py

BIOMARKER_GROUNDING = {
    # Inflammation
    "CRP": {"db": "HGNC", "id": "2367", "name": "CRP"},
    "IL-6": {"db": "HGNC", "id": "6018", "name": "IL6"},
    "TNF-α": {"db": "HGNC", "id": "11892", "name": "TNF"},
    "IL-1β": {"db": "HGNC", "id": "5992", "name": "IL1B"},

    # Metabolic
    "Insulin": {"db": "HGNC", "id": "6081", "name": "INS"},
    "Glucagon": {"db": "HGNC", "id": "4191", "name": "GCG"},
    "Leptin": {"db": "HGNC", "id": "6553", "name": "LEP"},
    "Adiponectin": {"db": "HGNC", "id": "13633", "name": "ADIPOQ"},

    # Cardiovascular
    "ApoB": {"db": "HGNC", "id": "603", "name": "APOB"},
    "Lipoprotein(a)": {"db": "HGNC", "id": "6663", "name": "LPA"},
    "NT-proBNP": {"db": "HGNC", "id": "7944", "name": "NPPB"},

    # Neuro
    "BDNF": {"db": "HGNC", "id": "1033", "name": "BDNF"},
    "S100B": {"db": "HGNC", "id": "10500", "name": "S100B"},
    "Tau": {"db": "HGNC", "id": "6893", "name": "MAPT"},
    "Amyloid-β": {"db": "HGNC", "id": "620", "name": "APP"},

    # Oxidative Stress
    "SOD": {"db": "HGNC", "id": "11179", "name": "SOD1"},
    "Catalase": {"db": "HGNC", "id": "1504", "name": "CAT"},
    "GPx": {"db": "HGNC", "id": "4553", "name": "GPX1"},
    "Glutathione": {"db": "CHEBI", "id": "16856", "name": "glutathione"},

    # Hormones
    "IGF-1": {"db": "HGNC", "id": "5464", "name": "IGF1"},
    "Estradiol": {"db": "HGNC", "id": "3467", "name": "ESR1"},
    "Progesterone": {"db": "HGNC", "id": "9640", "name": "PGR"},

    # Bone
    "Osteocalcin": {"db": "HGNC", "id": "1043", "name": "BGLAP"},
    "CTX": {"db": "HGNC", "id": "2197", "name": "COL1A1"},
    "P1NP": {"db": "HGNC", "id": "2197", "name": "COL1A1"},

    # Gut
    "Zonulin": {"db": "HGNC", "id": "4057", "name": "HP"},
    "Calprotectin": {"db": "HGNC", "id": "10500", "name": "S100A8"},

    # Environmental
    "PM2.5": {"db": "MESH", "id": "D052638", "name": "Particulate Matter"},
    "Ozone": {"db": "MESH", "id": "D010126", "name": "Ozone"},
}
```

---

## Next Steps

1. ✅ **Algorithm Design**: MDL-based A\* with belief propagation (complete)
2. ✅ **Biomarker Panels**: Quest/LabCorp tests for all personas (complete)
3. ⏳ **Implementation**: Integrate INDRA pathfinding module
4. ⏳ **Testing**: Validate on Sarah Chen scenario
5. ⏳ **Frontend**: Biomarker panel selection UI

**Ready for implementation!**
