# Aeon Cascade - Frontend

Multi-Factor Causal Discovery for Precision Health

## Overview

Aeon Cascade is a SvelteKit-based web application that demonstrates SCM (Structural Causal Model) based causal discovery across diverse biomarker types:

- **Women's Health**: Hormonal, metabolic, bone/mineral, iron/anemia markers
- **Multi-Condition**: Convergent pathways (Type 2 Diabetes + CVD + inflammation)
- **Environmental/Occupational**: Genetic-environmental synergy, circadian disruption
- **Athletic/Performance**: Exercise physiology, myokine responses

## Features

✅ **4 Comprehensive User Personas** with realistic biomarker data
✅ **Interactive Causal Graph Visualization** (Cytoscape.js)
✅ **Convergent Node Detection** for intervention planning
✅ **Temporal Predictions** (3, 6, 12-month trajectories)
✅ **Real-time INDRA Bio-Ontology Integration** via REST API
✅ **Evidence-Based Pathways** backed by scientific literature

## Tech Stack

- **SvelteKit 2.0** - Frontend framework (Svelte 5 runes)
- **TailwindCSS 3.4** - Styling and design system
- **Cytoscape.js 3.30** - Graph visualization
- **TypeScript 5.0** - Type safety
- **Vite 5.0** - Build tool

## Quick Start

### Prerequisites

- Node.js 18+ and npm
- Running INDRA agent backend on `http://localhost:8000`

### Installation

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Open browser
open http://localhost:5173
```

### Production Build

```bash
# Build for production
npm run build

# Preview production build
npm run preview
```

## Project Structure

```
frontend/
├── src/
│   ├── lib/
│   │   ├── components/
│   │   │   ├── ui/                    # Design system primitives
│   │   │   │   ├── Button.svelte
│   │   │   │   ├── Card.svelte
│   │   │   │   ├── Badge.svelte
│   │   │   │   └── Input.svelte
│   │   │   ├── PersonaSelector.svelte # 4-persona grid
│   │   │   ├── BiomarkerDashboard.svelte # Categorized biomarker display
│   │   │   ├── QueryBuilder.svelte    # Pre-filled scenarios + custom queries
│   │   │   ├── CausalGraph.svelte     # Cytoscape.js visualization
│   │   │   ├── InterventionPlanner.svelte # Convergent node targeting
│   │   │   └── TemporalPrediction.svelte  # 12-month biomarker trajectories
│   │   ├── stores/
│   │   │   ├── persona.ts             # Selected persona state
│   │   │   ├── query.ts               # Query & loading state
│   │   │   └── graph.ts               # Causal graph state
│   │   ├── api/
│   │   │   └── indra.ts               # REST API client for indra_agent
│   │   ├── data/
│   │   │   └── personas.ts            # 4 comprehensive personas (722 lines)
│   │   └── types/
│   │       └── models.ts              # TypeScript types matching Pydantic
│   ├── routes/
│   │   ├── +layout.svelte             # Root layout
│   │   └── +page.svelte               # Main application page
│   ├── app.html                       # HTML template
│   └── app.css                        # Tailwind directives + design tokens
├── static/
├── package.json
├── tailwind.config.js
├── svelte.config.js
├── vite.config.ts
└── tsconfig.json
```

## User Personas

### 1. Sarah Chen (Women's Health)
- **Age**: 34, Female
- **Conditions**: Prediabetes, inflammation, perimenopause
- **Biomarkers** (35 total):
  - Hormonal: Estradiol (45 pg/mL - low), FSH (28 - elevated)
  - Metabolic: HbA1c 5.9% (prediabetes), Insulin 18.5 (borderline)
  - Bone/Mineral: Vitamin D 22 (deficient), PTH 58
  - Iron/Anemia: Ferritin 18 (low), Hemoglobin 12.1
- **Scenarios**: Hormonal-inflammatory cross-talk, metabolic-inflammatory feedback

### 2. Michael Torres (Multi-Condition)
- **Age**: 58, Male
- **Conditions**: Type 2 Diabetes, CVD, chronic inflammation
- **Biomarkers** (25 total):
  - Metabolic: HbA1c 8.2% (diabetic), Glucose 178
  - Cardiovascular: LDL 160, Lp(a) 68 (genetic risk)
  - Inflammatory: CRP 8.5, IL-6 12.3, TNF-α 18.5
- **Genetics**: APOE ε4/ε4 (highest CVD risk)
- **Scenarios**: Diabetes-inflammation feedback, convergent CVD pathways

### 3. Priya Patel (Environmental + Occupational)
- **Age**: 42, Female
- **Conditions**: Night shift work, industrial pollution exposure
- **Biomarkers** (20 total):
  - Oxidative: 8-OHdG 38 (severely elevated), Glutathione 450 (depleted)
  - Circadian: Melatonin 8 (severely low), disrupted cortisol rhythm
  - Liver: ALT 42, AST 38, GGT 58 (detox burden)
- **Genetics**: GSTM1/GSTT1 double null (worst detox capacity)
- **Scenarios**: Circadian disruption, environmental-genetic synergy

### 4. James Wilson (Athletic/Performance)
- **Age**: 29, Male
- **Conditions**: Marathon runner (2:45:32 PR)
- **Biomarkers** (25 total):
  - Recovery: Creatine Kinase 580, T/C Ratio 36
  - Inflammatory: IL-6 6.2 (myokine - beneficial), CRP 1.2 (normal)
  - Performance: VO2 Max 68 (elite), HRV 98
- **Genetics**: ACE II (endurance), ACTN3 RR (sprint/power)
- **Scenarios**: Exercise IL-6 vs inflammatory, genetic endurance optimization

## API Integration

The frontend integrates with the INDRA agent backend via REST API:

```typescript
// Example API call
const response = await fetch('http://localhost:8000/api/v1/causal_discovery', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    request_id: crypto.randomUUID(),
    query: { text: 'How does PM2.5 affect CRP?', focus_biomarkers: ['CRP', 'IL-6'] },
    user_context: {
      user_id: 'sarah-chen',
      current_biomarkers: { 'CRP': 5.2, 'IL-6': 3.8 },
      genetics: { 'GSTM1': 'null' },
      location_history: [{ city: 'Los Angeles', avg_pm25: 42.3 }]
    },
    options: { max_graph_depth: 5, include_genetic_modifiers: true }
  })
});
```

## Design System

### Colors

- **Primary**: Blue (#3b82f6) - Actions, links
- **Node Types**:
  - Environmental: Purple (#8b5cf6)
  - Molecular: Cyan (#06b6d4)
  - Biomarker: Pink (#ec4899)
  - Genetic: Orange (#f97316)
- **Edge Types**:
  - Activates: Green (#10b981)
  - Inhibits: Red (#ef4444)
  - Increases: Blue (#3b82f6)
  - Decreases: Orange (#f59e0b)

### Typography

- **Font**: Inter (sans-serif)
- **Headings**: 700 weight, hierarchical sizing
- **Body**: 400 weight, 16px base

## Development

### Running Backend

The frontend requires the INDRA agent backend running:

```bash
# In parent directory
cd /Users/noot/Documents/digitalme
uv run python -m indra_agent.main

