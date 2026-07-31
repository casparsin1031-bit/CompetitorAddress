# Tickets: New Brand Onboarding for CompetitorAddress

Build a smooth, repeatable workflow for Caspar to request a new competitor brand and for Hermes to assess, validate, and optionally onboard it into the monthly competitor address process without polluting the maintained dataset.

Work the frontier: any ticket whose blockers are all done. For a mostly linear chain, start from Ticket 1 and continue downward.

## Ticket 1 — Define the new-brand intake contract

**What to build:** A clear, reusable intake contract that captures exactly what Hermes needs before researching a brand: brand name, markets, category, expected count, source hints, automation appetite, and approval rules.

**Blocked by:** None — can start immediately.

- [ ] Intake fields are grouped into required, recommended, and optional.
- [ ] The contract distinguishes “quick source assessment” from “full onboarding”.
- [ ] The contract includes target markets, category, expected count range, known official URLs, fallback tolerance, and whether repo changes are allowed.
- [ ] The contract states when Hermes must ask Caspar before changing files or enabling monthly automation.
- [ ] The contract is understandable to a non-engineering user and can be copy-pasted into a Hermes prompt.

## Ticket 2 — Add a local HTML request form for Caspar

**What to build:** A simple local HTML file where Caspar can enter a new brand request and generate a ready-to-send Hermes prompt for source discovery or onboarding.

**Blocked by:** Ticket 1 — Define the new-brand intake contract.

- [ ] The form captures all required intake fields from the contract.
- [ ] The form offers workflow choices: source assessment only, prepare repo changes if safe, or full onboarding after approval.
- [ ] The generated prompt includes safety constraints: official sources first, fallback-only requires approval, do not publish failed runs.
- [ ] The form has a copy-to-clipboard button and a readable preview.
- [ ] The HTML runs standalone from a local file without a backend.

## Ticket 3 — Implement source discovery and confidence report flow

**What to build:** A Hermes operating flow that, given the intake prompt, searches for official/fallback sources and returns a decision-ready confidence report before modifying the repo.

**Blocked by:** Ticket 1 — Define the new-brand intake contract.

- [ ] The report lists each requested brand-market pair.
- [ ] For each pair, the report identifies official source, fallback sources, source confidence, expected count range, observed count, address completeness, and source risk.
- [ ] The report recommends one of: onboard, hold as candidate/manual review, reject/no confirmed presence, or ask for human confirmation.
- [ ] The report clearly separates current evidence from assumptions.
- [ ] The report does not modify repo files unless the request explicitly allows that step.

## Ticket 4 — Add registry/config onboarding path for approved brands

**What to build:** A controlled path for Hermes to add an approved brand-market pair into the source registry and competitor config using the discovered source evidence.

**Blocked by:** Ticket 3 — Implement source discovery and confidence report flow.

- [ ] Approved entries are added to the source registry with source priority, confidence, expected count range, significant drop threshold, and verification notes.
- [ ] Approved entries are added to the competitor config with the correct scraper class and enabled state.
- [ ] Fallback-only entries are either disabled by default or marked as needing approval before monthly automation.
- [ ] Expected ranges are conservative and evidence-based, not loosened just to pass tests.
- [ ] Caspar receives a concise diff summary before committing or publishing.

## Ticket 5 — Build scraper/parser only when the source passes intake gates

**What to build:** A narrow scraper/parser implementation for the approved source, preferring deterministic HTML/API parsing before browser automation.

**Blocked by:** Ticket 4 — Add registry/config onboarding path for approved brands.

- [ ] Official API/static HTML sources are implemented with requests/BeautifulSoup or equivalent deterministic parsing where possible.
- [ ] Playwright/browser scraping is used only when deterministic parsing is not feasible.
- [ ] Each returned store has source-traceable shop name and address, with phone/hours/lat/lon where available.
- [ ] Zero-row scrapes are treated as exceptions, not valid empty results.
- [ ] A small parser/source validation test exists for deterministic sources where feasible.

## Ticket 6 — Run scrape-only validation and sanity gates for the new brand

**What to build:** A verification run that proves the new brand can be found reliably before it joins monthly maintenance.

**Blocked by:** Ticket 5 — Build scraper/parser only when the source passes intake gates.

- [ ] Hermes runs a scrape-only validation with geocoding skipped where appropriate.
- [ ] Sanity checks fail zero counts, low counts, significant drops, missing addresses, and implausible counts.
- [ ] The validation produces a markdown or JSON report with counts, samples, and exceptions.
- [ ] The new brand is not published or committed as monthly-maintained output unless the sanity gate passes.
- [ ] Any exception includes a recommended default action for Caspar to approve or reject.

## Ticket 7 — Add monthly-maintenance eligibility decision

**What to build:** A final onboarding decision that moves the new brand into monthly maintenance only when the source, scraper, and sanity checks are strong enough.

**Blocked by:** Ticket 6 — Run scrape-only validation and sanity gates for the new brand.

- [ ] Official-source brands with passing sanity checks can be marked eligible for monthly automation.
- [ ] Fallback-only brands remain candidate/manual review unless Caspar explicitly approves monthly tracking.
- [ ] The decision records why the brand is eligible, held, or rejected.
- [ ] Caspar can see the exact command/result that validated the decision.
- [ ] The monthly process still publishes only on a passing sanity report.

## Ticket 8 — Document the smooth user interaction loop

**What to build:** A short runbook explaining how Caspar should use the HTML form and how Hermes should respond to each type of new-brand request.

**Blocked by:** Ticket 2 — Add a local HTML request form for Caspar; Ticket 7 — Add monthly-maintenance eligibility decision.

- [ ] The runbook includes example prompts for “check only”, “prepare if safe”, and “full onboarding”.
- [ ] The runbook defines approval checkpoints in plain language.
- [ ] The runbook explains easy/medium/difficult source cases.
- [ ] The runbook tells Caspar where to find the generated form and ticket file.
- [ ] The runbook gives the recommended default: assess first, change files only after evidence and approval.
