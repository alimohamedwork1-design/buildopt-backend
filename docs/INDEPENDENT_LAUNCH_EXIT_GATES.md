# BuildOpt AI — Independent Launch Exit Gates

**As of 21 November 2026.** Read this before claiming the independent platform or any of its integrations is production-ready.

| Capability | Code / tests | Live proof status | What still blocks acceptance |
| --- | --- | --- | --- |
| Brand-neutral marketing site, customer entry paths | merged and frontend deployed | deployed | visual QA and external claims review per target audience |
| CRM, customer portal, billing, proposals, support | code merged; PostgreSQL RLS suite | **production Supabase not confirmed** | authorized migrations, customer permissions, live end-to-end flows |
| Public lead capture and email notifications | Edge Function source and Turnstile requirement | **live lead/notification unverified** | Supabase deployment, keys, provider verification, test lead |
| Edge protocol connector framework | code + offline queue | only proprietary optional adapter has historical pathway; generic protocols are placeholders | site-approved driver and protocol tests |
| Synthetic Integration Lab | deterministic fixtures and failure tests | simulated only | lab is not physical interoperability certification |
| Engineering Copilot | rule-based sourced explanations, tests | no accepted real customer data | engineer validation, source references, clinical-quality? no: HVAC measurements |
| Energy baseline & M&V | service code and report framework | no approved site outcomes | metering boundary, weather/load adjustments, audit trail |
| Digital Twin | readiness, model/scenario foundations | **no fully calibrated customer twin** | approved physical calibration and measured error |
| Multi-site EUI | manually entered comparisons | unverified user inputs | comparable meters, area, occupancy, weather, tariff methods |
| On-prem / private deployment | Compose reference + mandatory secret preflight | **not an enterprise-ready release** | private auth, ingress, SSL, backup/restore and actual site |
| Field sales and paying customers | sales pipeline + quote templates | no confirmed signed customer in repository | legal entity, contracts, first paid site |
| Safe autonomous controls | writeback disabled in pilot | intentionally excluded | separate engineering safety case; do not enable by default |

## Immediate company execution milestones
**G0:** Actual Supabase project ownership verified → backup → staging migration → tenant isolation → production apply (separate authorized action).  
**G1:** Cloudflare/Resend configured → no false-success lead form → submit genuine opt-in request and follow-up.  
**G2:** One customer signs read-only site pilot → OT access and gateway engineer designated.  
**G3:** Data quality and FDD on real sensor measurements, digital twin shadow mode only.  
**G4:** Customer accepts technical report with limitations, and real invoice/payment/renewal process.  
**G5:** Reuse acceptance process with a second independent client and measure gross margin.

## Claim policy
All dashboard charts, simulator runs and market reports must be visibly labeled DEMO, OPERATOR-SUPPLIED or LIVE VERIFIED as appropriate. Pass of software test or GitHub CI ≠ a live meter or physical building certificate.

## Current engineering deliverables
- Main frontend: `alimohamedwork1-design/buildopt-ai`
- Backend/API: `alimohamedwork1-design/buildopt-backend`
- Connector simulation (offline): `python -m app.services.integration_lab --protocol bacnet_ip --scenario packet_loss`
- On-prem security preflight: `python scripts/onprem_preflight.py`
- CRM activation guidance: `buildopt-ai/docs/deployment/CRM_ACTIVATION.md`
