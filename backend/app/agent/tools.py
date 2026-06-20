"""Agent tool schemas + tenant-scoped executors.

Each tool is a JSON schema (sent to Claude) plus a Python executor. Write
executors are bound to the scan's `user_id`/`scan_run_id` via `ScanContext` and
must never read or write across tenants (`.claude/rules/security.md`). Keep
`TOOL_SCHEMAS` order stable — prompt caching depends on it.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import date

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.gmail import EmailCandidate, GmailClient
from app.models import Payment, Subscription

# Deterministic, append-only order (prompt caching depends on it).
TOOL_SCHEMAS: list[dict] = [
    {
        "name": "list_candidate_emails",
        "description": (
            "List the candidate subscription emails for this scan (id, sender, "
            "subject, date). Read-only. The same list is in the user turn; use "
            "this if you need to re-read it."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_email",
        "description": (
            "Fetch one candidate email's headers and trimmed plaintext body so "
            "you can decide what it is. Read-only. Call only for emails worth "
            "reading."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "message_id": {
                    "type": "string",
                    "description": "The Gmail message id from the candidate list.",
                }
            },
            "required": ["message_id"],
        },
    },
    {
        "name": "upsert_subscription",
        "description": (
            "Create or update a subscription for this user. Matches an existing "
            "subscription by merchant_name. Returns the subscription_id to use "
            "when recording payments."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "merchant_name": {"type": "string"},
                "category": {"type": "string"},
                "billing_cycle": {
                    "type": "string",
                    "enum": ["monthly", "annual", "weekly", "quarterly", "unknown"],
                },
                "amount": {"type": "number", "description": "Expected recurring amount."},
                "currency": {"type": "string", "description": "ISO code, e.g. USD."},
                "status": {
                    "type": "string",
                    "enum": ["active", "cancelled", "unknown"],
                },
                "next_payment_date": {
                    "type": "string",
                    "description": "Inferred next charge date, YYYY-MM-DD.",
                },
                "trial_end_date": {
                    "type": "string",
                    "description": (
                        "Date a free trial converts to paid, YYYY-MM-DD. Set only "
                        "when the email indicates a trial converting on a specific date."
                    ),
                },
                "confidence": {
                    "type": "number",
                    "description": "0..1 confidence this is a real subscription.",
                },
            },
            "required": ["merchant_name"],
        },
    },
    {
        "name": "record_payment",
        "description": (
            "Record a payment for a subscription. Pass source_message_id so "
            "re-scans don't double-count. Idempotent per (subscription, "
            "source_message_id)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "subscription_id": {"type": "string"},
                "amount": {"type": "number"},
                "currency": {"type": "string"},
                "status": {"type": "string", "enum": ["paid", "upcoming"]},
                "occurred_on": {"type": "string", "description": "Charge date, YYYY-MM-DD."},
                "source_message_id": {
                    "type": "string",
                    "description": "Gmail message id this charge came from.",
                },
            },
            "required": ["subscription_id", "amount", "occurred_on"],
        },
    },
    {
        "name": "flag_missing_payment",
        "description": (
            "Flag an expected-but-missing or overdue charge for a subscription "
            "(e.g. a monthly plan with a gap)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "subscription_id": {"type": "string"},
                "amount": {"type": "number"},
                "currency": {"type": "string"},
                "status": {"type": "string", "enum": ["missing", "overdue"]},
                "occurred_on": {
                    "type": "string",
                    "description": "Expected charge date, YYYY-MM-DD.",
                },
            },
            "required": ["subscription_id", "amount", "occurred_on", "status"],
        },
    },
    {
        "name": "finish_scan",
        "description": (
            "End the scan with a one-paragraph summary of what you found. Call "
            "this when you are done."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"summary": {"type": "string"}},
            "required": ["summary"],
        },
    },
]


@dataclass
class ScanContext:
    """Per-scan state shared by the loop and the tool executors."""

    db: AsyncSession
    user_id: uuid.UUID
    scan_run_id: uuid.UUID
    gmail: GmailClient
    candidates: list[EmailCandidate] = field(default_factory=list)
    emails_scanned: int = 0
    subscriptions_found: int = 0
    summary: str | None = None
    finished: bool = False


def _parse_date(value: str | None) -> tuple[date | None, str | None]:
    if value is None:
        return None, None
    try:
        return date.fromisoformat(value), None
    except (ValueError, TypeError):
        return None, f"invalid date '{value}' (expected YYYY-MM-DD)"


async def _subscription_for_user(ctx: ScanContext, subscription_id: str) -> Subscription | None:
    try:
        sid = uuid.UUID(subscription_id)
    except (ValueError, TypeError):
        return None
    sub = await ctx.db.get(Subscription, sid)
    if sub is None or sub.user_id != ctx.user_id:
        return None
    return sub


async def _exec_list_candidate_emails(ctx: ScanContext, data: dict) -> tuple[str, bool]:
    rows = [
        {"message_id": c.message_id, "from": c.sender, "subject": c.subject, "date": c.date}
        for c in ctx.candidates
    ]
    return json.dumps({"candidates": rows}), False


async def _exec_get_email(ctx: ScanContext, data: dict) -> tuple[str, bool]:
    message_id = data.get("message_id")
    if not message_id:
        return json.dumps({"error": "message_id is required"}), True
    email = await run_in_threadpool(ctx.gmail.get_email, message_id)
    ctx.emails_scanned += 1
    return (
        json.dumps(
            {
                "message_id": email.message_id,
                "from": email.sender,
                "subject": email.subject,
                "date": email.date,
                "body": email.body,
            }
        ),
        False,
    )


async def _exec_upsert_subscription(ctx: ScanContext, data: dict) -> tuple[str, bool]:
    merchant = (data.get("merchant_name") or "").strip()
    if not merchant:
        return json.dumps({"error": "merchant_name is required"}), True

    next_date, err = _parse_date(data.get("next_payment_date"))
    if err:
        return json.dumps({"error": err}), True

    trial_end, err = _parse_date(data.get("trial_end_date"))
    if err:
        return json.dumps({"error": err}), True

    existing = await ctx.db.scalar(
        select(Subscription).where(
            Subscription.user_id == ctx.user_id,
            Subscription.merchant_name == merchant,
        )
    )
    created = existing is None
    sub = existing or Subscription(user_id=ctx.user_id, merchant_name=merchant)

    if "category" in data:
        sub.category = data["category"]
    if "billing_cycle" in data:
        sub.billing_cycle = data["billing_cycle"]
    if "amount" in data:
        sub.amount = data["amount"]
    if "currency" in data:
        sub.currency = data["currency"]
    if "status" in data:
        sub.status = data["status"]
    if next_date is not None:
        sub.next_payment_date = next_date
    if trial_end is not None:
        sub.trial_end_date = trial_end
    if "confidence" in data:
        sub.confidence = data["confidence"]

    if created:
        ctx.db.add(sub)
        ctx.subscriptions_found += 1
    await ctx.db.commit()
    await ctx.db.refresh(sub)
    return json.dumps({"subscription_id": str(sub.id), "created": created}), False


async def _exec_record_payment(ctx: ScanContext, data: dict) -> tuple[str, bool]:
    sub = await _subscription_for_user(ctx, data.get("subscription_id", ""))
    if sub is None:
        return json.dumps({"error": "unknown subscription_id for this user"}), True

    occurred_on, err = _parse_date(data.get("occurred_on"))
    if err or occurred_on is None:
        return json.dumps({"error": err or "occurred_on is required"}), True
    if "amount" not in data:
        return json.dumps({"error": "amount is required"}), True

    source_message_id = data.get("source_message_id")
    if source_message_id:
        dup = await ctx.db.scalar(
            select(Payment).where(
                Payment.user_id == ctx.user_id,
                Payment.subscription_id == sub.id,
                Payment.source_message_id == source_message_id,
            )
        )
        if dup is not None:
            return json.dumps({"payment_id": str(dup.id), "duplicate": True}), False

    payment = Payment(
        user_id=ctx.user_id,
        subscription_id=sub.id,
        amount=data["amount"],
        currency=data.get("currency"),
        status=data.get("status", "paid"),
        occurred_on=occurred_on,
        source_message_id=source_message_id,
    )
    ctx.db.add(payment)
    await ctx.db.commit()
    await ctx.db.refresh(payment)
    return json.dumps({"payment_id": str(payment.id), "duplicate": False}), False


async def _exec_flag_missing_payment(ctx: ScanContext, data: dict) -> tuple[str, bool]:
    sub = await _subscription_for_user(ctx, data.get("subscription_id", ""))
    if sub is None:
        return json.dumps({"error": "unknown subscription_id for this user"}), True

    occurred_on, err = _parse_date(data.get("occurred_on"))
    if err or occurred_on is None:
        return json.dumps({"error": err or "occurred_on is required"}), True
    if "amount" not in data:
        return json.dumps({"error": "amount is required"}), True
    status = data.get("status")
    if status not in ("missing", "overdue"):
        return json.dumps({"error": "status must be 'missing' or 'overdue'"}), True

    payment = Payment(
        user_id=ctx.user_id,
        subscription_id=sub.id,
        amount=data["amount"],
        currency=data.get("currency"),
        status=status,
        occurred_on=occurred_on,
    )
    ctx.db.add(payment)
    await ctx.db.commit()
    await ctx.db.refresh(payment)
    return json.dumps({"payment_id": str(payment.id)}), False


async def _exec_finish_scan(ctx: ScanContext, data: dict) -> tuple[str, bool]:
    ctx.summary = (data.get("summary") or "").strip() or "Scan complete."
    ctx.finished = True
    return json.dumps({"ok": True}), False


_EXECUTORS = {
    "list_candidate_emails": _exec_list_candidate_emails,
    "get_email": _exec_get_email,
    "upsert_subscription": _exec_upsert_subscription,
    "record_payment": _exec_record_payment,
    "flag_missing_payment": _exec_flag_missing_payment,
    "finish_scan": _exec_finish_scan,
}


async def execute_tool(ctx: ScanContext, name: str, raw_input: object) -> tuple[str, bool]:
    """Dispatch a tool call. Returns (result_content, is_error)."""
    executor = _EXECUTORS.get(name)
    if executor is None:
        return json.dumps({"error": f"unknown tool '{name}'"}), True
    # Tool input is usually a parsed dict; parse defensively if it's a JSON string.
    data = json.loads(raw_input) if isinstance(raw_input, str) else (raw_input or {})
    return await executor(ctx, data)
