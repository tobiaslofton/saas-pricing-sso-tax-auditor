# 💸 B2B SaaS Pricing Model, PLG & Enterprise "SSO-Tax" Auditor — MCP Server

[![tobiaslofton/saas-pricing-sso-tax-auditor MCP server](https://glama.ai/mcp/servers/tobiaslofton/saas-pricing-sso-tax-auditor/badges/score.svg)](https://glama.ai/mcp/servers/tobiaslofton/saas-pricing-sso-tax-auditor)

A standalone, self-contained **Model Context Protocol (MCP) Server** written in Python (`mcp_server.py`) that enables AI assistants (Claude Desktop, Cursor, Windsurf, Cline, and custom MCP clients) to inspect any B2B SaaS domain's pricing pages and extract its **Go-To-Market (GTM) sales motion**, **pricing model**, **starting USD price point**, **free tier / trial availability**, **billing infrastructure stack**, and whether **SAML / SSO is gated behind an Enterprise plan ("SSO Tax")** directly over local `stdio`.

Zero third-party API keys or external cloud subscriptions are required. All HTTP probing (`httpx`) and HTML/DOM pricing extraction (`BeautifulSoup4`) run locally inside the MCP server process.

---

## 🔧 MCP Tools Provided

This MCP server exposes two tools over JSON-RPC 2.0 `stdio`:

### 1. `audit_saas_pricing`
Audits a single B2B SaaS domain's pricing page (`/pricing`, `/plans`) to extract its sales motion, pricing model, lowest paid tier, Free Tier/Trial flags, Enterprise SSO/SAML gating, and billing stack.
- **Input Schema:**
  - `domain` (`string`, required): Target SaaS domain (e.g., `"linear.app"`, `"supabase.com"`, `"figma.com"`).

### 2. `batch_audit_saas_pricing`
Concurrently audits up to 15 B2B SaaS domains in parallel.
- **Input Schema:**
  - `domains` (`array[string]`, required): List of SaaS domains to inspect concurrently.

---

## 📦 Installation & Local MCP Configuration

### Prerequisites
- Python 3.11+ (or Docker)
- Dependencies: `httpx`, `beautifulsoup4`, `pydantic`

```bash
git clone https://github.com/tobiaslofton/saas-pricing-sso-tax-auditor.git
cd saas-pricing-sso-tax-auditor
pip install -r requirements.txt
```

### Option 1: Claude Desktop / Cursor / Windsurf (`python` or `uv` over `stdio`)

Add the following entry to your `claude_desktop_config.json` or `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "saas-pricing-sso-tax-auditor": {
      "command": "python",
      "args": [
        "/absolute/path/to/saas-pricing-sso-tax-auditor/mcp_server.py"
      ]
    }
  }
}
```

Or using `uv`:

```json
{
  "mcpServers": {
    "saas-pricing-sso-tax-auditor": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/saas-pricing-sso-tax-auditor",
        "run",
        "python",
        "mcp_server.py"
      ]
    }
  }
}
```

### Option 2: Run via Docker (`stdio`)

Build the local image and connect via `docker run -i`:

```bash
docker build -t saas-pricing-sso-tax-auditor .
```

```json
{
  "mcpServers": {
    "saas-pricing-sso-tax-auditor": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "saas-pricing-sso-tax-auditor"
      ]
    }
  }
}
```

---

## 🚀 Extracted Signals & Schema

| Field | Description |
| :--- | :--- |
| **`sales_motion`** | Classifies as `Product-Led Growth (PLG Self-Serve)`, `Hybrid (PLG Self-Serve + Enterprise Sales)`, or `Enterprise Sales-Led (SLG)`. |
| **`pricing_model`** | Detects `Per-Seat / User Subscription`, `Usage-Based / Pay-As-You-Go`, `Hybrid (Per-Seat + Usage-Based)`, `Tiered Flat Subscription`, or `Enterprise Custom Quote Only`. |
| **`lowest_paid_price_usd`** | Extracts the entry-level paid price point in USD (e.g., `8.0`, `10.0`, `25.0`). |
| **`price_points_detected`** | Array of all detected tier price points (e.g., `["$0", "$8", "$14", "$25"]`). |
| **`has_free_tier` / `has_free_trial`** | Boolean flags indicating self-serve Free Forever or time-boxed trial availability. |
| **`sso_tax_gated`** | Detects whether SAML / Okta / SCIM / Single Sign-On is gated behind an Enterprise plan. |
| **`billing_stack`** | Fingerprints payment/subscription scripts (`Stripe`, `Chargebee`, `Paddle`, `Recurly`, `Zuora`, `Maxio / Chargify`, `Orb Billing`, `Metronome`). |
| **`gtm_summary`** | Concise human-readable summary of the vendor's packaging and GTM posture. |

---

## 📊 Example Tool Output (`audit_saas_pricing`)

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
  "sso_saml_mentioned": true,
  "sso_tax_gated": true,
  "billing_stack": [],
  "gtm_summary": "supabase.com runs a Hybrid (PLG Self-Serve + Enterprise Sales) motion with Hybrid (Per-Seat + Usage-Based) pricing (Lowest paid tier: $2/mo, Free tier: Yes, Enterprise SSO-Tax gated: Yes)."
}
```

---

## 📄 License

MIT License — see [LICENSE](LICENSE).
