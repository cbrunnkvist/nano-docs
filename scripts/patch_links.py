#!/usr/bin/env python3
"""
Link Patching

Reads the audit report and patches .md files to annotate or remove dead/problematic links.
Supports dry-run mode, selective filtering, and generates a patch log.

Usage:
    python scripts/patch_links.py --dry-run          # Preview changes
    python scripts/patch_links.py --apply             # Apply changes
    python scripts/patch_links.py --status DEAD       # Only patch DEAD links
    python scripts/patch_links.py --status UNCERTAIN  # Only patch UNCERTAIN links
"""

import argparse
import json
import os
import re
import shutil
from datetime import date
from pathlib import Path

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
report_json_path = os.path.join(repo_root, "scripts", "link_audit_report.json")
patch_log_path = os.path.join(repo_root, "scripts", "patch_log.md")
backup_dir = os.path.join(repo_root, "scripts", "backups")

MONTH_YEAR = date.today().strftime("%B %Y")

# Regex patterns
INLINE_LINK_RE = re.compile(r'\[([^\]]*)\]\((https?://[^)]+)\)')
IMAGE_LINK_RE = re.compile(r'!\[([^\]]*)\]\((https?://[^)]+)\)')
CODE_BLOCK_RE = re.compile(r'^```')


def is_in_code_block(lines: list[str], line_idx: int) -> bool:
    """Check if a line is inside a fenced code block."""
    in_block = False
    for i in range(line_idx):
        if CODE_BLOCK_RE.match(lines[i].strip()):
            in_block = not in_block
    return in_block


def build_patch_map(audit_data: dict, statuses: set[str]) -> dict:
    """Build a map of (file, line) -> link data for links needing patches."""
    patch_map = {}
    for link in audit_data.get("links_needing_action", []):
        if link["status"] not in statuses:
            continue
        key = (link["file"], link["line"])
        if key not in patch_map:
            patch_map[key] = []
        patch_map[key].append(link)
    return patch_map


def patch_line(line: str, url: str, text: str, status: str) -> str | None:
    """Patch a single URL occurrence in a line. Returns new line or None if no change."""

    # Skip if URL is inside an image markdown ![...](url) — annotations break image syntax
    for m in IMAGE_LINK_RE.finditer(line):
        if m.group(2) == url:
            return None

    # 1. Try inline markdown link: [text](url)
    inline_pattern = re.compile(r'\[([^\]]*)\]\(' + re.escape(url) + r'\)')
    m = inline_pattern.search(line)
    if m:
        link_text = m.group(1)
        if status in ("DEAD", "REDIRECT"):
            replacement = f"{link_text} (n.b. link dead as of {MONTH_YEAR})"
        elif status == "UNCERTAIN":
            replacement = f"[{link_text}]({url}) (n.b. verify link - status uncertain as of {MONTH_YEAR})"
        else:
            return None
        return line[:m.start()] + replacement + line[m.end():]

    # 2. Try footnote definition: [^n]: ... url
    footnote_match = re.match(r'^(\[\^[^\]]+\]:\s*)', line)
    if footnote_match and url in line:
        prefix = footnote_match.group(1)
        # Find the URL in the line after the footnote prefix
        url_pos = line.find(url, len(prefix))
        if url_pos >= 0:
            url_end = url_pos + len(url)
        # Check it's not part of a longer URL (e.g. .sha256)
            if url_end < len(line) and line[url_end] not in (' ', '\t', '\n', ')', '>', '"', "'", '|', ';', ',', '.'):
                return None  # URL is part of a longer URL, skip
            if status in ("DEAD", "REDIRECT"):
                return line[:url_pos] + f"(link dead as of {MONTH_YEAR})" + line[url_end:]
            elif status == "UNCERTAIN":
                return line[:url_pos] + f"{url} (verify - uncertain as of {MONTH_YEAR})" + line[url_end:]
            return None

    # 3. Try bare URL (not inside markdown link or image)
    # First, find all inline links and images to exclude their URL ranges
    excluded_ranges = []
    for m in INLINE_LINK_RE.finditer(line):
        excluded_ranges.append((m.start(2), m.end(2)))
    for m in IMAGE_LINK_RE.finditer(line):
        excluded_ranges.append((m.start(2), m.end(2)))

    # Find the bare URL
    url_pos = line.find(url)
    if url_pos >= 0:
        # Check it's not inside an excluded range
        if any(s <= url_pos < e for s, e in excluded_ranges):
            return None

        url_end = url_pos + len(url)
        # Check it's not part of a longer URL
        if url_end < len(line) and line[url_end] not in (' ', '\t', '\n', ')', '>', '"', "'", '|', ';', ',', '.'):
            return None

        if status in ("DEAD", "REDIRECT"):
            # For bare URLs, wrap in parentheses with note
            return line[:url_pos] + f"(link dead as of {MONTH_YEAR}: {url})" + line[url_end:]
        elif status == "UNCERTAIN":
            return line[:url_pos] + f"{url} (verify - uncertain as of {MONTH_YEAR})" + line[url_end:]

    return None


