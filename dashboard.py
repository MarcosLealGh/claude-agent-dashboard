"""
Claude Agent Dashboard — un "command center" para gestionar múltiples agentes
de Claude Code desde una sola pantalla.

Descubre agentes (carpetas con un CLAUDE.md) bajo un directorio raíz, parsea sus
TODO.md, detecta qué sesiones de Claude están corriendo ahora mismo, y permite
lanzar cada agente en su propia terminal o abrir su carpeta — todo desde el navegador.

Configuración (variables de entorno, con defaults que corren out-of-the-box):
    AGENT_VAULT_ROOT   raíz donde buscar agentes (default: ./example-vault)
    DASHBOARD_USER     nombre a mostrar en el título (default: "User")

Uso:
    pip install -r requirements.txt
    streamlit run dashboard.py

Corre en localhost. No expone nada a la red.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import urllib.parse
from datetime import datetime
from pathlib import Path

import streamlit as st

# ─── CONFIG ────────────────────────────────────────────────────────────────────
DASHBOARD_USER = os.environ.get("DASHBOARD_USER", "User")
VAULT_ROOT = Path(os.environ.get("AGENT_VAULT_ROOT", Path(__file__).parent / "example-vault")).resolve()

# Reglas de dominio: si la ruta del agente contiene la clave, se le asigna ese
# dominio (para agrupar y colorear). Ajusta a tu propia taxonomía.
DOMAIN_RULES = [
    ("Infra",    "Infra"),
    ("Security", "Infra"),
    ("Backend",  "Dev"),
    ("Frontend", "Dev"),
    ("Docs",     "Docs"),
    ("Personal", "Personal"),
]

DOMAIN_ICON = {"Infra": "🔷", "Dev": "🟣", "Docs": "📄", "Personal": "🏠", "General": "⬜"}
DOMAIN_COLOR = {"Infra": "#00BFFF", "Dev": "#DA70D6", "Docs": "#FFD700", "Personal": "#32CD32", "General": "#808080"}


def get_domain(path: str) -> str:
    for key, domain in DOMAIN_RULES:
        if key in path:
            return domain
    return "General"


# ─── PARSING ───────────────────────────────────────────────────────────────────

def extract_name(content: str) -> str:
    for line in content.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return "Sin nombre"


def extract_desc(content: str) -> str:
    lines = content.splitlines()
    past_header = False
    desc: list[str] = []
    for line in lines:
        if line.startswith("# ") and not past_header:
            past_header = True
            continue
        if past_header:
            s = line.strip()
            if s == "" and desc:
                break
            if s.startswith("#") or s == "---":
                break
            if s:
                desc.append(s)
    return " ".join(desc)


def parse_todo(agent_dir: Path) -> dict:
    """Cuenta tareas pendientes de un TODO.md, clasificadas por sección."""
    base = {"total": 0, "urgent": [], "week": [], "progress": []}
    todo_file = agent_dir / "TODO.md"
    if not todo_file.exists():
        return base
    try:
        content = todo_file.read_text(encoding="utf-8")
    except OSError:
        return base

    section = ""
    for line in content.splitlines():
        if line.startswith("## "):
            section = line[3:].strip().upper()
        elif line.strip().startswith("- [ ]"):
            raw = line.strip()[6:].strip()
            m = re.search(r"\*\*(.*?)\*\*", raw)
            task = (m.group(1) if m else raw.split("—")[0].strip())[:70]
            base["total"] += 1
            if "URGENT" in section or "BLOCK" in section:
                base["urgent"].append(task)
            elif "WEEK" in section or "SEMANA" in section:
                base["week"].append(task)
            elif "PROGRESS" in section or "PROGRESO" in section:
                base["progress"].append(task)
            else:
                base["week"].append(task)
    return base


def get_active_sessions(all_agents: list) -> set:
    """Detecta qué agentes tienen una sesión de Claude corriendo (por cwd del proceso)."""
    try:
        import psutil
    except ImportError:
        return set()
    active_cwds: set[str] = set()
    for proc in psutil.process_iter(["name", "cwd"]):
        try:
            if proc.info["name"] and "claude" in proc.info["name"].lower():
                cwd = proc.info["cwd"]
                if cwd:
                    active_cwds.add(str(Path(cwd).resolve()))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return {a["path"] for a in all_agents if str(Path(a["path"]).resolve()) in active_cwds}


def last_modified(path: Path) -> str:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).strftime("%d/%m/%Y")
    except OSError:
        return "N/A"


# ─── DISCOVERY ─────────────────────────────────────────────────────────────────

def discover_agents() -> list:
    """Cada carpeta con un CLAUDE.md (excepto la raíz) es un agente."""
    agents = []
    if not VAULT_ROOT.exists():
        return agents
    for claude_md in sorted(VAULT_ROOT.rglob("CLAUDE.md")):
        agent_dir = claude_md.parent
        if agent_dir == VAULT_ROOT:  # el dispatcher raíz no es un agente
            continue
        try:
            content = claude_md.read_text(encoding="utf-8")
        except OSError:
            continue
        rel = agent_dir.relative_to(VAULT_ROOT)
        agents.append({
            "name": extract_name(content),
            "desc": extract_desc(content),
            "domain": get_domain(str(agent_dir)),
            "sub": " / ".join(rel.parts),
            "path": str(agent_dir),
            "todo": parse_todo(agent_dir),
            "last_mod": last_modified(claude_md),
        })
    return agents


# ─── LAUNCHER ──────────────────────────────────────────────────────────────────

def launch_agent(path: str, title: str = "Claude", color: str = "07"):
    """Abre una terminal en la carpeta del agente y arranca `claude`."""
    try:
        temp = Path(os.environ.get("TEMP", Path.home() / "AppData" / "Local" / "Temp"))
        bat = temp / "launch_agent.bat"
        bat.write_text(f'@echo off\ncd /d "{path}"\nclaude\n', encoding="utf-8")
        wt = shutil.which("wt")
        if wt:
            subprocess.Popen([wt, "new-tab", "--title", title, "--suppressApplicationTitle",
                              "--tabColor", color, "cmd", "/K", str(bat)])
        else:
            subprocess.Popen(["cmd", "/c", "start", "", "cmd", "/K", str(bat)])
        return True
    except OSError as e:
        return str(e)


def open_folder(path: str):
    try:
        subprocess.Popen(["explorer", path])
        return True
    except OSError as e:
        return str(e)


# ─── COMPONENTS ────────────────────────────────────────────────────────────────

def agent_card(agent: dict, key: str, is_active: bool = False):
    todo = agent["todo"]
    dot = "🟢" if is_active else "🔴"
    with st.expander(f"{dot} **{agent['name']}**", expanded=False):
        st.caption(f"📁 {agent['sub']}  ·  mod. {agent['last_mod']}  ·  `{agent['domain']}`")
        d = agent["desc"]
        if d:
            st.markdown(f"*{d[:160]}{'…' if len(d) > 160 else ''}*")
        if todo["total"] > 0:
            st.divider()
            shown = 0
            for t in todo["urgent"][:3]:
                st.markdown(f"🔴 {t}"); shown += 1
            for t in todo["week"][:2]:
                st.markdown(f"🟡 {t}"); shown += 1
            for t in todo["progress"][:2]:
                st.markdown(f"🔵 {t}"); shown += 1
            remaining = todo["total"] - shown
            if remaining > 0:
                st.caption(f"+ {remaining} más…")
        st.divider()
        term_color = DOMAIN_COLOR.get(agent.get("domain", "General"), "07")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("▶ Lanzar Claude", key=f"launch_{key}", width="stretch"):
                result = launch_agent(agent["path"], title=agent["name"], color=term_color)
                st.success("Terminal abierto") if result is True else st.error(f"Error: {result}")
        with c2:
            if st.button("📂 Carpeta", key=f"folder_{key}", width="stretch"):
                result = open_folder(agent["path"])
                st.success("Carpeta abierta") if result is True else st.error(f"Error: {result}")


def render_section(agents: list, key_prefix: str, active_paths: set):
    cols = st.columns(3)
    for idx, agent in enumerate(agents):
        with cols[idx % 3]:
            agent_card(agent, f"{key_prefix}_{idx}", agent["path"] in active_paths)


# ─── APP ───────────────────────────────────────────────────────────────────────

st.set_page_config(page_title=f"{DASHBOARD_USER} Dashboard", layout="wide")
st.title(f"{DASHBOARD_USER} — Agent Command Center")
st.caption(f"{datetime.now().strftime('%d/%m/%Y  %H:%M')}  ·  raíz: `{VAULT_ROOT}`")

all_agents = discover_agents()
active_paths = get_active_sessions(all_agents)

if not all_agents:
    st.warning(f"No se encontraron agentes (carpetas con CLAUDE.md) bajo `{VAULT_ROOT}`. "
               "Define AGENT_VAULT_ROOT o usa el example-vault incluido.")
    st.stop()


def sort_agents(lst):
    return sorted(lst, key=lambda a: (-len(a["todo"]["urgent"]), -a["todo"]["total"]))


with st.sidebar:
    st.subheader("Sesiones activas")
    if active_paths:
        for a in all_agents:
            if a["path"] in active_paths:
                st.markdown(f"🟢 {DOMAIN_ICON.get(a['domain'], '⬜')} **{a['name']}**")
                st.caption(a["sub"])
    else:
        st.caption("Ninguna sesión Claude corriendo")
    st.divider()
    auto_refresh = st.toggle("Auto-refresh", value=True)
    refresh_interval = st.select_slider("Intervalo (min)", options=[1, 2, 5, 10, 15, 30],
                                        value=1, disabled=not auto_refresh)
    if st.button("↺ Recargar ahora", width="stretch"):
        st.rerun()

# Agrupa por dominio y renderiza cada sección
domains = {}
for a in all_agents:
    domains.setdefault(a["domain"], []).append(a)

for domain in sorted(domains):
    st.divider()
    st.subheader(f"{DOMAIN_ICON.get(domain, '⬜')} {domain}")
    render_section(sort_agents(domains[domain]), domain.lower(), active_paths)

if auto_refresh:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=refresh_interval * 60 * 1000, key="autorefresh")
