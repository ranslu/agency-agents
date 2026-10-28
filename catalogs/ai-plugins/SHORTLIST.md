# AI Plugin Shortlist for The Agency

Hand-picked plugins for each Agency division, chosen from catalogs/ai-plugins/plugins.json. Picks favour official vendor plugins and servers, Anthropic-maintained plugins, and widely used open-source servers. Every pick is checked against the catalog by scripts/build-shortlist.py.

163 picks across 20 groups. Tier is the catalog's heuristic vetting tier.

- [Core (every division)](#core-every-division) (11)
- [Engineering](#engineering) (25)
- [Engineering: data and databases](#engineering-data-and-databases) (15)
- [Testing](#testing) (7)
- [Security](#security) (12)
- [Design](#design) (8)
- [Product](#product) (7)
- [Project Management](#project-management) (6)
- [Marketing](#marketing) (9)
- [Paid Media](#paid-media) (4)
- [Sales](#sales) (9)
- [Support](#support) (7)
- [Finance](#finance) (9)
- [Research](#research) (8)
- [Academic](#academic) (6)
- [Healthcare](#healthcare) (4)
- [GIS](#gis) (3)
- [Game Development](#game-development) (3)
- [Spatial Computing](#spatial-computing) (3)
- [Specialized: legal, HR and AI ops](#specialized-legal-hr-and-ai-ops) (7)

## Core (every division)

| Plugin | Type | Tier | Why |
|---|---|---|---|
| [github](https://github.com/anthropics/claude-plugins-public/tree/main/external_plugins/github) | Claude Code plugin | recommended | Issues, PRs, code search and reviews; the backbone for any repo-based work. |
| [context7](https://github.com/anthropics/claude-plugins-public/tree/main/external_plugins/context7) | Claude Code plugin | recommended | Pulls current library docs into context so answers match the version in use. |
| [exa](https://exa.ai/docs/reference/exa-mcp) | Claude Code plugin | recommended | High-quality web search and content extraction built for agents. |
| [firecrawl](https://github.com/firecrawl/firecrawl-claude-plugin.git) | Claude Code plugin | recommended | Turns any site into clean markdown; reliable crawling for research tasks. |
| [zapier](https://github.com/zapier/zapier-mcp/tree/main/plugins/zapier) | Claude Code plugin | recommended | One connection to 8,000+ apps for cross-tool automation. |
| [skill-creator](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/skill-creator) | Claude Code plugin | recommended | Anthropic's tool for writing and testing new skills for the agents in this repo. |
| [plugin-dev](https://github.com/anthropics/claude-plugins-public/tree/main/plugins/plugin-dev) | Claude Code plugin | recommended | Anthropic's toolkit for building Claude Code plugins, hooks and commands. |
| [productivity](https://github.com/anthropics/knowledge-work-plugins/tree/main/productivity) | Claude Code plugin | recommended | Anthropic's knowledge-work plugin for tasks, memory and daily planning. |
| [enterprise-search](https://github.com/anthropics/knowledge-work-plugins/tree/main/enterprise-search) | Claude Code plugin | recommended | Anthropic's plugin for searching across connected work tools at once. |
| [modelcontextprotocol/server-filesystem](https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem) | MCP server | recommended | Reference filesystem server for controlled local file access. |
| [microsoft/markitdown](https://github.com/microsoft/markitdown/tree/main/packages/markitdown-mcp) | MCP server | ok | Converts PDFs, Office files and HTML to markdown for agents to read. |

## Engineering

| Plugin | Type | Tier | Why |
|---|---|---|---|
| [feature-dev](https://github.com/anthropics/claude-plugins-public/tree/main/plugins/feature-dev) | Claude Code plugin | recommended | Anthropic's structured explore-plan-build workflow for new features. |
| [code-review](https://github.com/anthropics/claude-plugins-public/tree/main/plugins/code-review) | Claude Code plugin | recommended | Anthropic's multi-agent PR review with confidence-filtered findings. |
| [pr-review-toolkit](https://github.com/anthropics/claude-plugins-public/tree/main/plugins/pr-review-toolkit) | Claude Code plugin | recommended | Specialised reviewers for tests, types, comments and silent failures. |
| [commit-commands](https://github.com/anthropics/claude-plugins-public/tree/main/plugins/commit-commands) | Claude Code plugin | recommended | Commit, push and open PRs with consistent messages. |
| [code-simplifier](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/code-simplifier) | Claude Code plugin | recommended | Cleans up recently changed code without changing behaviour. |
| [code-modernization](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/code-modernization) | Claude Code plugin | recommended | Guided assessment and migration plan for legacy codebases. |
| [typescript-lsp](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/typescript-lsp) | Claude Code plugin | recommended | Real type-checking and go-to-definition for TypeScript projects. |
| [pyright-lsp](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/pyright-lsp) | Claude Code plugin | recommended | Python type intelligence via Pyright. |
| [serena](https://github.com/anthropics/claude-plugins-public/tree/main/external_plugins/serena) | Claude Code plugin | recommended | Semantic code navigation and symbol-level editing across large repos. |
| [frontend-design](https://github.com/anthropics/claude-plugins-public/tree/main/plugins/frontend-design) | Claude Code plugin | recommended | Anthropic's skill for distinctive, production-grade frontend UI. |
| [replica-skill](https://github.com/Jakeschincariol/replica-skill) | Claude Code plugin | unvetted | Eleven skills that rebuild an app clean-room, recon to deploy; already in .claude/skills as /replica-*. |
| [chrome-devtools-mcp](https://github.com/ChromeDevTools/chrome-devtools-mcp) | Claude Code plugin | recommended | Debug a live browser: console, network, performance traces. |
| [gitkraken](https://www.gitkraken.com) | Claude Code plugin | recommended | Git context across repos, branches, PRs and issues. |
| [gitlab](https://github.com/anthropics/claude-plugins-public/tree/main/external_plugins/gitlab) | Claude Code plugin | recommended | Merge requests and pipelines for GitLab-hosted work. |
| [vercel](https://github.com/vercel/vercel-plugin) | Claude Code plugin | recommended | Deploy, inspect logs and manage projects on Vercel. |
| [cloudflare](https://github.com/cloudflare/skills) | Claude Code plugin | recommended | Workers, Durable Objects and the Agents SDK, from Cloudflare. |
| [com.cloudflare.mcp/mcp](https://github.com/cloudflare/mcp-server-cloudflare) | MCP server | recommended | Cloudflare's official server for configuring account resources. |
| [terraform](https://github.com/anthropics/claude-plugins-public/tree/main/external_plugins/terraform) | Claude Code plugin | recommended | Infrastructure-as-code with provider docs and plan review. |
| [azure](https://github.com/microsoft/azure-skills) | Claude Code plugin | recommended | Microsoft's Azure MCP server plus deployment skills. |
| [aws-agents](https://github.com/aws/agent-toolkit-for-aws) | Claude Code plugin | recommended | AWS's official agent toolkit for building and running on AWS. |
| [render](https://render.com) | Claude Code plugin | recommended | Deploy and troubleshoot services on Render. |
| [railway](https://docs.railway.com/ai/claude-code-plugin) | Claude Code plugin | recommended | Deploy and manage Railway projects from the terminal. |
| [firebase](https://github.com/anthropics/claude-plugins-public/tree/main/external_plugins/firebase) | Claude Code plugin | recommended | Firebase projects, Firestore and hosting from Google. |
| [microsoft-docs](https://github.com/microsoftdocs/mcp) | Claude Code plugin | recommended | Official Microsoft docs and code samples, always current. |
| [buildkite](https://buildkite.com) | Claude Code plugin | recommended | CI pipelines and build debugging on Buildkite. |

## Engineering: data and databases

| Plugin | Type | Tier | Why |
|---|---|---|---|
| [supabase](https://github.com/supabase-community/supabase-plugin) | Claude Code plugin | recommended | Postgres, auth, storage and edge functions on Supabase. |
| [neon](https://github.com/neondatabase/agent-skills/tree/main/plugins/neon-postgres) | Claude Code plugin | recommended | Serverless Postgres with branching, from Neon. |
| [prisma](https://prisma.io) | Claude Code plugin | recommended | Schema migrations and queries through Prisma. |
| [planetscale](https://planetscale.com/) | Claude Code plugin | recommended | PlanetScale databases, branches and deploy requests. |
| [mongodb](https://www.mongodb.com/docs/mcp-server/overview/) | Claude Code plugin | recommended | MongoDB's official server for queries and Atlas admin. |
| [redis-development](https://redis.io) | Claude Code plugin | recommended | Redis data modelling and commands, from Redis. |
| [clickhouse](https://github.com/ClickHouse/clickhouse-claude-code-plugin) | Claude Code plugin | recommended | Analytics queries on ClickHouse Cloud. |
| [neo4j-contrib/mcp-neo4j](https://github.com/neo4j-contrib/mcp-neo4j) | MCP server | recommended | Graph queries and memory on Neo4j. |
| [qdrant-skills](https://skills.qdrant.tech) | Claude Code plugin | recommended | Vector search design and tuning from Qdrant. |
| [pinecone](https://github.com/pinecone-io/pinecone-claude-code-plugin) | Claude Code plugin | recommended | Managed vector indexes for RAG, from Pinecone. |
| [dbt-labs/dbt-mcp](https://github.com/dbt-labs/dbt-mcp) | MCP server | recommended | dbt models, lineage and runs from dbt Labs. |
| [snowflake-cortex-code](https://docs.snowflake.com/en/user-guide/cortex-code) | Claude Code plugin | recommended | Snowflake's coding agent for SQL and data apps. |
| [bigquery-data-analytics](https://github.com/gemini-cli-extensions/bigquery-data-analytics) | Claude Code plugin | recommended | Query and analyse BigQuery datasets. |
| [databricks](https://developers.databricks.com/) | Claude Code plugin | recommended | Databricks notebooks, jobs and Unity Catalog. |
| [data](https://github.com/astronomer/agents) | Claude Code plugin | recommended | Airflow DAG authoring and debugging from Astronomer. |

## Testing

| Plugin | Type | Tier | Why |
|---|---|---|---|
| [playwright](https://github.com/anthropics/claude-plugins-public/tree/main/external_plugins/playwright) | Claude Code plugin | ok | Drive real browsers for end-to-end tests and repros. |
| [microsoft/playwright-mcp](https://github.com/microsoft/playwright-mcp) | MCP server | recommended | Microsoft's Playwright server using accessibility snapshots. |
| [browser-use](https://browser-use.com) | Claude Code plugin | recommended | Agent-driven browsing for exploratory QA flows. |
| [Currents](https://github.com/currents-dev/currents-mcp) | MCP server | recommended | Fix flaky and failing Playwright tests from Currents reports. |
| [codspeed](https://codspeed.io) | Claude Code plugin | recommended | Benchmarks and performance regressions in CI. |
| [mergify](https://mergify.com) | Claude Code plugin | recommended | Merge queues and flaky-test insights. |
| [growthbook](https://growthbook.io) | Claude Code plugin | recommended | Feature flags and A/B experiments for safe rollouts. |

## Security

| Plugin | Type | Tier | Why |
|---|---|---|---|
| [security-guidance](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/security-guidance) | Claude Code plugin | recommended | Anthropic's hook that warns on risky code patterns as you write. |
| [claude-security](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/claude-security) | Claude Code plugin | recommended | Anthropic's security review workflow for code changes. |
| [semgrep](https://github.com/semgrep/mcp-marketplace.git) | Claude Code plugin | recommended | Static analysis that flags vulnerabilities in real time. |
| [snyk/studio-mcp](https://github.com/snyk/studio-mcp) | MCP server | ok | Dependency, code and container scanning from Snyk. |
| [sonarqube](https://www.sonarsource.com) | Claude Code plugin | recommended | Code quality and security gates in the agent loop. |
| [aikido](https://github.com/AikidoSec/aikido-claude-plugin) | Claude Code plugin | recommended | SAST, secrets and IaC scanning from Aikido. |
| [stackhawk-hawkscan](https://docs.stackhawk.com/ai-security/) | Claude Code plugin | recommended | Dynamic application security testing (DAST) on running apps. |
| [sonatype-guide](https://github.com/sonatype/sonatype-guide-claude-plugin.git) | Claude Code plugin | recommended | Supply-chain risk and safer dependency versions. |
| [vanta-mcp-plugin](https://help.vanta.com/en/articles/14094979-connecting-to-vanta-mcp#h_887ce3f337) | Claude Code plugin | recommended | SOC 2 and ISO compliance tests and evidence in Vanta. |
| [auth0](https://auth0.com) | Claude Code plugin | recommended | Login, MFA and migrations done the Auth0 way. |
| [workos](https://workos.com) | Claude Code plugin | recommended | Enterprise SSO, directory sync and RBAC from WorkOS. |
| [io.github.BurtTheCoder/shodan](https://github.com/BurtTheCoder/mcp-shodan) | MCP server | recommended | Internet exposure and CVE lookups for recon. |

## Design

| Plugin | Type | Tier | Why |
|---|---|---|---|
| [figma](https://github.com/figma/mcp-server-guide) | Claude Code plugin | recommended | Read Figma frames, variables and components to build matching UI. |
| [design](https://github.com/anthropics/knowledge-work-plugins/tree/main/design) | Claude Code plugin | recommended | Anthropic's design plugin: critiques, specs and handoff docs. |
| [canva](https://www.canva.com) | Claude Code plugin | recommended | Create, resize and brand-check Canva designs. |
| [adobe-for-creativity](https://github.com/adobe/skills/tree/main/plugins/creative-cloud/adobe-for-creativity) | Claude Code plugin | recommended | Adobe Creative Cloud edits: background removal, vectorising, retouching. |
| [miro](https://miro.com) | Claude Code plugin | recommended | Read and create Miro boards and diagrams. |
| [cloudinary](https://cloudinary.com/documentation) | Claude Code plugin | recommended | Image and video transformations and asset management. |
| [Excalidraw Architect](https://github.com/BV-Venky/excalidraw-architect-mcp) | MCP server | recommended | Generates architecture diagrams as editable Excalidraw files. |
| [ai.smithery/hustcc-mcp-mermaid](https://github.com/hustcc/mcp-mermaid) | MCP server | recommended | Renders Mermaid diagrams for docs and specs. |

## Product

| Plugin | Type | Tier | Why |
|---|---|---|---|
| [product-management](https://github.com/anthropics/knowledge-work-plugins/tree/main/product-management) | Claude Code plugin | recommended | Anthropic's PM plugin: specs, roadmaps and research synthesis. |
| [linear](https://github.com/anthropics/claude-plugins-public/tree/main/external_plugins/linear) | Claude Code plugin | recommended | Issues, projects and cycles in Linear. |
| [amplitude](https://github.com/amplitude/mcp-marketplace) | Claude Code plugin | recommended | Product analytics charts and cohorts from Amplitude. |
| [posthog](https://posthog.com/docs/model-context-protocol) | Claude Code plugin | recommended | Product analytics, session replay and flags from PostHog. |
| [pendo-analytics](https://github.com/pendo-io/claude-pendo-plugin/tree/main/plugins/pendo-analytics) | Claude Code plugin | recommended | Feature adoption and account health from Pendo. |
| [product-tracking-skills](https://www.accoil.com/product-tracking) | Claude Code plugin | recommended | Designs and audits event tracking plans. |
| [mintlify](https://www.mintlify.com/) | Claude Code plugin | recommended | Writes and publishes product documentation sites. |

## Project Management

| Plugin | Type | Tier | Why |
|---|---|---|---|
| [atlassian](https://github.com/atlassian/atlassian-mcp-server) | Claude Code plugin | recommended | Atlassian's official Jira and Confluence server. |
| [asana](https://github.com/anthropics/claude-plugins-public/tree/main/external_plugins/asana) | Claude Code plugin | recommended | Tasks, projects and status updates in Asana. |
| [notion](https://github.com/makenotion/claude-code-notion-plugin) | Claude Code plugin | recommended | Notion's official plugin for pages and databases. |
| [monday-com](https://monday.com) | Claude Code plugin | recommended | Boards, items and docs on monday.com. |
| [airtable](https://www.airtable.com) | Claude Code plugin | recommended | Airtable bases as a lightweight ops database. |
| [operations](https://github.com/anthropics/knowledge-work-plugins/tree/main/operations) | Claude Code plugin | recommended | Anthropic's ops plugin: runbooks, status reports, change requests. |

## Marketing

| Plugin | Type | Tier | Why |
|---|---|---|---|
| [marketing](https://github.com/anthropics/knowledge-work-plugins/tree/main/marketing) | Claude Code plugin | recommended | Anthropic's marketing plugin: campaigns, content and reporting. |
| [brand-voice](https://github.com/anthropics/knowledge-work-plugins/tree/main/partner-built/brand-voice) | Claude Code plugin | recommended | Builds brand guidelines and keeps content on-voice. |
| [searchfit-seo](https://searchfit.ai) | Claude Code plugin | recommended | SEO audits, keyword clusters and content strategy. |
| [activecampaign](https://www.activecampaign.com) | Claude Code plugin | recommended | Email automation, lists and campaign reporting. |
| [resend](https://resend.com) | Claude Code plugin | recommended | Transactional and marketing email from code. |
| [postiz](https://postiz.com/agent) | Claude Code plugin | recommended | Schedules and manages posts across social networks. |
| [sanity-plugin](https://www.sanity.io) | Claude Code plugin | recommended | Content modelling and publishing on Sanity CMS. |
| [wix](https://dev.wix.com/docs/wix-cli/guides/development/about-wix-skills) | Claude Code plugin | recommended | Build and manage Wix sites and apps. |
| [brightdata-plugin](https://docs.brightdata.com) | Claude Code plugin | recommended | Brand listening, competitor and SERP data at scale. |

## Paid Media

| Plugin | Type | Tier | Why |
|---|---|---|---|
| [adspirer-ads-agent](https://www.adspirer.com) | Claude Code plugin | recommended | One agent across Google, Meta, LinkedIn, TikTok and Amazon Ads. |
| [gomarble-ai/google-ads-mcp-server](https://github.com/gomarble-ai/google-ads-mcp-server) | MCP server | ok | Google Ads campaigns, keywords and performance. |
| [mikusnuz/meta-ads-mcp](https://github.com/mikusnuz/meta-ads-mcp) | MCP server | ok | Meta (Facebook and Instagram) ad campaigns and insights. |
| [amazon-selling-partner](https://github.com/amzn/selling-partner-agentic-toolkit) | Claude Code plugin | recommended | Amazon seller data: listings, orders and advertising. |

## Sales

| Plugin | Type | Tier | Why |
|---|---|---|---|
| [sales](https://github.com/anthropics/knowledge-work-plugins/tree/main/sales) | Claude Code plugin | recommended | Anthropic's sales plugin: call prep, pipeline and outreach. |
| [hubspot-sales](https://www.hubspot.com) | Claude Code plugin | recommended | HubSpot CRM deals, contacts and sequences. |
| [salesforce-development](https://github.com/forcedotcom/sf-skills/tree/main/plugins/builder/salesforce-development) | Claude Code plugin | recommended | Salesforce's own skills for building on the platform. |
| [apollo](https://www.apollo.io/) | Claude Code plugin | recommended | Prospecting and enrichment from Apollo.io. |
| [zoominfo](https://www.zoominfo.com) | Claude Code plugin | recommended | Company and contact intelligence, intent and lookalikes. |
| [common-room](https://github.com/anthropics/knowledge-work-plugins/tree/main/partner-built/common-room) | Claude Code plugin | recommended | Buyer signals and account research from Common Room. |
| [lusha](https://www.lusha.com) | Claude Code plugin | recommended | Contact enrichment and call-ready lead lists. |
| [leadfeeder](https://www.leadfeeder.com) | Claude Code plugin | recommended | Turns website visitors into named leads. |
| [monday-crm](https://monday.com) | Claude Code plugin | recommended | Pipeline management in monday CRM. |

## Support

| Plugin | Type | Tier | Why |
|---|---|---|---|
| [customer-support](https://github.com/anthropics/knowledge-work-plugins/tree/main/customer-support) | Claude Code plugin | recommended | Anthropic's support plugin: triage, drafts and KB articles. |
| [intercom](https://github.com/intercom/claude-plugin-external) | Claude Code plugin | recommended | Intercom conversations, tickets and help-centre content. |
| [michaelrice/zendesk-mcp](https://github.com/michaelrice/zendesk-mcp) | MCP server | ok | Zendesk tickets and macros. |
| [slack](https://github.com/slackapi/slack-mcp-plugin/tree/main) | Claude Code plugin | recommended | Slack's official server for channels, search and messages. |
| [twilio-developer-kit](https://www.twilio.com) | Claude Code plugin | recommended | SMS, voice and WhatsApp support channels via Twilio. |
| [zoom-plugin](https://developers.zoom.us/) | Claude Code plugin | recommended | Zoom meetings, recordings and transcripts. |
| [incident-io](https://incident.io) | Claude Code plugin | recommended | Incident response and status updates. |

## Finance

| Plugin | Type | Tier | Why |
|---|---|---|---|
| [finance](https://github.com/anthropics/knowledge-work-plugins/tree/main/finance) | Claude Code plugin | recommended | Anthropic's finance plugin: close, reconciliations, variance analysis. |
| [intuit-quickbooks](https://github.com/intuit/quickbooks-claude-plugin) | Claude Code plugin | recommended | QuickBooks books, reports and actions from Intuit. |
| [XeroAPI/xero-mcp-server](https://github.com/XeroAPI/xero-mcp-server) | MCP server | recommended | Xero's official accounting server. |
| [stripe](https://github.com/stripe/ai/tree/main/providers/claude/plugin) | Claude Code plugin | recommended | Payments, customers and billing from Stripe. |
| [netsuite-finance-analyst](https://github.com/oracle/netsuite-suitecloud-sdk/tree/ai-plugins-dist/anthropic/netsuite-finance-analyst) | Claude Code plugin | recommended | NetSuite ERP analysis from Oracle. |
| [daloopa](https://github.com/daloopa/plugin) | Claude Code plugin | recommended | Institutional-grade company financials and models. |
| [lseg](https://github.com/LSEG-API-Samples/lseg-claude-plugin) | Claude Code plugin | recommended | Bond, curve and FX analytics from LSEG data. |
| [sp-global](https://kensho.com) | Claude Code plugin | recommended | S&P Global company data, tear sheets and earnings prep. |
| [com.twelvedata/mcp](https://github.com/twelvedata/mcp) | MCP server | recommended | Market data for stocks, FX and crypto. |

## Research

| Plugin | Type | Tier | Why |
|---|---|---|---|
| [tavily](https://www.tavily.com/) | Claude Code plugin | recommended | Search, extract and research endpoints tuned for agents. |
| [ai.smithery/brave](https://github.com/brave/brave-search-mcp-server) | MCP server | recommended | Brave Search: independent index, privacy-friendly. |
| [Perplexity](https://github.com/ppl-ai/modelcontextprotocol) | MCP server | ok | Perplexity's cited answers and research mode. |
| [apify/actors-mcp-server](https://github.com/apify/actors-mcp-server) | MCP server | recommended | Thousands of ready-made scrapers via Apify Actors. |
| [nimble](https://docs.nimbleway.com/integrations/agent-skills/plugin-installation) | Claude Code plugin | recommended | Web data at scale: search, extract, map and crawl. |
| [unstructured-foundation](https://unstructured.io) | Claude Code plugin | recommended | Parses messy documents into searchable chunks. |
| [box](https://github.com/box/skills) | Claude Code plugin | recommended | Search and act on Box content. |
| [dropbox](https://www.dropbox.com) | Claude Code plugin | recommended | Find and organise Dropbox files. |

## Academic

| Plugin | Type | Tier | Why |
|---|---|---|---|
| [blazickjp/arxiv-mcp-server](https://github.com/blazickjp/arxiv-mcp-server) | MCP server | ok | Search and read arXiv papers. |
| [andybrandt/mcp-simple-pubmed](https://github.com/andybrandt/mcp-simple-pubmed) | MCP server | ok | PubMed search and abstracts. |
| [kaliaboi/mcp-zotero](https://github.com/kaliaboi/mcp-zotero) | MCP server | ok | Your Zotero library and citations. |
| [learn-with-coursera](https://github.com/coursera/skills) | Claude Code plugin | recommended | Personalised Coursera learning paths. |
| [math-proof](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/math-proof) | Claude Code plugin | recommended | Anthropic's skill for writing and checking proofs. |
| [huggingface-skills](https://github.com/huggingface/skills.git) | Claude Code plugin | recommended | Models, datasets and training jobs on Hugging Face. |

## Healthcare

| Plugin | Type | Tier | Why |
|---|---|---|---|
| [bio-research](https://github.com/anthropics/knowledge-work-plugins/tree/main/bio-research) | Claude Code plugin | recommended | Anthropic's bio-research plugin: literature, trials and pipelines. |
| [maven-bio](https://mavenbio.com/mcp/docs) | Claude Code plugin | recommended | Evidence-backed biopharma research workflows. |
| [wso2/fhir-mcp-server](https://github.com/wso2/fhir-mcp-server) | MCP server | recommended | Read and write FHIR clinical records. |
| [boltz](https://boltz.bio) | Claude Code plugin | recommended | Protein structure prediction and molecule screening. |

## GIS

| Plugin | Type | Tier | Why |
|---|---|---|---|
| [mapbox](https://www.mapbox.com) | Claude Code plugin | recommended | Maps, geocoding, routing and static map images. |
| [amazon-location-service](https://github.com/awslabs/agent-plugins) | Claude Code plugin | recommended | AWS maps, places and routes. |
| [HasData Google Maps](https://github.com/HasData/google-maps-mcp) | MCP server | recommended | Google Maps places and reviews data. |

## Game Development

| Plugin | Type | Tier | Why |
|---|---|---|---|
| [unity](https://unity.com) | Claude Code plugin | recommended | Unity's official plugin for building and shipping games. |
| [unreal-engine-skills-for-claude-code](https://dev.epicgames.com/documentation/unreal-engine/unreal-mcp-in-unreal-editor) | Claude Code plugin | recommended | Epic's plugin to control Unreal Editor. |
| [beckettlab/beckett-godot-mcp](https://github.com/beckettlab/beckett-godot-mcp) | MCP server | ok | Drives the Godot editor for scenes and scripts. |

## Spatial Computing

| Plugin | Type | Tier | Why |
|---|---|---|---|
| [ahujasid/blender-mcp](https://github.com/ahujasid/blender-mcp) | MCP server | ok | Create and edit 3D scenes in Blender. |
| [swift-lsp](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/swift-lsp) | Claude Code plugin | recommended | Swift language intelligence for visionOS and iOS apps. |
| [r-huijts/xcode-mcp-server](https://github.com/r-huijts/xcode-mcp-server) | MCP server | ok | Build, run and test Xcode projects. |

## Specialized: legal, HR and AI ops

| Plugin | Type | Tier | Why |
|---|---|---|---|
| [legal](https://github.com/anthropics/knowledge-work-plugins/tree/main/legal) | Claude Code plugin | recommended | Anthropic's legal plugin: contract review, NDA triage, compliance. |
| [human-resources](https://github.com/anthropics/knowledge-work-plugins/tree/main/human-resources) | Claude Code plugin | recommended | Anthropic's HR plugin: hiring, onboarding, reviews. |
| [langfuse](https://langfuse.com) | Claude Code plugin | recommended | Traces, evals and prompt management for LLM apps. |
| [deepeval](https://github.com/confident-ai/deepeval) | Claude Code plugin | recommended | Evaluation suites for agent and LLM output quality. |
| [datadog](https://www.datadoghq.com/) | Claude Code plugin | recommended | Datadog logs, metrics and traces through its MCP server. |
| [sentry](https://github.com/getsentry/plugin-claude) | Claude Code plugin | recommended | Errors, stack traces and releases from Sentry. |
| [grafana-assistant](https://grafana.com) | Claude Code plugin | recommended | Dashboards and observability queries on Grafana Cloud. |
