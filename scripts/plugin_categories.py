"""Keyword categoriser for AI plugins that arrive without a topic category.

The MCP Registry only says whether a server is hosted ("remote") or installable
("package"), so those entries get a topic inferred from their name, id and
description. Category names follow punkpeye/awesome-mcp-servers so inferred and
listed entries share one taxonomy.

Each rule is a list of regex stems matched at word starts. A hit in the name or
id counts double. The highest score wins; ties go to the rule listed first, so
narrow categories sit above broad ones. No hit means "Other Tools and
Integrations".
"""
import re

FALLBACK = "Other Tools and Integrations"

# Categories that describe where an entry came from, not what it does.
GENERIC = {
    "", "remote", "package", "uncategorized", "Official Servers", "Clients",
    "Archived", "Server Managers", FALLBACK,
}

# Payment boilerplate ("paid per call via x402 in USDC") says how a server
# bills, not what it does, and would otherwise pull hundreds into Finance.
BILLING_NOISE = re.compile(
    r"\b(?:paid|pay|billed|priced)\b[^.;]{0,40}?\b(?:x402|usdc|api key|micropayments?)\b"
    r"|\bx402\b|\bmicropayments?\b|\bpay[- ]per[- ](?:call|use|request)\b",
    re.I,
)

RULES = [
    ("Version Control", r"git\b github gitlab bitbucket pull.?request commits?\b repos?\b repositor git.?branch code.?review"),
    ("Code Execution", r"sandbox code.?execut run.?code repl jupyter notebook interpreter e2b"),
    ("Command Line", r"shell terminal command.?line cli\b bash ssh\b"),
    ("Coding Agents", r"coding.?agent code.?gen refactor codebase ide\b vscode cursor claude.?code copilot"),
    ("Developer Tools", r"developer dev.?tool api.?(?:test|doc|spec|client|mock|design) openapi swagger postman sdk(?:s)? documentation docs\b lint debug ci\b ci.?cd test(?:s|ing)?\b npm pypi packag(?:e|ing).?(?:registry|manager) webhook regex json\b yaml graphql rest.?api http.?client"),
    ("Browser Automation", r"browser playwright puppeteer selenium headless chrome web.?automation"),
    ("Search & Data Extraction", r"scrap crawl web.?search search.?engine serp extract(?:ion)? screenshot ocr pdf\b parse(?:r)? enrichment"),
    ("Databases", r"database sql postgres mysql sqlite mongo redis supabase dynamo cassandra neo4j clickhouse vector.?(?:db|store|database) pinecone qdrant"),
    ("Data Platforms", r"data.?warehouse snowflake bigquery databricks etl\b data.?pipeline kafka airflow dbt\b"),
    ("Data Visualization", r"chart graph(?:s|ing)?\b dashboard visuali[sz] plot"),
    ("Data Science Tools", r"machine.?learning ml\b statistic dataset pandas forecast(?:ing)? analytic"),
    ("Cloud Platforms", r"aws\b azure gcp google.?cloud cloudflare kubernetes k8s docker terraform serverless vercel netlify heroku deploy hosting dns\b domain"),
    ("Monitoring", r"monitor observab logging logs\b metric uptime incident alert(?:s|ing)? sentry datadog grafana prometheus trac(?:e|ing)\b error.?track stack.?trace status.?page"),
    ("Security", r"secur vulnerab pentest threat malware phishing cve\b oauth auth\b authenticat authoriz secret vault compliance sanction kyc\b aml\b fraud privacy encrypt firewall soc.?2 audit governance polic(?:y|ies) permission access.?control mandate"),
    ("Finance & Fintech", r"financ stock equit trading trader invest portfolio market.?data bank payment invoice accounting tax(?:es)?\b crypto blockchain defi wallet token(?:s|ized)?\b solana ethereum bitcoin web3 nft forex fx\b loan mortgage insurance budget expense fintech sec.?filing earnings dividend options\b perps prediction.?market gold silver valuation"),
    ("E-Commerce", r"e.?commerce shop(?:ify|ping)? product.?catalog store\b retail cart checkout amazon ebay etsy woocommerce inventory order(?:s)?\b price.?compar coupon deal(?:s)?\b gift restock"),
    ("Marketing", r"marketing seo\b ads?\b advertis campaign brand(?:ing)? lead.?gen newsletter email.?marketing analytics.?4 google.?analytics conversion keyword backlink geo\b"),
    ("Customer Data Platforms", r"crm\b salesforce hubspot customer.?data pipedrive sales.?pipeline prospect"),
    ("Support & Service Management", r"support.?ticket helpdesk help.?desk zendesk intercom freshdesk customer.?support service.?desk itsm servicenow"),
    ("Social Media", r"social.?media twitter tweet x\.com instagram tiktok facebook linkedin reddit youtube bluesky mastodon threads\b influencer"),
    ("Communication", r"email gmail outlook slack discord telegram whatsapp sms\b chat(?:s)?\b messag notification teams\b voice.?call phone call(?:s)?\b twilio inbox poll(?:s)?\b"),
    ("Workplace & Productivity", r"productiv task(?:s)?\b todo calendar schedul meeting notion jira asana trello confluence project.?manage spreadsheet google.?(?:docs|sheets|drive) office excel word\b docx document workflow kanban note(?:s)?\b"),
    ("Product Management", r"product.?manag roadmap user.?feedback feature.?request backlog okr"),
    ("Knowledge & Memory", r"memory memories knowledge.?(?:base|graph) rag\b retriev embedding semantic.?search second.?brain context.?(?:store|engine) wiki"),
    ("AI Models & Agent Infrastructure", r"llm(?:s)?\b inference model(?:s)?\b openai gpt gemini anthropic ollama prompt multi.?agent agent.?(?:orchestr|framework|registry|network|identity|economy|commerce|marketplace) orchestrat agent.?fleet coordinat guardrail eval(?:s|uation)?\b fine.?tun"),
    ("Aggregators", r"gateway aggregat registry mcp.?(?:hub|proxy|router|marketplace|directory) unified.?api integrations? platform zapier make\.com n8n"),
    ("Multimedia Process", r"image video audio music photo speech text.?to.?speech tts\b transcri voice(?:over)? podcast media render 3d\b ffmpeg generat(?:e|ion).?(?:image|video)"),
    ("Art & Culture", r"art(?:s|work|ist)?\b museum culture book(?:s)?\b literature poetry movie film anime manga history recipe cook"),
    ("Architecture & Design", r"design figma ui\b ux\b whiteboard diagram cad\b architect"),
    ("Gaming", r"game gaming minecraft roblox unity\b unreal steam chess poker"),
    ("Sports", r"sport football soccer nba nfl golf fitness workout tennis cricket baseball f1\b betting odds cycling running hiking"),
    ("Travel & Transportation", r"travel flight hotel airline airport visa trip booking transit train(?:s)?\b vehicle car(?:s)?\b ev\b charging tourism"),
    ("Location Services", r"map(?:s)?\b geocod location gps weather geo.?spatial address(?:es)?\b place(?:s)?\b"),
    ("Delivery", r"deliver shipping shipment package(?:s)?\b track(?:ing)?.?(?:package|parcel) logistic courier freight carrier"),
    ("Real Estate", r"real.?estate propert housing rent(?:al)? mortgage zillow apartment realtor"),
    ("Legal", r"legal law(?:s|yer)?\b contract court case.?law regulat attorney patent trademark redlin"),
    ("Education", r"educat learn(?:ing)?\b course student school teach tutor quiz flashcard exam language.?learning"),
    ("Health & Wellness", r"health medical clinic patient doctor nutrition diet mental.?health wellness sleep pharma drug"),
    ("Biology, Medicine and Bioinformatics", r"biolog bioinformat genom protein molecul chem pubmed clinical.?trial gene\b"),
    ("Research", r"research paper(?:s)?\b arxiv scholar academic citation scientific math theorem"),
    ("Environment & Nature", r"climate environment carbon emission energy solar nature ecolog agricultur"),
    ("Home Automation", r"smart.?home home.?assistant iot\b thermostat light(?:s|ing)?\b"),
    ("Jobs", r"job(?:s)?\b hiring recruit resume career talent applicant hr\b payroll"),
    ("Spirituality & Esoterica", r"astrolog tarot horoscope bible quran religio spiritual"),
    ("File Systems", r"file(?:s)?\b filesystem storage s3\b dropbox box\b convert(?:er)?"),
    ("Government & Public Data", r"government public.?(?:data|records) civic open.?data census municipal federal parliament legislat election"),
    ("Food & Dining", r"food restaurant recipe cater menu grocery dining wine coffee"),
    ("Translation Services", r"translat locali[sz] multilingual"),
]

