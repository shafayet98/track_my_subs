# Rule: LLM usage (Claude)

These apply to all code that calls Claude / the Anthropic SDK.

- **Model:** always `claude-opus-4-8`. Do not hardcode any other model or add a
  date suffix. If a cheaper model is ever wanted for a sub-task, that is a
  deliberate decision the owner makes — don't downgrade silently.
- **Thinking:** use `thinking={"type": "adaptive"}`. Never use `budget_tokens`
  (removed on Opus 4.8 — returns 400).
- **No sampling params:** `temperature`, `top_p`, `top_k` are removed on Opus 4.8
  and return 400. Steer behavior with the prompt instead.
- **No assistant prefills:** last-assistant-turn prefills return 400. Use
  `output_config={"format": ...}` (structured outputs) or system-prompt
  instructions to constrain output shape.
- **max_tokens:** default `16000` for non-streaming; stream (`messages.stream`)
  for larger outputs to avoid HTTP timeouts.
- **Agentic loop:** check `response.stop_reason` before reading content. Handle
  `end_turn`, `tool_use`, and `refusal`. Append the full `response.content`
  (preserving `tool_use` blocks) and return one `tool_result` per `tool_use` id.
- **Parse tool inputs with `json.loads`**, never raw string matching — escaping
  can vary.
- **Prompt caching:** keep the system prompt and tool list stable (deterministic
  order). Put volatile per-scan content in the user turn, not the system prompt.
- **Client:** initialize `anthropic.Anthropic()` / `AsyncAnthropic()` and let it
  read `ANTHROPIC_API_KEY` from the environment. Never hardcode the key.

When in doubt about the API, consult the `claude-api` skill rather than guessing
SDK shapes.
