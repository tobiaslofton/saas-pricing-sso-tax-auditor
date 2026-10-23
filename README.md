# 💸 B2B SaaS Pricing Model, PLG & Enterprise "SSO-Tax" Auditor

Automatically audit any list of B2B SaaS domains (e.g., `linear.app`, `supabase.com`, `calendly.com`) to extract their **Go-To-Market (GTM) sales motion**, **pricing model**, **starting price**, **free tier / trial availability**, **billing stack**, and whether **SAML / SSO is gated behind an Enterprise tier ("SSO Tax")**.

Built for **Clay.com outbound agencies**, **RevOps teams**, **Private Equity / VC analysts**, and **MCP AI Agents**.

> 🌐 **Live Benchmark Demo:** See this Actor's live output across leading SaaS & AI companies at **[The 2026 B2B SaaS Trust Center, AI Sub-Processor & SSO-Tax Index](https://tobiaslofton.github.io/saas-trust-ai-index/)** (Open-source dataset: [GitHub Repo](https://github.com/tobiaslofton/saas-trust-ai-index)).

---

## 🚀 What Data Does It Extract?

| Field | Description |
| :--- | :--- |
| **`sales_motion`** | Classifies as `Product-Led Growth (PLG Self-Serve)`, `Hybrid (PLG Self-Serve + Enterprise Sales)`, or `Enterprise Sales-Led (SLG)`. |
| **`pricing_model`** | Detects `Per-Seat / User Subscription`, `Usage-Based / Pay-As-You-Go`, `Hybrid (Per-Seat + Usage-Based)`, `Tiered Flat Subscription`, or `Enterprise Custom Quote Only`. |
| **`lowest_paid_price_usd`** | Extracts the entry-level paid price point in USD (e.g., `8`, `10`, `25`). |
| **`price_points_csv`** | Flat CSV list of all detected tier price points (e.g., `$0, $8, $14, $25`). |
| **`has_free_tier` / `has_free_trial`** | Boolean flags for instant PLG lead segmentation in Clay.com and HubSpot. |
| **`sso_tax_gated`** | Detects whether SAML / Okta / SCIM / Single Sign-On is gated behind an Enterprise plan. |
| **`billing_stack_csv`** | Identifies payment/subscription infrastructure (`Stripe`, `Chargebee`, `Paddle`, `Recurly`, `Zuora`, `Maxio`, `Orb`, `Metronome`). |
| **`gtm_summary`** | Executive GTM & packaging summary (with optional **Gemini 2.5 Flash** synthesis). |

---

## 📊 Sample Output (Clay.com & n8n Ready)

```json
{
  "domain": "supabase.com",
  "pricing_page_url": "https://supabase.com/pricing",
  "sales_motion": "Hybrid (PLG Self-Serve + Enterprise Sales)",
  "pricing_model": "Hybrid (Per-Seat + Usage-Based)",
  "has_free_tier": true,
  "has_free_trial": false,
  "has_enterprise_tier": true,
  "lowest_paid_price_usd": 2.0,
  "price_points_detected": ["$0", "$2", "$3", "$5", "$10", "$25", "$60", "$75"],
  "price_points_csv": "$0, $2, $3, $5, $10, $25, $60, $75",
  "sso_saml_mentioned": true,
  "sso_tax_gated": true,
  "billing_stack": [],
  "billing_stack_csv": "",
  "gtm_summary": "supabase.com runs a Hybrid (PLG Self-Serve + Enterprise Sales) motion with Hybrid (Per-Seat + Usage-Based) pricing (Lowest paid tier: $2/mo, Free tier: Yes, Enterprise SSO-Tax gated: Yes)."
}
```

---

## 🔗 Companion Actor: Pair with Our Trust Center & SOC 2 Auditor
For complete B2B account intelligence in **Clay.com** or **n8n**, pair this Actor with:
- 🛡️ **[Trust Center, SOC 2 Compliance & IAM Technographic Auditor](https://apify.com/algernontechnologies/trust-center-iam-auditor)** — Extracts live Trust Center platforms (`Vanta`, `Drata`, `SafeBase`), `SOC 2` / `ISO 27001` / `HIPAA` certifications, `OpenAI` / `Anthropic` AI sub-processors, and DNS Identity stacks (`Okta`, `Entra ID`, `Wiz`).
- 📦 **[1-Click n8n & Clay.com Workflows (GitHub)](https://github.com/tobiaslofton/n8n-clay-b2b-trust-center-workflows)**

---

## 🤖 Use as a Model Context Protocol (MCP) Server

This repository includes both a **standalone local stdio MCP server** (`mcp_server.py`) and a **remote cloud MCP endpoint** hosted on Apify.

### Option A: Local `stdio` MCP Server (Zero API Keys Required)

Clone the repository and add it to your `claude_desktop_config.json`, Cursor, or Windsurf MCP settings:

```json
{
  "mcpServers": {
    "saas-pricing-sso-tax-auditor": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/saas-pricing-sso-tax-auditor",
        "run",
        "python",
        "mcp_server.py"
      ]
    }
  }
}
```

#### Exposed MCP Tools:
- `audit_saas_pricing(domain: str)` — Audits a single SaaS domain's pricing page for PLG vs. SLG sales motion, per-seat vs. usage-based pricing, starting USD price point, Enterprise SSO-Tax gating, and billing infrastructure (`Stripe`, `Chargebee`, `Paddle`, `Zuora`, `Orb`, `Metronome`).
- `batch_audit_saas_pricing(domains: list[str])` — Concurrently audits up to 15 SaaS domains in parallel.

### Option B: Remote Cloud MCP Server (via Apify)

```json
{
  "mcpServers": {
    "apify-saas-pricing-auditor": {
      "url": "https://mcp.apify.com?actors=algernontechnologies/saas-pricing-sso-tax-auditor",
      "headers": {
        "Authorization": "Bearer YOUR_APIFY_API_TOKEN"
      }
    }
  }
}
```
