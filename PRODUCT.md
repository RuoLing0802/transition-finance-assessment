# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Existing FastAPI service with a static HTML/CSS/JavaScript workbench; no frontend framework is introduced in this redesign.

## Users

Primary users are finance and enterprise assessment staff who need to review one company's transition-finance evidence, data quality, energy changes, directory candidates and report in one run-scoped workspace. Team administrators also need a separate operational view for model, tool and audit diagnostics.

## Product Purpose

The product supports traceable transition-finance assessment workflows: register a simulated competition workbook, validate its five sheets, bind one company to one assessment run, inspect evidence and quality issues, ask run-scoped questions, match transition-directory candidates, and generate a basic report. Success means the user can understand what is known, missing, comparable or pending review without confusing simulated data with real enterprise conclusions.

## Positioning

Its distinctive mechanism is the separation of deterministic, replayable assessment facts and rules from external model orchestration, with each conversation, attachment, report and comparison bound to an assessment run.

## Operating Context

Users work in a three-part assessment workspace: select a task or company run, converse about the current run and its evidence, review generated reports, and keep the current enterprise's facts and quality signals visible alongside the conversation. A workspace may contain multiple enterprises, but a run is bound to one enterprise. Administrators can enter a separate diagnostics surface when they need model or audit details.

## Capabilities and Constraints

- Upload and register `.xlsx` batches, validate five sheets, and reuse the same batch for multiple enterprise runs.
- Display enterprise details, 2024–2025 energy and operating changes, missing data, quality issues, directory candidates and reference comparison.
- Use an external OpenAI-compatible model for run-scoped orchestration and route visual attachments to a vision-capable model when needed; keep an offline deterministic path available.
- Generate and preview a basic report and compare completed runs without producing enterprise rankings.
- `转型规划结论` is an isolated reference/comparison layer and never enters model input, features or labels.
- Current data is competition-provided simulated development data; the product must not claim real enterprise outcomes, formal carbon accounting, model accuracy or credit decisions.
- The current redesign is a user-facing workbench. Model selectors, raw tool calls, audit events, provider details and debug traces belong in the administrator surface, not the default user view.

## Brand Commitments

The product name is “碳迹可循”. The existing deep teal and quiet green palette is accepted as a starting point, while the user explicitly requires a larger, more readable type system, a calmer information hierarchy and a more finished product surface than the incumbent debug-oriented page.

## Evidence on Hand

Repository documentation, the existing M1/M2 API and static workbench, and the competition's de-identified simulated workbook are available. No real enterprise data, verified production outcomes, testimonials or formal model-performance evidence may be fabricated or implied.

## Product Principles

1. Make the next assessment action obvious.
2. Keep enterprise facts, evidence and reports in the current run's boundary.
3. Show uncertainty and missingness as useful work queues, never as silent blanks.
4. Let deterministic rules and evidence remain inspectable while keeping model plumbing out of the user's way.
5. Prefer calm, legible density over dashboard ornament.

## Accessibility & Inclusion

The web workbench must keep body text readable at a comfortable size, provide visible keyboard focus, preserve native form semantics, expose accessible names for icon-only controls, support reduced motion, and avoid making hover the only way to discover or complete an action.
