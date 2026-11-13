# Bob playbook: how IBM Bob IDE is a core part of this build

Judging requires the solution to **showcase IBM Bob IDE as a core component**. Use Bob for the
work below, in this order (budget: about 50 Bobcoins per person, so front-load the big prompts).
Keep notes of what Bob did, because the submission asks how each IBM tool was used.

## 0. Project context (1 prompt)
Open the repo in Bob IDE and run `/init` so Bob writes persistent project context.
Add these project rules in Bob:
> This repo is "Last Bus Out". Numbers shown to users must come from deterministic code in
> app/engine.py, never from the LLM. Granite (watsonx.ai) is only used in app/granite.py for
> parsing postings and writing memos, and every memo number must pass verify_numbers().
> Never write API keys into files; read them from environment variables.

## 1. Get real data running (Code mode, ~2 prompts)
> Run `python scripts/fetch_data.py` then `python scripts/build_index.py`. If either fails on the
> real DDOT or SMART feed (missing columns, odd time formats, expired calendars), fix the script,
> rerun, and run `python -m pytest -q tests` to confirm nothing broke.

## 2. Wire watsonx.ai Granite (Code mode, ~1 prompt)
> Using .env values, call /api/parse with samples/postings.json texts and confirm the provider
> badge shows "IBM watsonx.ai". If the chat endpoint or model ID fails, check the model list in
> Prompt Lab and fix app/granite.py.

## 3. Build the demo feature: shift comparison (Plan → Code mode, ~3 prompts)
> When a posting has more than one shift (e.g., 1st and 2nd shift), add buttons in web/app.js to
> switch between them, and show a one-line comparison: "1st shift: X% round trip · 2nd shift: Y%".
> Reuse tractStatus(); don't add new math.

## 4. Polish the UI (Code mode, ~2 prompts)
> Make the coverage number animate when the slider moves, add a "last bus home" line under it from
> the memo facts, and make the panel readable on a projector (bigger type, high contrast).

## 5. Review and ship (Review workflow + commit/PR)
- Run Bob's **Review** workflow on the diff and apply its fixes.
- Let Bob generate the commit message and open the PR.
- Optional: ask Bob to deploy the `Dockerfile` to **IBM Code Engine** for a live URL judges can open.

## 6. Evidence
Screenshot the Bob **Budget** badge → `bob_usage/` (see `bob_usage/README.md`).
