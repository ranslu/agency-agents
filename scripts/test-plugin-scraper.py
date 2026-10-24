#!/usr/bin/env python3
"""Offline behavior checks for scripts/plugin-scraper.py and its helpers."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

spec = importlib.util.spec_from_file_location("plugin_scraper", ROOT / "scripts" / "plugin-scraper.py")
ps = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ps)

from plugin_categories import FALLBACK, categorise, infer_category  # noqa: E402
from plugin_vetting import vet  # noqa: E402


def entry(**kw):
    base = {"name": "x", "id": "x", "type": "mcp-server", "category": "remote",
            "description": "", "url": "https://example.com", "sources": ["mcp-registry"]}
    base.update(kw)
    return base


class Categories(unittest.TestCase):
    def test_infers_topic_from_description(self):
        self.assertEqual(infer_category("Acme", "com.acme/mcp", "Query Postgres and MySQL tables with SQL")[0], "Databases")

    def test_registry_id_host_words_do_not_count(self):
        # "github" in io.github.* ids used to send everything to Version Control.
        cat, _ = infer_category("io.github.jane/weather", "io.github.jane/weather", "Forecasts and weather alerts by city")
        self.assertEqual(cat, "Location Services")

    def test_billing_boilerplate_is_not_finance(self):
        cat, _ = infer_category("Shotz", "com.shotz/mcp", "Screenshot any web page. Paid per call via x402 in USDC.")
        self.assertEqual(cat, "Search & Data Extraction")

    def test_reports_is_not_a_repo(self):
        cat, _ = infer_category("Weekly", "com.weekly/mcp", "Weekly GA4 reports and SEO keyword research")
        self.assertEqual(cat, "Marketing")

    def test_no_match_falls_back(self):
        self.assertEqual(infer_category("Zzq", "com.zzq/mcp", "Qwerty plumbus")[0], FALLBACK)

    def test_categorise_keeps_listed_and_records_hosting(self):
        listed, generic = entry(category="Databases"), entry(category="remote", description="Send SMS and WhatsApp messages")
        categorise([listed, generic])
        self.assertEqual((listed["category"], listed["category_source"]), ("Databases", "listed"))
        self.assertEqual((generic["category"], generic["category_source"], generic["hosting"]),
                         ("Communication", "inferred", "remote"))


class Vetting(unittest.TestCase):
    def test_anthropic_marketplace_is_recommended(self):
        e = entry(type="claude-code-plugin", sources=["anthropics/claude-plugins-official"],
                  description="Manage Linear issues, projects and cycles from Claude Code.")
        vet([e])
        self.assertEqual(e["tier"], "recommended")

    def test_self_published_registry_entry_is_unvetted(self):
        e = entry(id="com.acme/mcp", url="https://acme.com", description="Look up Acme order status and shipping times.")
        vet([e])
        self.assertEqual(e["tier"], "unvetted")

    def test_temporary_tunnel_and_template_text_are_junk(self):
        tunnel = entry(id="com.trycloudflare.x/y", url="https://x.trycloudflare.com", description="Video generation for agents with voiceover.")
        template = entry(id="io.github.bob/thing", description="Thing MCP Server by Bob Labs")
        vet([tunnel, template])
        self.assertEqual(tunnel["tier"], "likely-junk")
        self.assertIn("-temporary-tunnel-url", tunnel["flags"])
        self.assertEqual(template["tier"], "likely-junk")

    def test_bulk_publisher_is_penalised(self):
        spam = [entry(id=f"io.github.spammer/s{i}", name=f"s{i}", description=f"Tool number {i} that converts units for agents") for i in range(45)]
        vet(spam)
        self.assertTrue(all("-bulk-publisher(45)" in e["flags"] for e in spam))


class Merge(unittest.TestCase):
    def test_merge_prefers_listed_category_over_registry_hosting(self):
        reg = entry(url="https://github.com/a/b", category="remote", description="short")
        awesome = entry(url="https://github.com/A/b.git", category="Databases", sources=["punkpeye/awesome-mcp-servers"],
                        description="A longer description of the same server")
        merged = ps.merge([reg, awesome])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["category"], "Databases")
        self.assertEqual(merged[0]["hosting"], "remote")
        self.assertEqual(merged[0]["sources"], ["mcp-registry", "punkpeye/awesome-mcp-servers"])

    def test_plugins_sharing_a_marketplace_repo_stay_separate(self):
        a = entry(type="claude-code-plugin", name="sales", url="https://github.com/anthropics/kw", sources=["m"])
        b = entry(type="claude-code-plugin", name="marketing", url="https://github.com/anthropics/kw", sources=["m"])
        self.assertEqual(len(ps.merge([a, b])), 2)

    def test_plugin_source_url_points_at_the_plugin_folder(self):
        self.assertEqual(ps.plugin_source_url("anthropics/kw", "./sales"), "https://github.com/anthropics/kw/tree/main/sales")
        sub = {"source": "git-subdir", "url": "https://github.com/acme/mono.git", "path": "plugins/x", "ref": "v1"}
        self.assertEqual(ps.plugin_source_url("m", sub), "https://github.com/acme/mono/tree/v1/plugins/x")
        self.assertEqual(ps.plugin_source_url("m", {"source": "github", "repo": "acme/p"}), "https://github.com/acme/p")


if __name__ == "__main__":
    unittest.main(verbosity=2)
