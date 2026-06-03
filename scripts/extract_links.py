#!/usr/bin/env python3
"""
External Link Extraction

Walks all .md files under docs/ and extracts external HTTP/HTTPS URLs from:
  - Standard markdown links: [text](url)
  - Footnote definitions: [^n]: ... url ...
  - Angle-bracket URLs: <url>
  - Bare URLs (pymdownx.magiclink auto-linking)

Outputs scripts/link_report.json with structured data.

Usage:
    python scripts/extract_links.py
"""

import json
import os
import re
from datetime import date
from urllib.parse import urlparse

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
docs_dir = os.path.join(repo_root, "docs")
output_path = os.path.join(repo_root, "scripts", "link_report.json")

# Regex patterns
INLINE_LINK_RE = re.compile(r'\[([^\]]*)\]\((https?://[^)]+)\)')
FOOTNOTE_URL_RE = re.compile(r'^\[\^[^\]]+\]:\s*.*?(https?://\S+)', re.MULTILINE)
ANGLE_BRACKET_RE = re.compile(r'<(https?://[^>]+)>')
BARE_URL_RE = re.compile(r'(?<!\()(https?://[^\s\)>\]]+)')

SKIP_HOSTS = {
    "127.0.0.1", "localhost", "www.example.com", "example.com",
    "example.org", "www.example.org", "example.net", "www.example.net",
}


def is_external(url: str) -> bool:
    """Check if URL points to an external site worth verifying."""
    parsed = urlparse(url)
    host = parsed.hostname or ""
    if host in SKIP_HOSTS:
        return False
    return parsed.scheme in ("http", "https")


def extract_links_from_file(filepath: str, rel_path: str) -> list[dict]:
    """Extract all external links from a single markdown file."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.splitlines()
    links = []
    seen_positions = set()  # (line, url) dedup within file

    def add_link(url: str, text: str, line_no: int, context: str):
        key = (line_no, url)
        if key in seen_positions:
            return
        seen_positions.add(key)
        links.append({
            "url": url.rstrip(".,;:!?)"),
            "text": text.strip(),
            "file": rel_path,
            "line": line_no,
            "context": context.strip()[:200],
        })

    for i, line in enumerate(lines, 1):
        # 1. Standard markdown links
        for m in INLINE_LINK_RE.finditer(line):
            url = m.group(2)
            if is_external(url):
                ctx_start = max(0, m.start() - 40)
                ctx_end = min(len(line), m.end() + 40)
                add_link(url, m.group(1), i, line[ctx_start:ctx_end])

        # 2. Angle-bracket URLs
        for m in ANGLE_BRACKET_RE.finditer(line):
            url = m.group(1)
            if is_external(url):
                ctx_start = max(0, m.start() - 40)
                ctx_end = min(len(line), m.end() + 40)
                add_link(url, "", i, line[ctx_start:ctx_end])

        # 3. Bare URLs (not already captured by inline link or angle bracket)
        captured_ranges = []
        for m in INLINE_LINK_RE.finditer(line):
            captured_ranges.append((m.start(2), m.end(2)))
        for m in ANGLE_BRACKET_RE.finditer(line):
            captured_ranges.append((m.start(1), m.end(1)))

        for m in BARE_URL_RE.finditer(line):
            # Skip if inside a captured range
            if any(s <= m.start(1) < e for s, e in captured_ranges):
                continue
            url = m.group(1)
            if is_external(url):
                ctx_start = max(0, m.start() - 40)
                ctx_end = min(len(line), m.end() + 40)
                add_link(url, "", i, line[ctx_start:ctx_end])

    # 4. Footnote definitions (can span multiple lines)
    for m in FOOTNOTE_URL_RE.finditer(content):
        url = m.group(1)
        if is_external(url):
            # Find line number
            char_pos = m.start(1)
            line_no = content[:char_pos].count("\n") + 1
            line_text = lines[line_no - 1] if line_no <= len(lines) else ""
            add_link(url, "", line_no, line_text.strip()[:200])

    return links


def main():
    all_links = []
    file_count = 0

    for root, dirs, files in os.walk(docs_dir):
        # Skip non-doc directories
        dirs[:] = [d for d in dirs if d not in ("site", ".git", "images", "stylesheets", "diagrams")]
        for fname in sorted(files):
            if not fname.endswith(".md"):
                continue
            filepath = os.path.join(root, fname)
            rel_path = os.path.relpath(filepath, repo_root)
            file_links = extract_links_from_file(filepath, rel_path)
            all_links.extend(file_links)
            file_count += 1

    # Deduplicate URLs for summary
    unique_urls = sorted(set(link["url"] for link in all_links))
    domains = sorted(set(urlparse(u).hostname or u for u in unique_urls))

    report = {
        "extraction_date": date.today().isoformat(),
        "total_links": len(all_links),
        "unique_urls": len(unique_urls),
        "unique_domains": len(domains),
        "files_scanned": file_count,
        "domains": domains,
        "links": all_links,
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"Extracted {len(all_links)} links ({len(unique_urls)} unique URLs across {len(domains)} domains) from {file_count} files")
    print(f"Report saved to {os.path.relpath(output_path, repo_root)}")


if __name__ == "__main__":
    main()
