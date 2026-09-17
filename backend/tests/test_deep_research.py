"""Tests for the deep research engine."""
from __future__ import annotations

import pytest

from app.deep_research import (
    _expand_queries,
    _extract_year,
    _extract_domain,
    _categorize,
    _build_summary,
    _result_to_node,
    _group_nodes,
    _generate_topic_summary,
)


class TestExpandQueries:
    def test_generates_multiple_queries(self):
        queries = _expand_queries("artificial intelligence", max_queries=6)
        assert len(queries) >= 3
        assert len(queries) <= 6
        assert "artificial intelligence" in queries

    def test_respects_max_queries(self):
        queries = _expand_queries("topic", max_queries=2)
        assert len(queries) <= 2

    def test_deduplicates(self):
        queries = _expand_queries("test", max_queries=10)
        assert len(queries) == len(set(q.lower() for q in queries))


class TestExtractYear:
    def test_extracts_from_text(self):
        assert _extract_year("Published in 2023") == 2023
        assert _extract_year("A study from 1999") == 1999

    def test_extracts_from_url(self):
        assert _extract_year("", "https://example.com/2024/article") == 2024

    def test_returns_none_for_no_year(self):
        assert _extract_year("no year here") is None

    def test_ignores_invalid_years(self):
        assert _extract_year("Year 3000") is None


class TestExtractDomain:
    def test_extracts_domain(self):
        assert _extract_domain("https://www.example.com/page") == "example.com"
        assert _extract_domain("https://sub.domain.org/path") == "sub.domain.org"

    def test_handles_invalid_url(self):
        assert _extract_domain("not-a-url") == "unknown" or _extract_domain("not-a-url") == ""


class TestCategorize:
    def test_research(self):
        assert _categorize("New Research Paper", "A study on AI") == "Research & Academic"

    def test_technology(self):
        assert _categorize("Python Framework", "A new software tool") == "Technology"

    def test_news(self):
        assert _categorize("Breaking News", "Report shows...") == "News & Media"

    def test_default_general(self):
        assert _categorize("Random title", "Some random snippet") == "General"


class TestResultToNode:
    def test_creates_node(self):
        result = {
            "title": "Test Article",
            "url": "https://example.com/article",
            "snippet": "This is a test snippet about research",
        }
        node = _result_to_node(result, "test query", 1)
        assert node["id"] == "node-1"
        assert node["title"] == "Test Article"
        assert node["url"] == "https://example.com/article"
        assert node["domain"] == "example.com"
        assert node["query"] == "test query"
        assert node["category"] in [
            "Research & Academic", "General", "News & Media",
            "Technology", "Business & Industry", "Tutorial & Guide",
            "Statistics & Data", "Opinion & Analysis", "Official & Government",
        ]

    def test_with_fetched_content(self):
        result = {"title": "T", "url": "https://x.com/p", "snippet": "s"}
        node = _result_to_node(result, "q", 1, "Long fetched content paragraph here.")
        assert node["fetched"] is True
        assert len(node["content_preview"]) > 0


class TestGroupNodes:
    def test_groups_by_source_year_category(self):
        nodes = [
            {"id": "n1", "domain": "example.com", "year": 2023, "category": "Technology"},
            {"id": "n2", "domain": "example.com", "year": 2024, "category": "Technology"},
            {"id": "n3", "domain": "other.org", "year": 2023, "category": "Research & Academic"},
        ]
        groups = _group_nodes(nodes)
        assert "by_source" in groups
        assert "by_year" in groups
        assert "by_category" in groups
        assert groups["by_source"]["example.com"]["count"] == 2
        assert groups["by_source"]["other.org"]["count"] == 1
        assert groups["by_year"]["2023"]["count"] == 2
        assert groups["by_category"]["Technology"]["count"] == 2


class TestGenerateSummary:
    def test_generates_summary(self):
        nodes = [
            {"id": "n1", "domain": "example.com", "year": 2023, "category": "Technology"},
        ]
        groups = _group_nodes(nodes)
        summary = _generate_topic_summary("AI", nodes, groups)
        assert "1 informasi" in summary
        assert "1 sumber" in summary
