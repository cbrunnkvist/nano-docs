# External Link Audit — June 2026

Automated verification of all 603 external links across 153 documentation files. 487 unique URLs checked via HTTP, 4 false positives excluded (localhost/placeholder URLs in code examples).

## Summary

| Status | Count | % |
|--------|-------|---|
| OK | 575 | 95.4% |
| Dead | 23 | 3.8% |
| Redirected (domain-napped) | 2 | 0.3% |
| Uncertain | 2 | 0.3% |

**25 link annotations applied** across 16 files. 24 medium.com links return 403 to automated clients (anti-bot protection) but load fine in browsers — no changes made.

## Changes by root cause

| Root cause | Count | Status | Action taken |
|------------|-------|--------|--------------|
| forum.nano.org NXDOMAIN | 19 | Dead | Link removed, annotated "link dead as of June 2026" |
| Domain napped (nanolinks.info, nanocenter.org) | 2 | Redirected | Link removed, annotated "link dead as of June 2026" |
| 404 / gone (acodersjourney, IOTA PDF) | 2 | Dead | Link removed, annotated |
| wiki.sei.cmu.edu timeout | 1 | Dead | Link removed, annotated |
| nanocrawler.cc SSL error | 1 | Dead | Link removed, annotated |
| GitHub rate limit (429) | 1 | Uncertain | Annotated "verify - uncertain" (image URL skipped) |

## Verified as OK (initially flagged, confirmed working)

- **repo.nano.org binaries** (9 URLs): Initial verification timed out downloading full file bodies. HEAD requests confirm all return HTTP 200 — these are large binaries (`.tar.bz2`, `.deb`, `.exe`, `.zip`, `.dmg`), not broken links.
- **s3.us-east-2.amazonaws.com/beta-snapshot.nano.org** (1 URL): 57GB snapshot file. HEAD returns 200. Link is inside a code block and was correctly skipped by the patcher.
- **medium.com / blog.nano.org** (24 URLs): Return 403 to curl (anti-bot protection) but articles load normally in browsers.

## Detailed findings by source category

### Releases (9 issues, 147 OK)

| Status | File | Line | URL | Reason |
|--------|------|------|-----|--------|
| Dead | releases/network-upgrades.md | 166 | `forum.nano.org/t/automated-network-upgrades/113` | NXDOMAIN |
| Dead | releases/release-v19-0.md | 135 | `nanocrawler.cc` | SSL error |
| Dead | releases/release-v20-0.md | 42 | `forum.nano.org/c/node-and-rep` | NXDOMAIN |
| Dead | releases/release-v20-0.md | 68 | `forum.nano.org/t/rocksdb-ledger-backend-testing/111/4` | NXDOMAIN |
| Dead | releases/release-v20-0.md | 106 | `forum.nano.org/c/node-and-rep` | NXDOMAIN |
| Dead | releases/release-v21-0.md | 60 | `forum.nano.org/t/node-telemetry-metrics/112/8` | NXDOMAIN |
| Dead | releases/release-v21-0.md | 75 | `forum.nano.org/c/node-and-rep` | NXDOMAIN |
| Dead | releases/release-v22-0.md | 34 | `forum.nano.org/t/election-scheduler-and-prioritization-revamp/1837` | NXDOMAIN |
| Dead | releases/release-v22-0.md | 65 | `forum.nano.org/t/election-scheduler-and-prioritization-revamp/1837` | NXDOMAIN |

### Protocol Design (3 issues, 73 OK)

| Status | File | Line | URL | Reason |
|--------|------|------|-----|--------|
| Dead | protocol-design/introduction.md | 49 | `forum.nano.org/t/nano-stress-tests-measuring-bps-cps-tps-in-the-real-world/436` | NXDOMAIN |
| Dead | protocol-design/introduction.md | 58 | `assets.ctfassets.net/.../iota1_4_3.pdf` | 404 |
| Dead | protocol-design/ledger.md | 84 | `forum.nano.org/t/ledger-pruning/114` | NXDOMAIN |

### Running a Node (6 issues, 58 OK)

