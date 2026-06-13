"""The manual agentic loop and the background scan job.

`run_agent_loop` is the orchestrator: it drives Claude through tool calls until
the model ends its turn, finishes the scan, refuses, or hits the iteration cap.
The Anthropic client is passed in so tests can inject a fake (no network).
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select

from app.agent.prompts import SYSTEM_PROMPT
from app.agent.tools import TOOL_SCHEMAS, ScanContext, execute_tool
from app.core.config import settings
from app.core.db import SessionLocal
from app.core.security import decrypt_token
from app.integrations.anthropic_client import get_anthropic_client
from app.integrations.gmail import GmailClient
from app.models import EmailAccount, ScanRun

MAX_ITERATIONS = 25


def _build_user_turn(ctx: ScanContext) -> str:
    lines = [
        f"Today's date is {date.today().isoformat()}.",
        f"There are {len(ctx.candidates)} candidate emails to review:",
    ]
    for c in ctx.candidates:
        lines.append(f"- id={c.message_id} | from={c.sender} | subject={c.subject} | date={c.date}")
    lines.append(
        "Review these, read the ones worth reading with get_email, record any "
        "subscriptions and payments you find, then call finish_scan."
    )
    return "\n".join(lines)


async def run_agent_loop(ctx: ScanContext, client, *, max_iterations: int = MAX_ITERATIONS) -> str:
    """Drive the agent. Returns 'completed' | 'refused' | 'max_iterations'."""
    messages: list[dict] = [{"role": "user", "content": _build_user_turn(ctx)}]

    for _ in range(max_iterations):
        response = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=16000,
            thinking={"type": "adaptive"},
            system=[
                {"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}
            ],
            tools=TOOL_SCHEMAS,
            messages=messages,
        )

        if response.stop_reason == "refusal":
            ctx.summary = ctx.summary or "Scan stopped: the model declined to continue."
            return "refused"
        if response.stop_reason == "end_turn":
            return "completed"

        # Preserve the full assistant content (tool_use + thinking blocks intact).
        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in response.content:
            if getattr(block, "type", None) != "tool_use":
                continue
            content, is_error = await execute_tool(ctx, block.name, block.input)
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": content,
                    "is_error": is_error,
                }
            )

        messages.append({"role": "user", "content": tool_results})
        if ctx.finished:
            return "completed"

    return "max_iterations"


async def run_scan_job(scan_run_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Background job: Gmail candidate search → agent loop → update the scan run.

    Runs in its own DB session (the request session is already closed).
    """
    async with SessionLocal() as db:
        scan = await db.get(ScanRun, scan_run_id)
        if scan is None:
            return
        try:
            account = await db.scalar(
                select(EmailAccount).where(
                    EmailAccount.user_id == user_id,
                    EmailAccount.provider == "gmail",
                )
            )
            if account is None or not account.oauth_refresh_token_encrypted:
                raise RuntimeError("no connected Gmail account")

            refresh_token = decrypt_token(account.oauth_refresh_token_encrypted)
            gmail = GmailClient.from_refresh_token(refresh_token)
            candidates = await run_in_threadpool(gmail.search_candidates)

            ctx = ScanContext(
                db=db,
                user_id=user_id,
                scan_run_id=scan_run_id,
                gmail=gmail,
                candidates=candidates,
            )
            result = await run_agent_loop(ctx, get_anthropic_client())

            scan.emails_scanned = ctx.emails_scanned
            scan.subscriptions_found = ctx.subscriptions_found
            scan.summary = ctx.summary
            scan.status = "succeeded" if result == "completed" else "failed"
            account.last_synced_at = datetime.now(UTC)
        except Exception:
            scan.status = "failed"
            scan.summary = "Scan failed due to an internal error."
        finally:
            scan.finished_at = datetime.now(UTC)
            await db.commit()
