# Manual setup of the Markov regime research tool

The original video onboarding prompt generated a second implementation. That
copy used different defaults and retained warm-up bars as Sideways. v2 uses the
maintained repository source for both manual and plugin workflows. The original
on-camera artifact remains available in Git history.

1. Download or clone this repository and inspect the maintained script, its
   inline dependencies, script lockfile, and tests.
2. Install uv from its official source if needed. No administrator access is
   required for the project environment.
3. From the repository directory, install the locked environment and run checks:

   ```bash
   uv sync --locked
   uv run --locked python -m pytest -q
   ```

4. Run the same maintained script the plugin uses:

   ```bash
   uv run --locked --script scripts/markov_regime.py --csv tests/fixtures/cli_prices.csv --json --no-hmm
   uv run --locked --script scripts/markov_regime.py --ticker SPY --json --no-hmm
   ```

The first command uses a deliberately sparse local fixture. Null probabilities
for its final, previously unobserved Bull state are expected. The second requires
Yahoo Finance access and can fail if the provider is unavailable.

Optional HMM fitting is a separate dependency choice:

```bash
uv run --with hmmlearn --script scripts/markov_regime.py --ticker SPY --json
```

An HMM installation failure does not affect the core command. To use the tool
through Claude Code, follow the local-marketplace instructions in [README](README.md).
Keep the script and its lockfile together when distributing the plugin.

See the [v2 contract](skills/regime/SKILL.md) and
[release verification](docs/RELEASE_CHECKLIST.md).
Historical analysis does not establish future performance.
