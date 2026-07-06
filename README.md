# Claude Agent Dashboard

A single-screen command center for managing multiple [Claude Code](https://claude.com/claude-code) agents. Discovers your agents, shows what each one has pending, tells you which ones are running right now, and launches any of them in its own terminal — all from the browser.

Built for a real multi-agent setup where a dozen `CLAUDE.md`-defined agents (infra, security, docs, personal projects…) each live in their own folder and it got hard to keep track of them.

## What it does

- **Auto-discovers agents** — every folder with a `CLAUDE.md` under the vault root is an agent. No registration, no config file listing them.
- **Parses each agent's `TODO.md`** — shows pending tasks grouped by urgency, so you see at a glance who's blocked.
- **Detects live sessions** — uses `psutil` to find running `claude` processes and matches them to agents by working directory. A green dot means that agent is active *right now*.
- **One-click launch** — opens a Windows Terminal tab in the agent's folder and starts `claude`, or just opens the folder in Explorer.
- **Groups by domain** — configurable rules bucket agents (infra / dev / docs / …) with icons and colors.

## Run it

```bash
pip install -r requirements.txt
streamlit run dashboard.py
```

Out of the box it reads the bundled [`example-vault/`](example-vault/) so you can see it working immediately. Point it at your own agents with an environment variable:

```bash
# Windows PowerShell
$env:AGENT_VAULT_ROOT = "C:\path\to\your\vault"
$env:DASHBOARD_USER   = "Your Name"
streamlit run dashboard.py
```

## Conventions it expects

The dashboard reads two files per agent folder:

- **`CLAUDE.md`** — first `# Heading` is the agent's name; the paragraph after it is the description.
- **`TODO.md`** *(optional)* — `- [ ]` items under `## URGENT` / `## WEEK` / `## PROGRESS` sections are counted and shown by bucket.

See `example-vault/` for the minimal shape.

## Notes

- **Localhost only** — Streamlit binds locally; nothing is exposed to the network.
- **Windows-oriented launcher** — the "Launch" button uses Windows Terminal (`wt`) / `cmd`. Discovery, TODO parsing and session detection are cross-platform; only the launch action is Windows-specific.
- The dashboard **reads** your agent files — it never writes to them.
- Comments are in Spanish (built for a Spanish-speaking user).

## License

MIT — see [LICENSE](LICENSE).