# Backend should be accessible at http://localhost:8000
```

### Environment Variables

Set in `vite.config.ts`:
- API proxy configured to forward `/api` requests to `http://localhost:8000`

## Deployment

### Static Export (SvelteKit Adapter)

For production deployment, build and serve the static output:

```bash
npm run build
# Output in: frontend/build/

# Serve with any static host (Vercel, Netlify, Cloudflare Pages, etc.)
```

## Testing Scenarios

### Test 1: Sarah Chen - Hormonal-Inflammatory Cross-Talk
1. Select Sarah Chen persona
2. Click scenario: "Hormonal-Inflammatory Cross-Talk"
3. Verify graph shows: Estradiol → NF-κB → IL-6 → CRP
4. Check intervention planner suggests NF-κB targeting

### Test 2: Michael Torres - Multi-Condition Convergence
1. Select Michael Torres persona
2. Query: "What shared mechanisms drive my diabetes and cardiovascular disease?"
3. Verify convergent nodes: IRS-1, NF-κB, oxidative stress
4. Check synergy scores ≥ 1.3

### Test 3: Priya Patel - Environmental-Genetic Synergy
1. Select Priya Patel persona
2. Query: "How do my GSTM1/GSTT1 null variants amplify PM2.5 toxicity?"
3. Verify genetic modifiers applied (effect sizes amplified by 1.3×)
4. Check oxidative stress biomarkers (8-OHdG, MDA) in graph

### Test 4: James Wilson - Exercise Myokine Response
1. Select James Wilson persona
2. Query: "Why is my IL-6 elevated but CRP normal?"
3. Verify IL-6 → IL-10 anti-inflammatory pathway
4. Check temporal predictions show beneficial IL-6 response

## Troubleshooting

**Issue**: `npm install` fails with Svelte version conflicts
**Fix**: Ensure using Node.js 18+ and run `npm cache clean --force`

**Issue**: Cytoscape graph not rendering
**Fix**: Check browser console for errors, verify `<div>` container has dimensions

**Issue**: API calls failing
**Fix**: Ensure backend is running on `http://localhost:8000`, check CORS settings

**Issue**: TypeScript errors in Svelte components
**Fix**: Install `@sveltejs/vite-plugin-svelte` dev dependency

## License

Aeon Cascade © 2025 - Built with SvelteKit, INDRA Bio-Ontology, and AWS Bedrock
