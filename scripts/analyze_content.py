#!/usr/bin/env python3
"""
Content Analysis and Report Generation

Combines link extraction data with verification results, filters false positives,
performs content matching analysis, and generates the final audit report.

Usage:
    python scripts/analyze_content.py
"""

import json
import os
import re
from collections import Counter, defaultdict
from datetime import date
from urllib.parse import urlparse

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
link_report_path = os.path.join(repo_root, "scripts", "link_report.json")
verification_path = os.path.join(repo_root, "scripts", "verification_results.json")
report_md_path = os.path.join(repo_root, "scripts", "link_audit_report.md")
report_json_path = os.path.join(repo_root, "scripts", "link_audit_report.json")

FALSE_POSITIVE_PATTERNS = [
    r"^https?://127\.0\.0\.",
    r"^https?://localhost",
    r"^https?://your-",
    r"^https?://callback_",
    r"^https?://example\.(com|org|net)",
    r"://[^/]*:<",  # URLs with angle brackets inside (code examples)
    r"://[^/]*`$",  # URLs ending with backtick (inline code)
]

# Domains where curl 403 is anti-bot protection, not actual gating
ANTI_BOT_DOMAINS = {"medium.com", "blog.nano.org"}

# Domains where connection timeouts are likely transient (large files, slow server)
SLOW_SERVER_DOMAINS = {"repo.nano.org", "s3.us-east-2.amazonaws.com"}


def is_false_positive(url: str, context: str) -> bool:
    """Check if a URL is likely a false positive from code examples."""
    for pattern in FALSE_POSITIVE_PATTERNS:
        if re.search(pattern, url):
            return True
    # Check if context suggests inline code
    if context.startswith("`") and context.endswith("`"):
        return True
    return False


def classify_redirect_severity(original_url: str, final_url: str) -> str:
    """Classify redirect as benign or concerning."""
    orig_host = urlparse(original_url).hostname or ""
    final_host = urlparse(final_url).hostname or ""

    # Same domain redirect (e.g., http -> https, www -> non-www)
    orig_base = orig_host.replace("www.", "")
    final_base = final_host.replace("www.", "")
    if orig_base == final_base:
        return "benign"

    # Known safe redirects
    safe_redirects = {
        "twitter.com": "x.com",
        "www.twitter.com": "x.com",
        "facebook.com": "www.facebook.com",
        "reddit.com": "www.reddit.com",
        "youtube.com": "www.youtube.com",
        "desktop.github.com": "github.com",
        "help.github.com": "docs.github.com",
        "blockchain.info": "www.blockchain.com",
        "password-hashing.net": "www.password-hashing.net",
        "peercoin.net": "www.peercoin.net",
        "blake2.net": "www.blake2.net",
        "bitslog.files.wordpress.com": "bitslog.com",
        "nano.org": "hub.nano.org",
    }
    if safe_redirects.get(orig_host) == final_host:
        return "benign"

    # Same-domain subdomain redirects (e.g., release-assets.githubusercontent.com)
    orig_reg = ".".join(orig_host.split(".")[-2:]) if orig_host.count(".") >= 2 else orig_host
    final_reg = ".".join(final_host.split(".")[-2:]) if final_host.count(".") >= 2 else final_host
    if orig_reg == final_reg and orig_reg not in ("co.uk", "com.au", "org.io"):
        return "benign"

    # GitHub release asset CDN
    if orig_host == "github.com" and final_host.endswith("githubusercontent.com"):
        return "benign"

    # DOI resolver redirects
    if orig_host == "doi.org":
        return "benign"

    # URL shortener for known services
    if orig_host in ("eepurl.com", "aka.ms"):
        return "benign"

    return "domain_change"


