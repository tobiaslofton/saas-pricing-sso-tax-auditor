#!/usr/bin/env python3
"""
Standalone Model Context Protocol (MCP) Server for SaaS Pricing & SSO Tax Auditor.
Supports local stdio execution for Claude Desktop, Cursor, Windsurf, and OpenClaw,
as well as remote cloud execution via Apify (`algernontechnologies/saas-pricing-sso-tax-auditor`).
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

BILLING_STACK_SIGNATURES: dict[str, list[str]] = {
    "Stripe": ["js.stripe.com", "stripe.com", "checkout.stripe.com"],
    "Chargebee": ["chargebee.com", "js.chargebee.com"],
    "Paddle": ["paddle.com", "cdn.paddle.com"],
    "Recurly": ["recurly.com", "js.recurly.com"],
    "Zuora": ["zuora.com"],
    "Maxio / Chargify": ["maxio.com", "chargify.com"],
    "Orb Billing": ["withorb.com"],
    "Metronome": ["metronome.com"],
}


def normalize_domain(raw: str) -> str:
    raw = raw.strip().lower()
    if "://" in raw:
        parsed = urlparse(raw)
        host = parsed.netloc or parsed.path
    else:
        host = raw.split("/")[0]
    host = host.split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    return host


async def fetch_with_fallback(client: httpx.AsyncClient, url: str) -> httpx.Response | None:
    try:
        resp = await client.get(url, follow_redirects=True, timeout=15.0)
        if resp.status_code == 403:
            resp = await client.get(
                url,
                headers={"User-Agent": "python-httpx/0.28.1", "Accept": "*/*"},
                follow_redirects=True,
                timeout=15.0,
            )
        if resp.status_code < 400:
            return resp
    except Exception:
        pass
    return None


async def audit_single_domain(raw_domain: str) -> dict[str, Any]:
    domain = normalize_domain(raw_domain)
    candidates = [
        f"https://{domain}/pricing",
        f"https://www.{domain}/pricing",
        f"https://{domain}/plans",
        f"https://{domain}",
    ]
    pricing_url = f"https://{domain}/pricing"
    combined_text = ""
    combined_html = ""

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    }

    async with httpx.AsyncClient(headers=headers, http2=False) as client:
        responses = await asyncio.gather(*(fetch_with_fallback(client, u) for u in candidates))

    for resp in responses:
        if not resp:
            continue
        final_url = str(resp.url)
        html = resp.text
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(separator=" ", strip=True)

        if any(k in final_url.lower() for k in ["/pricing", "/plans", "/billing"]):
            pricing_url = final_url
        else:
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"]
                if "pricing" in href.lower() or "plans" in href.lower():
                    pricing_url = urljoin(final_url, href)
                    break

        combined_text += " " + text
        combined_html += " " + html.lower()

    corpus = (combined_text + " " + combined_html).lower()

    raw_prices = re.findall(
        r"\$\s*(\d{1,4})(?:\.\d{2})?\s*(?:/|\bper\b|\bmo|\bmonth|\buser|\bseat|\byear|\byr)",
        combined_text,
        re.IGNORECASE,
    )
    if not raw_prices:
        raw_prices = re.findall(r"\$(\d{1,4})\b", combined_text)

    numeric_prices = sorted({int(p) for p in raw_prices if 0 <= int(p) <= 5000})
    paid_prices = [p for p in numeric_prices if p > 0]
    lowest_paid = float(paid_prices[0]) if paid_prices else None
    price_points = [f"${p}" for p in numeric_prices[:8]]

    has_free_tier = bool(
        re.search(r"\b(?:free\s+forever|free\s+plan|free\s+tier|\$0\b|start\s+for\s+free)\b", corpus)
    )
    has_free_trial = bool(
        re.search(
            r"\b(?:free\s+trial|14[\s\-]*day\s+trial|7[\s\-]*day\s+trial|30[\s\-]*day\s+trial|try\s+for\s+free)\b",
            corpus,
        )
    )
    has_enterprise_tier = bool(
        re.search(r"\b(?:enterprise|contact\s+sales|talk\s+to\s+sales|custom\s+pricing)\b", corpus)
    )

    is_seat = bool(re.search(r"\b(?:per\s+user|per\s+seat|/user|/seat|per\s+member|/member)\b", corpus))
    is_usage = bool(
        re.search(r"\b(?:pay\s+as\s+you\s+go|usage[\s\-]*based|per\s+request|per\s+credit|per\s+gb|compute)\b", corpus)
    )

    if is_seat and is_usage:
        pricing_model = "Hybrid (Per-Seat + Usage-Based)"
    elif is_seat:
        pricing_model = "Per-Seat / User Subscription"
    elif is_usage:
        pricing_model = "Usage-Based / Pay-As-You-Go"
    elif paid_prices:
        pricing_model = "Tiered Flat Subscription"
    else:
        pricing_model = "Enterprise Custom Quote Only"

    if (has_free_tier or has_free_trial or paid_prices) and has_enterprise_tier:
        sales_motion = "Hybrid (PLG Self-Serve + Enterprise Sales)"
    elif has_free_tier or has_free_trial or paid_prices:
        sales_motion = "Product-Led Growth (PLG Self-Serve)"
    else:
        sales_motion = "Enterprise Sales-Led (SLG)"

    sso_saml_mentioned = bool(re.search(r"\b(?:saml|sso|single\s+sign[\s\-]*on|scim|okta)\b", corpus))
    sso_tax_gated = bool(sso_saml_mentioned and has_enterprise_tier)

    billing_stack: list[str] = []
    for vendor, sigs in BILLING_STACK_SIGNATURES.items():
        if any(sig in corpus for sig in sigs):
            billing_stack.append(vendor)

    gtm_summary = (
        f"{domain} runs a {sales_motion} motion with {pricing_model} pricing "
        f"(Lowest paid tier: {'$' + str(int(lowest_paid)) + '/mo' if lowest_paid else 'Custom Quote'}, "
        f"Free tier: {'Yes' if has_free_tier else 'No'}, Enterprise SSO-Tax gated: {'Yes' if sso_tax_gated else 'No'})."
    )

    return {
        "domain": domain,
        "audited_at": datetime.now(timezone.utc).isoformat(),
        "pricing_page_url": pricing_url,
        "sales_motion": sales_motion,
        "pricing_model": pricing_model,
        "has_free_tier": has_free_tier,
        "has_free_trial": has_free_trial,
        "has_enterprise_tier": has_enterprise_tier,
        "lowest_paid_price_usd": lowest_paid,
        "price_points_detected": price_points,
        "sso_saml_mentioned": sso_saml_mentioned,
        "sso_tax_gated": sso_tax_gated,
        "billing_stack": billing_stack,
        "gtm_summary": gtm_summary,
    }


TOOLS = [
    {
        "name": "audit_saas_pricing",
        "description": (
            "Audit a B2B SaaS domain's pricing page to extract its GTM sales motion (PLG vs. Enterprise SLG), "
            "pricing model (Per-Seat, Usage-Based, Hybrid), lowest paid USD price point, Free Tier/Trial availability, "
            "Enterprise SSO/SAML Tax gating, and underlying billing infrastructure (Stripe, Chargebee, Paddle, Zuora, Orb, Metronome)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "description": "Target SaaS domain (e.g., 'linear.app', 'supabase.com', 'figma.com').",
                }
            },
            "required": ["domain"],
        },
    },
    {
        "name": "batch_audit_saas_pricing",
        "description": "Audit multiple B2B SaaS domains concurrently for pricing models, PLG vs SLG motion, and SSO Tax gating.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "domains": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of SaaS domains to audit concurrently.",
                }
            },
            "required": ["domains"],
        },
    },
]


async def handle_request(req: dict[str, Any]) -> dict[str, Any] | None:
    method = req.get("method")
    req_id = req.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": "saas-pricing-sso-tax-auditor",
                    "version": "0.1.3",
                },
            },
        }
    if method == "notifications/initialized":
        return None
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = req.get("params") or {}
        name = params.get("name")
        args = params.get("arguments") or {}
        try:
            if name == "audit_saas_pricing":
                res = await audit_single_domain(args["domain"])
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"content": [{"type": "text", "text": json.dumps(res, indent=2)}]},
                }
            if name == "batch_audit_saas_pricing":
                domains = args.get("domains") or []
                results = await asyncio.gather(*(audit_single_domain(d) for d in domains[:15]))
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"content": [{"type": "text", "text": json.dumps(results, indent=2)}]},
                }
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Unknown tool: {name}"},
            }
        except Exception as exc:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": f"Error auditing domain: {exc}"}],
                    "isError": True,
                },
            }
    if req_id is not None:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }
    return None


async def stdio_loop() -> None:
    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)

    while True:
        line = await reader.readline()
        if not line:
            break
        raw = line.decode("utf-8", errors="replace").strip()
        if not raw:
            continue
        try:
            req = json.loads(raw)
        except json.JSONDecodeError:
            continue
        resp = await handle_request(req)
        if resp is not None:
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    asyncio.run(stdio_loop())
