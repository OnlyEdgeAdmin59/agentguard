# AI Agent Security Audit (AgentGuard)

Date: 2026-11-02

Scope: fixture example: skills `ejemplos`, config `tests/fixtures/cve/claude_desktop_config.json`, saved OSV data

## Executive summary

**Overall risk: High.**

- **scan**: 1 file(s) scanned, 6 finding(s), 2 HIGH.
- **cve**: 6 server(s), 4 with a pinned version checked on OSV.dev, 1 vulnerability(ies).
- **trifecta**: lethal trifecta in 1 of 1 scope(s) (global and each project).

| severity | findings |
|---|---|
| Critical | 1 |
| High | 3 |
| Medium | 3 |
| Low | 0 |
| Info | 2 |

## Findings by severity

### Critical (1)

**H-01 · CVE-2025-6514 in mcp-remote 0.1.15** — cve · npm
- Detail: GHSA-6xpm-ggf7-wc3p · severity CRITICAL · mcp-remote exposed to OS command injection via untrusted MCP server connections
- How to fix: Upgrade mcp-remote to 0.1.16.

### High (3)

**H-02 · Asks to hide something from the user** — scan · ejemplos/malicioso_tools.json:1
- Detail: «Do not tell the user»
- How to fix: Remove the instruction to hide things from the user. If it comes from a third party, treat it as malicious: uninstall and report it.

**H-03 · Secret + external send (possible theft)** — scan · ejemplos/malicioso_tools.json:1
- Detail: «.ssh → send it to https://»
- How to fix: Review it now: it asks to read credentials and send them out. Uninstall it, rotate the keys it mentions and report it to the author or the registry.

**H-04 · Lethal trifecta** — trifecta · file · global
- Detail: Reads private data: filesystem (table), git (table), docker (table); Brings in untrusted content: remote-ok (heuristic), fetch (table), win-wrapped (table), docker (table); Sends data out: fetch (table), win-wrapped (table), docker (table)
- How to fix: Remove one of these options: filesystem, git, docker | fetch, win-wrapped, docker. docker combines all three on its own: restrict its tools (read-only, allowed repos).

### Medium (3)

**H-05 · Mentions secrets** — scan · multiple
- Detail: 2 times in 1 file(s): ejemplos/malicioso_tools.json:1, ejemplos/malicioso_tools.json:1
- How to fix: Confirm it only explains where to put the key and doesn't ask the model to read it.

**H-06 · Sends data to an external URL** — scan · ejemplos/malicioso_tools.json:1
- Detail: «send it to https://»
- How to fix: Confirm the domain belongs to the author and the send is needed; otherwise remove it.

**H-07 · Urgency tags aimed at the model** — scan · ejemplos/malicioso_tools.json:1
- Detail: «<IMPORTANT>»
- How to fix: Remove <IMPORTANT>-style tags aimed at the model; an honest description doesn't need them.

### Info (2)

**H-08 · mcp-server-fetch (PyPI): version not pinned (runs the latest)** — cve · file · fetch
- How to fix: Pin the exact version (`pkg@1.2.3` / `pkg==1.2.3`) so it can't change without your approval.

**H-09 · docker: command 'docker' does not point to an npm/PyPI package** — cve · file · docker
- How to fix: Review it manually: it can't be checked against OSV.

## Manual review

> To be completed by the auditor. The automated checks do not replace this part.

- [ ] Findings confirmed and dismissed (by ID):
- [ ] Actual permissions of each server (tokens, folders, accounts):
- [ ] Origin and maintainer of each server (did the owner or repo change?):
- [ ] Tools reviewed manually (tools/list output):
- [ ] Third-party skills read in full:
- [ ] Conclusion:

Auditor: ________ · Date: ________

## Limitations

- On an independent blind set (Skill-Inject, MIT: 34 attacks in 60 texts), rules alone rated 2 of 34 attacks HIGH (6%); with `--deep` (Claude Haiku) 31 of 34 (91%). On 120 benign samples, `--deep` raised 2 HIGH false alarms and 11 got some notice (9%). On 1,170 real SKILL.md files, `--deep` rated 30 HIGH (2.6%, all false alarms on manual review) and 39% got some notice. Single measurement; the model can vary between runs. `--deep` sends the text to Anthropic and needs ANTHROPIC_API_KEY. No findings does not prove something is safe.
- `cve`, `trifecta` and `lock`/`verify` don't depend on the `scan` rules or on `--deep`.
- `trifecta` classifies with a table of known servers and, otherwise, with keyword heuristics; heuristic results must be confirmed manually.
- `cve` only finds vulnerabilities published on OSV.dev for packages with a pinned version.
- No server was executed.
