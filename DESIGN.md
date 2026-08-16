# Visual Direction

<!-- impeccable:design-schema 1 -->

## Direction

**Evidence Desk** — a calm, editorial assessment desk for financial teams. The interface should feel like a well-arranged case file: one active enterprise, one conversation, one visible evidence trail. It is deliberately not a monitoring console.

## Surface

The primary web surface is an Operate-mode three-column workbench:

1. **Task rail**: workspace, enterprise runs, create/switch actions.
2. **Conversation and output**: the current run's assistant conversation, evidence upload, and report output.
3. **Evidence shelf**: current enterprise facts, quality signals, energy change summary, directory candidates and the isolated reference-comparison note.

The default user surface hides provider, model, tool, audit and raw payload details. A backend-gated administrator dialog reveals those diagnostics only after a password check using `TRANSITION_FINANCE_ADMIN_PASSWORD`.

## Palette

- Ink: `#193330`
- Deep teal: `#123F3E`
- Teal action: `#0E7772`
- Leaf accent: `#CDE9A3`
- Paper: `#F4F5F0`
- Panel: `#FFFFFF`
- Mist: `#E8EFEB`
- Line: `#D5E0DA`
- Warm review: `#B9783F` / `#FFF2DE`
- Risk: `#B95C59` / `#FCE9E6`

Use one elevation language: quiet borders for structure and soft offset shadows only for the app shell, dialogs and transient feedback.

## Typography

Use `Noto Sans SC`, then `PingFang SC`, then the platform sans fallback. Body text is 15–16px with 1.55 line-height. Section titles are 18–22px; the active enterprise title is 28–32px. Tables and metadata may use 13px, never smaller for primary content. Use weight and spacing for hierarchy instead of uppercase AI-style eyebrow labels.

## Components

- Prefer compact, purposeful panels with 14–18px radii; do not nest generic cards as the information architecture.
- Use inline SVG stroke icons with `aria-hidden="true"` and accessible labels on icon-only buttons.
- Use full-width empty states with one primary action and one clear next step.
- Keep data tables readable with sticky headers, tabular numerals and status tags that combine color with text.
- Keep the simulation notice visible but calm; it is a boundary statement, not a warning banner dominating the work.

## Motion

Author one entrance moment for the shell: a 12px upward reveal with 30–60ms stagger. Use 160–220ms ease-out transitions for buttons, list items, drawers and status changes. Add `scale(0.98)` press feedback to actionable controls. Do not animate tables or every card. Respect `prefers-reduced-motion` by removing transforms while retaining opacity and color transitions.

## Responsive Behavior

- At wide desktop widths, keep the three columns visible with a fixed task rail and evidence shelf.
- At medium widths, let the evidence shelf move below the conversation while preserving task navigation.
- At mobile widths, stack task rail, conversation/output and evidence shelf; preserve 44px touch targets and keep the composer visible without horizontal scrolling.

## Anti-Patterns to Avoid

- No debug-first layout, raw IDs, model plumbing or provider jargon in the default user view.
- No tiny grey text, decorative gradients, emoji or Unicode glyphs as icons.
- No hover-only actions, invisible focus rings, or motion that blocks the task.
- No ranking language in comparison surfaces; show versions, periods, batches and incomparability reasons only.
