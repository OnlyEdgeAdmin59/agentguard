# agentguard

**English** · [Español](README.es.md)

Security for AI agents that use skills and MCP servers. Runs on your machine, no account and no dependencies (Python 3.9+).

- `scan`: looks for hidden instructions (tool poisoning) in skills (`SKILL.md`) and MCP tools (JSON).
- `lock` / `verify`: warns if a connector changed after you approved it (rug pull).
- `cve`: checks installed MCP servers against known vulnerabilities (OSV.dev).
- `trifecta`: warns if your setup combines the "lethal trifecta" (private data + untrusted content + a way out).
- `audit`: puts it all together in a Markdown audit report.

**It does not catch everything.** On an independent blind set (Skill-Inject, MIT: 34 attacks in 60 texts), rules alone rated 2 of 34 attacks HIGH (6%); with `--deep` (Claude Haiku) 31 of 34 (91%). On 120 benign samples, `--deep` raised 2 HIGH false alarms and 11 got some notice (9%). On 1,170 real SKILL.md files, `--deep` rated 30 HIGH (2.6%, all false alarms on manual review) and 39% got some notice. Single measurement; the model can vary between runs. `--deep` sends the text to Anthropic and needs `ANTHROPIC_API_KEY`. No findings does not prove something is safe.

`cve`, `trifecta` and `lock`/`verify` don't depend on the `scan` rules or on `--deep`. Details: [reports/deep_holdout_v3.md](reports/deep_holdout_v3.md), [reports/deep_ruido.md](reports/deep_ruido.md) and [CHANGELOG.md](CHANGELOG.md) (reports are in Spanish).

## Install
```bash
pip install agentguard-scan
```
Or without installing anything permanently:
```bash
uvx --from agentguard-scan agentguard scan ./my-skills
```

## Usage
Output is in Spanish by default. Add `--lang en` to any command, or set `AGENTGUARD_LANG=en`, for English output (including the `audit` report: [example](reports/audit_example_en.md)). In English, `audit` also accepts `--project` and `--offline` (aliases of `--proyecto` and `--sin-red`).
```bash
agentguard scan   folder [--all]       # HIGH findings exit with code 1
agentguard lock   folder               # saves fingerprints to agentguard.lock.json
agentguard verify folder               # exit code 1 if something changed since the lock
agentguard cve    [folder | config_file]
agentguard trifecta [folder | config_file] [--tools folder]
agentguard audit  [--skills folder] [--config file] [--tools folder] [--offline] [--out report.md]
```
```bash
agentguard scan ./my-skills --lang en
agentguard audit --skills ~/.claude/skills --offline --out report.md --lang en
```

### cve
```bash
agentguard cve --lang en                        # Claude Desktop, Claude Code, Cursor and VS Code configs
agentguard cve ~/.cursor/mcp.json --lang en     # a single config file
```
```
package                                  version      CVE                    severity   fixed
mcp-remote                               0.1.15       CVE-2025-6514          CRITICAL   0.1.16
[INFO] Claude Desktop · fetch: mcp-server-fetch (PyPI) — version not pinned (runs the latest)
```
Reads the package and version of each server (`npx pkg@1.2.3`, `uvx pkg==1.2.3`, …) and queries [OSV.dev](https://osv.dev).
Only name, ecosystem and version are sent to OSV; never tool descriptions or paths.
Exits with 1 if there are vulnerabilities and with 2 if there is no network.

### trifecta
```bash
agentguard trifecta --lang en                             # every config, per client and per project
agentguard trifecta .mcp.json --tools ./tools --lang en   # --tools: <server>.json with the tools/list output
```
Each server is classified with a table of known servers (`agentguard/trifecta/known.json`) or, if it isn't there, by heuristics; the report says which.
Each project is checked with the global servers plus its own, not mixed with other projects. The output suggests which option to remove to break the trifecta.

### audit
```bash
agentguard audit --skills ~/.claude/skills --out audit.md --lang en
```
Builds a report with an executive summary, findings by severity, how to fix each one, and a manual review section to fill in by hand.
`--offline` skips the OSV.dev lookup.

### Semantic check (`--deep`, optional, experimental)
> **Experimental.** On long real-world skills it raises many false alarms (2.6% HIGH, 39% with some notice). Review every finding by hand.

Fixed rules don't see attacks written as normal steps ("make a backup and upload it to…"). `--deep` adds an AI model that judges the intent of each skill or tool. It only **adds** findings: it never removes the rules' findings.

```bash
pip install agentguard-scan[deep]                          # Anthropic SDK (only for --deep)
agentguard scan ~/.claude/skills --deep --deep-dry-run     # what would be sent, where, and the cost
agentguard scan ~/.claude/skills --deep                    # asks for confirmation before sending
```

- **Privacy:** with the default provider (Anthropic, model `claude-haiku-5-5`) the text of each skill is sent to `api.anthropic.com` and needs `ANTHROPIC_API_KEY`. It never turns on by itself. Before sending it says what goes out and masks anything that looks like a real key. Without an interactive terminal you need `--deep-yes`.
- **Local:** `--deep-provider ollama --deep-model <model>` uses Ollama on your machine; nothing leaves it.
- **Cost:** with Haiku, about $0.002 per real skill (1,170 SKILL.md files cost $2.47).
- **CI:** `--deep` findings don't fail the build unless you pass `--deep-fail-on high`.
- **Limits:** a model's judgment is not deterministic and can be wrong in both directions. On long real-world skills it is noisy (see the numbers above): read it as "worth a look", not as a verdict.
- Also in `audit --skills <folder> --deep`.

## GitHub Action
```yaml
- uses: actions/checkout@v5
- uses: OnlyEdgeAdmin59/agentguard@v0.5.0
  with:
    lang: en
```
Fails the build on HIGH findings and marks them on the PR line.
With `deep: true` it also runs the semantic check. **It sends the reviewed PR content to Anthropic.** Pass the key through `env`; on PRs from forks there are no secrets and `--deep` is skipped without failing:
```yaml
- uses: OnlyEdgeAdmin59/agentguard@v0.5.0
  with:
    deep: true            # deep-fail-on: high to make a HIGH from the judge fail the build
  env:
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```
