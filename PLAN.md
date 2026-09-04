# Startup Diagnostic Platform — MVP Plan

AI-driven strategy & financial diagnostics for early-stage founders.
Based on validation report verdict: **GO / PROMISING (78)**.

## MVP Scope (focused per report recommendation)

The report's #1 action item: *Focus MVP on 1-2 critical financial diagnostic features.*
Founders ranked **unit economics analysis** and **runway projections** as top features.

### In scope (this MVP)
1. **Diagnostic Wizard** — founder describes their idea + enters basic financials
   (customers/mo, price, CAC, monthly costs, cash on hand).
2. **Unit Economics Engine** — deterministic, transparent calculations:
   - Gross margin & contribution margin
   - CAC, LTV, LTV:CAC ratio (benchmarks: <3 risky, ≥3 healthy)
   - Monthly burn rate & runway (months)
   - Break-even customers
3. **Idea Scorecard** — heuristic scoring across 6 dimensions
   (problem-solution fit, market clarity, feasibility, timing, competition, value prop).
4. **Explainability Panel** (the differentiator) — every score shows its formula,
   inputs used, and benchmark comparison. No black box.
5. **AI Narrative** (optional, env-keyed) — OpenAI-compatible API turns numbers
   into plain-language diagnosis + top 3 actions.
6. **Landing page** with waitlist capture (report quick win #1).

### Out of scope (later phases)
- Auth & saved ideas (Supabase) → Phase 2
- Payments/tiers ($29 / $99 / $499 per report pricing test) → Phase 2
- PDF export, integrations (QuickBooks/Xero), accelerators portal → Phase 3

## Architecture

```
Next.js 15 (App Router, TS, Tailwind)
├─ src/lib/engine/          ← pure functions, fully unit-testable
│   ├─ unitEconomics.ts     CAC/LTV/runway/burn/break-even
│   ├─ scoring.ts           6-dimension idea scorecard
│   └─ benchmarks.ts        thresholds from industry data
├─ src/app/api/
│   ├─ diagnose/route.ts    POST: inputs → full diagnostic JSON
│   └── waitlist/route.ts   POST: email capture (JSON file store for MVP)
├─ src/app/page.tsx         Landing + waitlist
├─ src/app/diagnose/page.tsx  Wizard (multi-step form)
└─ src/app/report/page.tsx   Dashboard: scores, charts, explainability
```

No backend server needed for MVP — engine runs client/server-side in Next.js.
State passed via URL params/sessionStorage between wizard → report.

## Key formulas (transparent by design)

| Metric | Formula | Healthy |
|---|---|---|
| CAC | marketing spend ÷ new customers | context |
| LTV | ARPU × gross margin % ÷ churn rate | — |
| LTV:CAC | LTV ÷ CAC | ≥ 3:1 |
| Runway | cash ÷ net monthly burn | > 12 mo |
| Break-even units | fixed costs ÷ contribution margin/unit | achievable |

## Milestones (mapped to report's execution horizon)

| When | Deliverable | Success metric |
|---|---|---|
| Week 1 | Engine + landing page live | 100+ waitlist signups / 2 wks |
| Week 2 | Wizard + report dashboard | 20+ complete diagnostics |
| Week 3 | AI narrative + explainability polish | >70% trust in survey |
| Week 4 | Save results, shareable link | 3+ founders say they'd pay |
| Month 2 | Auth (Supabase) + Stripe test tier | Conversion >2% |

## Pricing hypothesis to test (from report)
- Basic $29/mo · Pro $99/mo · Accelerator $499/mo
- Freemium: first diagnostic free → measure free→paid conversion (target ≥5%)
