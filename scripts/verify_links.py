#!/usr/bin/env python3
"""
URL Verification

Reads link_report.json and verifies each unique URL via HTTP HEAD/GET requests.
Detects dead links, redirects, domain changes, and parked/spam domains.
Results are checkpointed to scripts/verification_progress.json for resumability.

Usage:
    python scripts/verify_links.py [--resume] [--timeout 15] [--concurrency 10]
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from urllib.parse import urlparse

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
link_report_path = os.path.join(repo_root, "scripts", "link_report.json")
progress_path = os.path.join(repo_root, "scripts", "verification_progress.json")
results_path = os.path.join(repo_root, "scripts", "verification_results.json")

SPAM_KEYWORDS = [
    "casino", "gambling", "poker", "slots", "betting", "sportsbook",
    "viagra", "cialis", "pharmacy", "payday loan",
    "domain for sale", "domain is for sale", "buy this domain",
    "parked domain", "domain parking", "coming soon",
    "adult content", "xxx", "porn",
]

PARKING_INDICATORS = [
    "domain for sale", "domain is for sale", "buy this domain",
    "this domain", "parked", "coming soon", "under construction",
    "godaddy", "namecheap", "sedo", "afternic",
]


def classify_url(url: str, http_code: int, final_url: str, body_snippet: str) -> dict:
    """Classify a URL based on HTTP response and content."""
    original_host = urlparse(url).hostname or ""
    final_host = urlparse(final_url).hostname or ""
    body_lower = body_snippet.lower() if body_snippet else ""

    result = {
        "status": "OK",
        "reason": "",
        "domain_changed": original_host != final_host,
        "original_host": original_host,
        "final_host": final_host,
    }

    # Dead links
    if http_code == 0:
        result["status"] = "DEAD"
        result["reason"] = "Connection failed (timeout or DNS error)"
        return result

    if http_code == 404:
        result["status"] = "DEAD"
        result["reason"] = "404 Not Found"
        return result

    if http_code >= 500:
        result["status"] = "DEAD"
        result["reason"] = f"Server error ({http_code})"
        return result

    # Gated content
    if http_code in (401, 403):
        result["status"] = "GATED"
        result["reason"] = f"Authentication required ({http_code})"
        return result

    # Rate limited
    if http_code == 429:
        result["status"] = "UNCERTAIN"
        result["reason"] = "Rate limited (429)"
        return result

    # Check for spam/parking in body
    if body_snippet:
        for keyword in PARKING_INDICATORS:
            if keyword in body_lower:
                result["status"] = "SPAM"
                result["reason"] = f"Parked domain (detected: '{keyword}')"
                return result

        spam_score = sum(1 for kw in SPAM_KEYWORDS if kw in body_lower)
        if spam_score >= 2:
            result["status"] = "SPAM"
            result["reason"] = f"Spam content detected ({spam_score} indicators)"
            return result

    # Redirect to different domain (curl -L follows redirects, so http_code is final 200)
    if result["domain_changed"]:
        result["status"] = "REDIRECT"
        result["reason"] = f"Redirected from {original_host} to {final_host}"
        return result

    # Successful but check for soft 404 / empty pages
    if http_code == 200 and body_snippet:
        if len(body_snippet.strip()) < 100:
            result["status"] = "UNCERTAIN"
            result["reason"] = "Page has very little content"
            return result

    return result


def verify_url_curl(url: str, timeout: int = 15) -> dict:
    """Verify a single URL using curl. Returns HTTP code, final URL, and body snippet."""
    try:
        # First try HEAD
        cmd = [
            "curl", "-sS", "-o", "/dev/null",
            "-w", "%{http_code}\t%{url_effective}",
            "-L", "--max-redirs", "5",
            "--max-time", str(timeout),
            "-A", "Mozilla/5.0 (compatible; LinkChecker/1.0)",
            url,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
        if result.returncode != 0:
            return {"http_code": 0, "final_url": url, "body": ""}

        parts = result.stdout.strip().split("\t", 1)
        http_code = int(parts[0]) if parts[0].isdigit() else 0
        final_url = parts[1] if len(parts) > 1 else url

        # For non-redirect success, fetch a snippet of body for content analysis
        body = ""
        if http_code == 200:
            body_cmd = [
                "curl", "-sS", "-L",
                "--max-time", str(timeout),
                "--max-bytes", "50000",
                "-A", "Mozilla/5.0 (compatible; LinkChecker/1.0)",
                url,
            ]
            body_result = subprocess.run(body_cmd, capture_output=True, text=True, timeout=timeout + 5)
            if body_result.returncode == 0:
                body = body_result.stdout[:5000]

        return {"http_code": http_code, "final_url": final_url, "body": body}

    except (subprocess.TimeoutExpired, Exception):
        return {"http_code": 0, "final_url": url, "body": ""}


def load_progress() -> dict:
    """Load checkpointed verification progress."""
    if os.path.exists(progress_path):
        with open(progress_path, "r") as f:
            return json.load(f)
    return {}


def save_progress(progress: dict):
    """Save verification progress checkpoint."""
    with open(progress_path, "w") as f:
        json.dump(progress, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Verify external links")
    parser.add_argument("--resume", action="store_true", help="Resume from last checkpoint")
    parser.add_argument("--timeout", type=int, default=15, help="Per-URL timeout in seconds")
    parser.add_argument("--concurrency", type=int, default=10, help="Number of parallel requests")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between batches in seconds")
    args = parser.parse_args()

    with open(link_report_path, "r") as f:
        report = json.load(f)

    unique_urls = sorted(set(link["url"] for link in report["links"]))
    print(f"Verifying {len(unique_urls)} unique URLs...")

    # Load existing progress if resuming
    progress = load_progress() if args.resume else {}
    pending_urls = [u for u in unique_urls if u not in progress]
    print(f"  {len(progress)} already verified, {len(pending_urls)} pending")

    verified = dict(progress)
    batch_size = args.concurrency

    for batch_start in range(0, len(pending_urls), batch_size):
        batch = pending_urls[batch_start:batch_start + batch_size]
        batch_num = batch_start // batch_size + 1
        total_batches = (len(pending_urls) + batch_size - 1) // batch_size
        print(f"  Batch {batch_num}/{total_batches} ({len(batch)} URLs)...", end="", flush=True)

        with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
            futures = {executor.submit(verify_url_curl, url, args.timeout): url for url in batch}
            for future in as_completed(futures):
                url = futures[future]
                try:
                    curl_result = future.result()
                except Exception as e:
                    curl_result = {"http_code": 0, "final_url": url, "body": ""}

                classification = classify_url(
                    url, curl_result["http_code"], curl_result["final_url"], curl_result["body"]
                )

                verified[url] = {
                    "url": url,
                    "http_code": curl_result["http_code"],
                    "final_url": curl_result["final_url"],
                    "status": classification["status"],
                    "reason": classification["reason"],
                    "domain_changed": classification["domain_changed"],
                    "original_host": classification["original_host"],
                    "final_host": classification["final_host"],
                    "body_snippet": curl_result["body"][:500] if curl_result["body"] else "",
                }

        print(" done")

        # Checkpoint after each batch
        save_progress(verified)

        if batch_start + batch_size < len(pending_urls):
            time.sleep(args.delay)

    # Build final results
    status_counts = {}
    for entry in verified.values():
        s = entry["status"]
        status_counts[s] = status_counts.get(s, 0) + 1

    results = {
        "verification_date": date.today().isoformat(),
        "total_urls_checked": len(verified),
        "status_counts": status_counts,
        "results": verified,
    }

    with open(results_path, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\nVerification complete. Results saved to scripts/verification_results.json")
    print("Status summary:")
    for status, count in sorted(status_counts.items()):
        print(f"  {status}: {count}")


if __name__ == "__main__":
    main()