def patch_file(filepath: str, links_for_line: list[dict], dry_run: bool) -> list[dict]:
    """Patch a single file for the given links. Returns list of changes made."""
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    changes = []

    # Group links by line, process each line once with all its links
    by_line: dict[int, list[dict]] = {}
    for link in links_for_line:
        idx = link["line"] - 1
        if idx not in by_line:
            by_line[idx] = []
        by_line[idx].append(link)

    for line_idx, line_links in sorted(by_line.items()):
        if line_idx >= len(lines):
            continue

        current_line = lines[line_idx]

        # Skip lines inside code blocks
        if is_in_code_block(lines, line_idx):
            continue

        # Process links on this line
        for link in line_links:
            url = link["url"]
            text = link.get("text", "")
            status = link["status"]

            new_line = patch_line(current_line, url, text, status)
            if new_line is not None and new_line != current_line:
                changes.append({
                    "file": link["file"],
                    "line": link["line"],
                    "url": url,
                    "status": status,
                    "before": current_line.rstrip("\n"),
                    "after": new_line.rstrip("\n"),
                })
                current_line = new_line

        lines[line_idx] = current_line

    if changes and not dry_run:
        with open(filepath, "w", encoding="utf-8") as f:
            f.writelines(lines)

    return changes


def main():
    parser = argparse.ArgumentParser(description="Patch dead/problematic links in docs")
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="Preview changes without applying (default)")
    parser.add_argument("--apply", action="store_true",
                        help="Apply changes to files")
    parser.add_argument("--status", nargs="+", default=["DEAD", "UNCERTAIN"],
                        help="Which statuses to patch (default: DEAD UNCERTAIN)")
    args = parser.parse_args()

    dry_run = not args.apply
    statuses = set(args.status)

    with open(report_json_path, "r") as f:
        audit_data = json.load(f)

    patch_map = build_patch_map(audit_data, statuses)

    if not patch_map:
        print(f"No links with status {statuses} to patch.")
        return

    print(f"{'DRY RUN' if dry_run else 'APPLYING'} patches for {len(patch_map)} link locations...")
    print(f"Statuses: {statuses}")
    print()

    # Group by file
    by_file: dict[str, list[dict]] = {}
    for (filepath, line), links in patch_map.items():
        if filepath not in by_file:
            by_file[filepath] = []
        by_file[filepath].extend(links)

    all_changes = []

    if not dry_run:
        os.makedirs(backup_dir, exist_ok=True)

    for filepath, links in sorted(by_file.items()):
        abs_path = os.path.join(repo_root, filepath)
        if not os.path.exists(abs_path):
            print(f"  SKIP (not found): {filepath}")
            continue

        if not dry_run:
            backup_path = os.path.join(backup_dir, os.path.basename(filepath) + ".bak")
            shutil.copy2(abs_path, backup_path)

        changes = patch_file(abs_path, links, dry_run)
        all_changes.extend(changes)

        if changes:
            print(f"  {filepath}: {len(changes)} change(s)")
            for c in changes:
                print(f"    L{c['line']}: [{c['status']}] {c['url']}")

    # Write patch log
    log_lines = []
    log_lines.append(f"# Patch Log — {MONTH_YEAR}")
    log_lines.append(f"**Mode**: {'Dry Run (no changes applied)' if dry_run else 'Applied'}")
    log_lines.append(f"**Statuses**: {', '.join(sorted(statuses))}")
    log_lines.append(f"**Total changes**: {len(all_changes)}")
    log_lines.append("")

    for change in all_changes:
        log_lines.append(f"## {change['file']}:{change['line']}")
        log_lines.append(f"**URL**: {change['url']}")
        log_lines.append(f"**Status**: {change['status']}")
        log_lines.append("")
        log_lines.append("```diff")
        log_lines.append(f"- {change['before']}")
        log_lines.append(f"+ {change['after']}")
        log_lines.append("```")
        log_lines.append("")

    with open(patch_log_path, "w") as f:
        f.write("\n".join(log_lines) + "\n")

    print(f"\nPatch log: scripts/patch_log.md")
    if dry_run:
        print("No changes applied (dry run). Use --apply to apply.")
    else:
        print(f"Backups saved to scripts/backups/")


if __name__ == "__main__":
    main()