| Status | File | Line | URL | Reason |
|--------|------|------|-----|--------|
| Dead | running-a-node/ledger-management.md | 81 | `forum.nano.org/c/node-and-rep/8` | NXDOMAIN |
| Dead | running-a-node/ledger-management.md | 81 | `forum.nano.org` | NXDOMAIN |
| Dead | running-a-node/ledger-management.md | 125 | `forum.nano.org/t/rocksdb-ledger-backend-testing/111` | NXDOMAIN |
| Dead | running-a-node/node-setup.md | 404 | `forum.nano.org` | NXDOMAIN |
| Dead | running-a-node/voting-as-a-representative.md | 95 | `forum.nano.org/c/node-and-rep/8` | NXDOMAIN |
| Redirected | running-a-node/beyond-the-node.md | 12 | `nanocenter.org/` | -> cantrip.io (domain napped) |

### Core Development (6 issues, 132 OK)

| Status | File | Line | URL | Reason |
|--------|------|------|-----|--------|
| Dead | core-development/code-standards.md | 39 | `wiki.sei.cmu.edu/confluence/display/cplusplus` | Timeout |
| Dead | core-development/code-standards.md | 46 | `www.acodersjourney.com/2016/02/c-11-auto/` | 404 |
| Dead | core-development/collaboration-process.md | 58 | `forum.nano.org` | NXDOMAIN |
| Dead | core-development/collaboration-process.md | 79 | `forum.nano.org` | NXDOMAIN |
| Dead | core-development/collaboration-process.md | 83 | `forum.nano.org` | NXDOMAIN |
| Uncertain | core-development/overview.md | 32 | `github.com/search?q=nanocurrency&type=discussions` | Rate limited (429) |

### Integration Guides (2 issues, 52 OK)

| Status | File | Line | URL | Reason |
|--------|------|------|-----|--------|
| Redirected | integration-guides/index.md | 101 | `nanolinks.info/` | -> acciaroli.info (domain napped) |
| Uncertain | integration-guides/index.md | 89 | `opengraph.githubassets.com/.../pippin_nano_wallet` | Rate limited (429), image URL — not annotated |

### Snippets (1 issue, 97 OK)

| Status | File | Line | URL | Reason |
|--------|------|------|-----|--------|
| Dead | snippets/community-links.md | 2 | `forum.nano.org` | NXDOMAIN |

### No issues found

- What is Nano (2 links)
- Living Whitepaper (3 links)
- Snippets: current-build-links-main.md (5 links), current-build-links-test.md (5 links) — all repo.nano.org binaries confirmed OK via HEAD
- Other pages: glossary, index, whitepaper, articles, commands, javascript, node-implementation, diagrams (12 links)

## Files modified (16)

| File | Changes |
|------|---------|
| docs/core-development/code-standards.md | 2 |
| docs/core-development/collaboration-process.md | 3 |
| docs/core-development/overview.md | 1 |
| docs/integration-guides/index.md | 1 |
| docs/protocol-design/introduction.md | 2 |
| docs/protocol-design/ledger.md | 1 |
| docs/releases/network-upgrades.md | 1 |
| docs/releases/release-v19-0.md | 1 |
| docs/releases/release-v20-0.md | 3 |
| docs/releases/release-v21-0.md | 2 |
| docs/releases/release-v22-0.md | 2 |
| docs/running-a-node/beyond-the-node.md | 1 |
| docs/running-a-node/ledger-management.md | 3 |
| docs/running-a-node/node-setup.md | 1 |
| docs/running-a-node/voting-as-a-representative.md | 1 |
| docs/snippets/community-links.md | 1 |

## Patch format

Dead and domain-napped links:
```markdown
# Before
[Link Text](https://dead-site.com/page)

# After
Link Text (n.b. link dead as of June 2026)
```

Uncertain links (rate limited):
```markdown
# Before
[GitHub](https://github.com/search?q=nanocurrency&type=discussions)

# After
[GitHub](https://github.com/search?q=nanocurrency&type=discussions) (n.b. verify link - status uncertain as of June 2026)
```

## Verification scripts

The following scripts were created for this audit and can be re-run for future checks:

```
scripts/extract_links.py    # Extract all external links from docs/
scripts/verify_links.py     # Verify URLs via HTTP (resumable)
scripts/analyze_content.py  # Classify results, generate report
scripts/patch_links.py      # Apply patches (--dry-run or --apply)
```
