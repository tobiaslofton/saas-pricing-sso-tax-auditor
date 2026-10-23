from __future__ import annotations

import asyncio
import os
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from apify import Actor
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

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


class AIPricingSynthesis(BaseModel):
    gtm_summary: str = Field(
        description="Concise 2-sentence GTM, pricing model, and Enterprise SSO-tax summary for RevOps and competitive intelligence."
    )


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


async def audit_pricing_page(
    client: httpx.AsyncClient,
    raw_domain: str,
    gemini_api_key: str | None,
) -> dict[str, Any]:
    domain = normalize_domain(raw_domain)
    Actor.log.info(f"Auditing SaaS pricing & GTM motion for: {domain}")

    candidates = [
        f"https://{domain}/pricing",
        f"https://www.{domain}/pricing",
        f"https://{domain}/plans",
        f"https://{domain}",
    ]

    pricing_url = f"https://{domain}/pricing"
    combined_text = ""
    combined_html = ""

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
            # Look for a pricing link on the homepage
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"]
                if "pricing" in href.lower() or "plans" in href.lower():
                    pricing_url = urljoin(final_url, href)
                    break

        combined_text += " " + text
        combined_html += " " + html.lower()

    corpus = (combined_text + " " + combined_html).lower()

    # Extract USD price points like $8, $10, $20, $25, $49, $99, $599
    raw_prices = re.findall(r"\$\s*(\d{1,4})(?:\.\d{2})?\s*(?:/|\bper\b|\bmo|\bmonth|\buser|\bseat|\byear|\byr)", combined_text, re.IGNORECASE)
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
        re.search(r"\b(?:free\s+trial|14[\s\-]*day\s+trial|7[\s\-]*day\s+trial|30[\s\-]*day\s+trial|try\s+for\s+free)\b", corpus)
    )
    has_enterprise_tier = bool(
        re.search(r"\b(?:enterprise|contact\s+sales|talk\s+to\s+sales|custom\s+pricing)\b", corpus)
    )

    # Pricing Model detection
    is_seat = bool(re.search(r"\b(?:per\s+user|per\s+seat|/user|/seat|per\s+member|/member)\b", corpus))
    is_usage = bool(re.search(r"\b(?:pay\s+as\s+you\s+go|usage[\s\-]*based|per\s+request|per\s+credit|per\s+gb|compute)\b", corpus))

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

    # Sales Motion classification
    if (has_free_tier or has_free_trial or paid_prices) and has_enterprise_tier:
        sales_motion = "Hybrid (PLG Self-Serve + Enterprise Sales)"
    elif has_free_tier or has_free_trial or paid_prices:
        sales_motion = "Product-Led Growth (PLG Self-Serve)"
    else:
        sales_motion = "Enterprise Sales-Led (SLG)"

    # SSO / SAML & SSO-Tax Detection
    sso_saml_mentioned = bool(re.search(r"\b(?:saml|sso|single\s+sign[\s\-]*on|scim|okta)\b", corpus))
    sso_tax_gated = bool(sso_saml_mentioned and has_enterprise_tier)

    # Billing Stack Detection
    billing_stack: list[str] = []
    for vendor, sigs in BILLING_STACK_SIGNATURES.items():
        if any(sig in corpus for sig in sigs):
            billing_stack.append(vendor)

    gtm_summary = (
        f"{domain} runs a {sales_motion} motion with {pricing_model} pricing "
        f"(Lowest paid tier: {'$' + str(int(lowest_paid)) + '/mo' if lowest_paid else 'Custom Quote'}, "
        f"Free tier: {'Yes' if has_free_tier else 'No'}, Enterprise SSO-Tax gated: {'Yes' if sso_tax_gated else 'No'})."
    )

    # Optional Gemini synthesis
    key = gemini_api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if key:
        try:
            from google import genai
            from google.genai import types

            ai_client = genai.Client(api_key=key)
            prompt = (
                f"Summarize this B2B SaaS pricing & GTM audit for {domain}:\n"
                f"- Sales Motion: {sales_motion}\n"
                f"- Pricing Model: {pricing_model}\n"
                f"- Price Points: {price_points}\n"
                f"- Free Tier: {has_free_tier}, Free Trial: {has_free_trial}, Enterprise Tier: {has_enterprise_tier}\n"
                f"- SSO/SAML Gated (SSO Tax): {sso_tax_gated}\n"
                f"- Billing Stack: {billing_stack}\n"
            )
            resp = await asyncio.to_thread(
                ai_client.models.generate_content,
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=AIPricingSynthesis,
                    temperature=0.2,
                ),
            )
            gtm_summary = AIPricingSynthesis.model_validate_json(resp.text).gtm_summary
        except Exception as exc:
            Actor.log.warning(f"Gemini fallback for {domain}: {exc}")

    record = {
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
        "price_points_csv": ", ".join(price_points),
        "sso_saml_mentioned": sso_saml_mentioned,
        "sso_tax_gated": sso_tax_gated,
        "billing_stack": billing_stack,
        "billing_stack_csv": ", ".join(billing_stack),
        "gtm_summary": gtm_summary,
    }

    await Actor.push_data(record)

    if hasattr(Actor, "charge"):
        try:
            await Actor.charge(event_name="pricing-audited", count=1)
        except Exception as exc:
            Actor.log.debug(f"PPE charge skipped in local environment: {exc}")

    return record


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}
        domains: list[str] = actor_input.get("domains") or ["linear.app", "supabase.com", "calendly.com"]
        gemini_api_key: str | None = actor_input.get("gemini_api_key")
        max_concurrency: int = int(actor_input.get("max_concurrency", 5))

        semaphore = asyncio.Semaphore(max(1, min(max_concurrency, 20)))
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        }

        async with httpx.AsyncClient(headers=headers, http2=False) as client:
            async def sem_task(d: str) -> dict[str, Any]:
                async with semaphore:
                    return await audit_pricing_page(client, d, gemini_api_key)

            await asyncio.gather(*(sem_task(d) for d in domains), return_exceptions=True)