_COMPILED = [
    (name, re.compile(r"\b(?:" + "|".join(stems.split()) + r")", re.I))
    for name, stems in RULES
]


# Reverse-DNS and host words in registry ids ("io.github.user/x",
# "ai.smithery/x") name the publisher's hosting, not the plugin's topic.
ID_NOISE = re.compile(r"\b(?:io|com|ai|dev|app|net|org|co|sh|github|gitlab|smithery|mcp|server)\b", re.I)


def infer_category(name, ident, description):
    """Return (category, score) for one entry; score 0 means fallback."""
    ident = ID_NOISE.sub(" ", re.sub(r"[./]", " ", ident or ""))
    name = ID_NOISE.sub(" ", re.sub(r"[./]", " ", name)) if re.fullmatch(r"[\w.-]+/[\w.-]+", name or "") else name
    head = BILLING_NOISE.sub(" ", f"{name} {ident}".replace("-", " ").replace("_", " "))
    body = BILLING_NOISE.sub(" ", description or "")
    best, best_score = FALLBACK, 0
    for cat, rx in _COMPILED:
        score = 2 * len(rx.findall(head)) + len(rx.findall(body))
        if score > best_score:
            best, best_score = cat, score
    return best, best_score


def categorise(entries):
    """Fill in a topic for entries whose category is generic, in place."""
    for e in entries:
        if e.get("category", "") in ("remote", "package"):
            e.setdefault("hosting", e["category"])
        if e.get("category", "") in GENERIC:
            e["category"], _ = infer_category(e.get("name", ""), e.get("id", ""), e.get("description", ""))
            e["category_source"] = "inferred"
        else:
            e.setdefault("category_source", "listed")
    return entries