def generate_report():
    """Generate the final audit report."""
    with open(link_report_path, "r") as f:
        extraction = json.load(f)

    with open(verification_path, "r") as f:
        verification = json.load(f)

    verified = verification["results"]

    # Build enriched link records
    enriched_links = []
    false_positives = []

    for link in extraction["links"]:
        url = link["url"]

        # Check for false positives
        if is_false_positive(url, link.get("context", "")):
            false_positives.append(link)
            continue

        verification_data = verified.get(url, {})
        status = verification_data.get("status", "UNCERTAIN")

        # Catch domain changes missed by verify_links (curl -L follows redirects silently)
        if verification_data.get("domain_changed") and status == "OK":
            severity = classify_redirect_severity(url, verification_data.get("final_url", url))
            if severity != "benign":
                status = "REDIRECT"
                verification_data["status"] = "REDIRECT"
                verification_data["reason"] = f"Redirected from {verification_data.get('original_host', '')} to {verification_data.get('final_host', '')}"

        # Refine redirects
        if status == "REDIRECT":
            severity = classify_redirect_severity(url, verification_data.get("final_url", url))
            if severity == "benign":
                status = "OK"
                verification_data["status"] = "OK"
                verification_data["reason"] = "Benign redirect (same domain or known safe)"

        # Reclassify Medium/blog 403 as OK (anti-bot protection, not actual gating)
        if status == "GATED":
            host = urlparse(url).hostname or ""
            if host in ANTI_BOT_DOMAINS:
                status = "OK"
                verification_data["status"] = "OK"
                verification_data["reason"] = "Anti-bot protection (403 to curl, works in browser)"

        # Reclassify slow-server timeouts as UNCERTAIN (not DEAD)
        if status == "DEAD" and verification_data.get("http_code") == 0:
            host = urlparse(url).hostname or ""
            if host in SLOW_SERVER_DOMAINS:
                status = "UNCERTAIN"
                verification_data["status"] = "UNCERTAIN"
                verification_data["reason"] = "Connection timeout — likely slow server, not dead"

        enriched = {
            **link,
            "verification": verification_data,
            "status": status,
        }
        enriched_links.append(enriched)

    # Aggregate statistics
    status_counts = Counter(link["status"] for link in enriched_links)
    domain_status = defaultdict(lambda: Counter())
    for link in enriched_links:
        host = urlparse(link["url"]).hostname or "unknown"
        domain_status[host][link["status"]] += 1

    # Group by status for report
    by_status = defaultdict(list)
    for link in enriched_links:
        by_status[link["status"]].append(link)

    # Generate Markdown report
    total = len(enriched_links)
    report_date = date.today().strftime("%B %Y")

    lines = []
    lines.append("# External Link Audit Report")
    lines.append(f"**Date**: {report_date}")
    lines.append(f"**Total Links Checked**: {total}")
    lines.append(f"**Unique URLs**: {extraction['unique_urls']}")
    lines.append(f"**False Positives Excluded**: {len(false_positives)}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Status | Count | Percentage |")
    lines.append("|--------|-------|------------|")
    status_order = ["OK", "REDIRECT", "DEAD", "SPAM", "GATED", "UNCERTAIN"]
    status_labels = {
        "OK": "OK",
        "REDIRECT": "Redirected",
        "DEAD": "Dead",
        "SPAM": "Spam/Parked",
        "GATED": "Gated/Paywall",
        "UNCERTAIN": "Uncertain",
    }
    for s in status_order:
        count = status_counts.get(s, 0)
        if count > 0:
            pct = count / total * 100
            lines.append(f"| {status_labels[s]} | {count} | {pct:.1f}% |")

    # Dead links section
    if by_status.get("DEAD"):
        lines.append("")
        lines.append("## Dead Links")
        lines.append("")
        lines.append("| File | Line | URL | Reason |")
        lines.append("|------|------|-----|--------|")
        for link in sorted(by_status["DEAD"], key=lambda x: (x["file"], x["line"])):
            reason = link["verification"].get("reason", "Unknown")
            lines.append(f"| {link['file']} | {link['line']} | {link['url']} | {reason} |")

    # Spam links section
    if by_status.get("SPAM"):
        lines.append("")
        lines.append("## Spam / Domain-Napped Links")
        lines.append("")
        lines.append("| File | Line | URL | Detected Content |")
        lines.append("|------|------|-----|------------------|")
        for link in sorted(by_status["SPAM"], key=lambda x: (x["file"], x["line"])):
            reason = link["verification"].get("reason", "Unknown")
            lines.append(f"| {link['file']} | {link['line']} | {link['url']} | {reason} |")

    # Redirects section
    if by_status.get("REDIRECT"):
        lines.append("")
        lines.append("## Redirects (Domain Change)")
        lines.append("")
        lines.append("| File | Line | Original URL | Final URL |")
        lines.append("|------|------|--------------|-----------|")
        for link in sorted(by_status["REDIRECT"], key=lambda x: (x["file"], x["line"])):
            final = link["verification"].get("final_url", "Unknown")
            lines.append(f"| {link['file']} | {link['line']} | {link['url']} | {final} |")

    # Gated links section
    if by_status.get("GATED"):
        lines.append("")
        lines.append("## Gated / Paywalled Links")
        lines.append("")
        lines.append("| File | Line | URL | Reason |")
        lines.append("|------|------|-----|--------|")
        for link in sorted(by_status["GATED"], key=lambda x: (x["file"], x["line"])):
            reason = link["verification"].get("reason", "Unknown")
            lines.append(f"| {link['file']} | {link['line']} | {link['url']} | {reason} |")

    # Uncertain links section
    if by_status.get("UNCERTAIN"):
        lines.append("")
        lines.append("## Uncertain Links (Manual Review Needed)")
        lines.append("")
        lines.append("| File | Line | URL | Reason |")
        lines.append("|------|------|-----|--------|")
        for link in sorted(by_status["UNCERTAIN"], key=lambda x: (x["file"], x["line"])):
            reason = link["verification"].get("reason", "Unknown")
            lines.append(f"| {link['file']} | {link['line']} | {link['url']} | {reason} |")

    # Domain summary
    lines.append("")
    lines.append("## Domain Summary")
    lines.append("")
    lines.append("| Domain | Total | OK | Dead | Gated | Redirect | Spam | Uncertain |")
    lines.append("|--------|-------|----|------|-------|----------|------|-----------|")
    for domain in sorted(domain_status.keys()):
        counts = domain_status[domain]
        total_d = sum(counts.values())
        if total_d < 2:
            continue
        lines.append(
            f"| {domain} | {total_d} | "
            f"{counts.get('OK', 0)} | {counts.get('DEAD', 0)} | "
            f"{counts.get('GATED', 0)} | {counts.get('REDIRECT', 0)} | "
            f"{counts.get('SPAM', 0)} | {counts.get('UNCERTAIN', 0)} |"
        )

    # Write reports
    with open(report_md_path, "w") as f:
        f.write("\n".join(lines) + "\n")

    json_report = {
        "report_date": date.today().isoformat(),
        "total_links": total,
        "unique_urls": extraction["unique_urls"],
        "false_positives_excluded": len(false_positives),
        "status_counts": dict(status_counts),
        "links_needing_action": [
            link for link in enriched_links if link["status"] not in ("OK",)
        ],
        "all_links": enriched_links,
    }
    with open(report_json_path, "w") as f:
        json.dump(json_report, f, indent=2, ensure_ascii=False)

    print(f"Audit report generated:")
    print(f"  Markdown: {os.path.relpath(report_md_path, repo_root)}")
    print(f"  JSON:     {os.path.relpath(report_json_path, repo_root)}")
    print(f"\nSummary:")
    print(f"  Total links: {total}")
    print(f"  False positives excluded: {len(false_positives)}")
    for s in status_order:
        count = status_counts.get(s, 0)
        if count > 0:
            print(f"  {status_labels[s]}: {count}")


if __name__ == "__main__":
    generate_report()
