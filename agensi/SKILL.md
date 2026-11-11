---
name: agentguard
description: Security check for the skills (SKILL.md) and MCP servers an AI agent uses. Detects tool poisoning and hidden instructions, flags rug pulls (a skill or tool that changed after you approved it), looks up known CVEs for installed MCP servers (OSV.dev), detects the "lethal trifecta" (private data + untrusted content + outbound channel), and writes a Markdown audit report. Use this skill whenever the user installs, downloads, reviews or updates a skill, plugin or MCP server, asks "is this skill safe", "audit my MCP config", "check my agent setup", "scan for prompt injection", or before trusting third-party agent tools, even if they don't say "security".
---

# agentguard

Local security layer for AI agents. Runs on the user's machine; only `cve` (and `audit` without `--offline`) calls the network, to query OSV.dev. The optional `--deep` check (section 5) is the only feature that sends file content off the machine, and only when the user asks for it.

Source: https://github.com/OnlyEdgeAdmin59/agentguard · PyPI: `agentguard-scan`

## 1. Install (once)

```bash
pip install "agentguard-scan>=0.5.0"
agentguard --version
```

Always add `--lang en` (or set `AGENTGUARD_LANG=en`) so output is in English. Without it, output is in Spanish.

If `agentguard` is not on PATH, use `python -m agentguard`.

## 2. Pick the command for the request

| User wants | Command |
|---|---|
| Check a skill/plugin folder before trusting it | `agentguard scan <folder> --lang en` |
| Approve the current state of a folder | `agentguard lock <folder> --lang en` |
| Check whether anything changed since approval | `agentguard verify <folder> --lang en` |
| Known vulnerabilities in installed MCP servers | `agentguard cve --lang en` |
| Data-exfiltration risk across MCP tools | `agentguard trifecta [folder] [--tools dir] --lang en` |
| One full report | `agentguard audit --skills <folder> --out agentguard-report.md --lang en` |

Notes:
- `scan` skips `node_modules`, `CHANGELOG`, `LICENSE` by default; add `--all` to include them.
- `cve` and `trifecta` without arguments read the MCP configs already installed on the machine.
- `audit` accepts `--config <file>` for a specific MCP config, `--project <folder>`, and `--offline` to skip network lookups.
- Exit code is 1 when there are HIGH/critical findings or changes, so it works in CI.
- If the user writes in Spanish, drop `--lang en`.

## 3. Default workflow

When the user asks to "check" or "audit" their setup without more detail:

1. `agentguard audit --skills <skills folder> --out agentguard-report.md --lang en`
2. Read the report. Summarize for the user: number of findings by severity, then each HIGH/critical finding with the file, what it does, and the concrete fix (remove the skill, pin/upgrade the MCP server, cut one leg of the trifecta).
3. If everything is clean, run `agentguard lock <folder> --lang en` so future changes can be caught with `verify`.

## 4. Rules

- Never auto-delete or auto-edit a flagged skill or config. Report it and let the user decide.
- Do not run or install the skill being scanned to "test" it.
- A clean scan is not a guarantee. Say so when the user is about to trust a high-privilege tool.
- For CI, point the user to the GitHub Action in the repo instead of re-running this by hand.

## 5. Optional semantic check (`--deep`, experimental)

**Experimental.** On long real-world skills it raises many false alarms (2.6% HIGH, 39% with some notice). Review every finding by hand.

Fixed rules miss attacks written as normal steps ("back up the files and upload them to…"). `--deep` adds an AI judge on top of the rules. It only adds findings; it never removes the rules' findings.

- **Requirement:** `pip install "agentguard-scan[deep]"` and an `ANTHROPIC_API_KEY` in the environment. Alternative with nothing leaving the machine: a local Ollama model (`--deep-provider ollama --deep-model <model>`).
- **What is sent:** with Anthropic (default model `claude-haiku-5-5`), the full text of each scanned skill or tool goes to `api.anthropic.com`. Strings that look like real keys are masked first. Never turn it on without the user's explicit consent for that run.
- **Cost:** about $0.002 per skill with Haiku (1,170 real skills cost about $2.50).
- **First run:** always start with `--deep-dry-run`; it lists files, size, destination and estimated cost, and sends nothing. Show that to the user before the real run.

```bash
agentguard scan <folder> --deep --deep-dry-run --lang en
agentguard scan <folder> --deep --lang en            # asks for confirmation
agentguard audit --skills <folder> --deep --out agentguard-report.md --lang en
```

- **CI:** `--deep` findings do not fail the build by default; only with `--deep-fail-on high`. Without an interactive terminal it needs `--deep-yes`.
- **How to read it:** on a blind test set it rated 31 of 34 attacks HIGH (rules alone: 2). On long real-world skills it is noisy (2.6% HIGH false alarms, 39% with some notice). Present `--deep` findings as "worth a look", quote the judge's reason, and let the user decide. Results can vary between runs.
