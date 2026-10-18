---
name: model-routing
description: Classify a task as simple, repetitive, or complex before starting it, and route the work to the right model (haiku / sonnet / opus) via the Agent tool's `model` parameter. Use at the start of any non-trivial request, before spawning subagents, or when planning batch work (e.g. processing many videos, scripts, captions, or thumbnails for YouTube Shorts).
---

# Model routing: simple vs repetitive vs complex

Before doing the work, spend a few seconds classifying it. Pick the cheapest
model that will get it right the first time — a redo on a weak model costs more
than doing it once on a strong one.

## Step 1 — Classify

| Class | Signals | Examples (this repo) |
|---|---|---|
| **Simple** | One step, one file, answer is obvious, no judgment, easy to verify | Rename a file, fix a typo, look up a value, format a JSON file, write a one-line commit message, list files |
| **Repetitive** | Same well-defined operation applied to many items; a clear template or spec exists; each item is independent | Generate titles/hashtags for 30 clips, convert 50 SRT files, resize a batch of thumbnails, apply the same edit across many scripts, summarise each transcript in a folder |
| **Complex** | Ambiguous goal, multi-step reasoning, design decisions, cross-file changes, debugging an unknown cause, anything where a mistake is costly or hard to spot | Design the upload/render pipeline, debug a failing ffmpeg chain, choose a content strategy, refactor the codebase, write the spec/template the repetitive work will follow |

Tie-breakers:
- Unsure between two classes → pick the higher one.
- Touches credentials, publishing, deletion, or anything public-facing → **complex**.
- Repetitive work with no template yet → first do one item as **complex** to create the template, then hand the rest out as **repetitive**.

## Step 2 — Route

| Class | Model | How |
|---|---|---|
| Simple | `haiku` | Do it inline if it's faster than delegating; otherwise `Agent` with `model: "haiku"` |
| Repetitive | `sonnet` | `Agent` with `model: "sonnet"`, one agent per chunk of items, launched in parallel in a single message |
| Complex | `opus` | Handle it yourself (main session), or `Agent` with `model: "opus"` / the `Plan` agent for design work |

Rules:
- Give delegated agents a self-contained prompt: the exact input, the
  template/spec, the output location and format, and how to verify.
- For repetitive batches, split into chunks (≈5–20 items each) and run the
  chunks concurrently.
- Keep review and integration on the strong model: after cheaper agents finish,
  spot-check their output (at least one item per chunk) before reporting done.
- If a cheaper model's output fails the check twice, escalate that item one tier.

## Step 3 — Say what you chose

State the classification in one line before starting, e.g.
`Classified as repetitive (40 captions, fixed template) → sonnet ×4 in parallel; opus reviews.`
The user can override; if they name a model, use it.

## Mixed tasks

Most real requests are mixed. Decompose them:

1. **Complex** — understand the goal, decide the approach, write the template.
2. **Repetitive** — fan out the per-item work.
3. **Simple** — mechanical cleanup (renames, file moves, listing results).
4. **Complex** — final review and summary to the user.

Example: "Make Shorts scripts for these 25 topics"
→ opus drafts the script structure and one sample script →
sonnet ×5 agents write 5 scripts each from that sample →
haiku names/organises the files → opus spot-checks and reports.
