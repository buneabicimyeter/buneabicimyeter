import datetime as dt
import html
import re
import sys
import urllib.request
from pathlib import Path

USER = sys.argv[1] if len(sys.argv) > 1 else "buneabicimyeter"
PROMPT_USER = "yoruldum"
ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"

BG = "#0d1117"
PANE = "#0b0f14"
BORDER = "#30363d"
BOX = "#11161d"
INK = "#e6edf3"
MUTED = "#8b949e"
DIM = "#6e7681"
GREEN = "#39d353"
LEVELS = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]
MONO = "ui-monospace, 'SF Mono', SFMono-Regular, 'Cascadia Mono', Consolas, 'Liberation Mono', Menlo, monospace"
SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif"
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def fetch_days(user):
    req = urllib.request.Request(
        f"https://github.com/users/{user}/contributions",
        headers={"User-Agent": "profile-readme-builder"},
    )
    page = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
    cells = re.findall(r'data-date="([\d-]+)" id="([^"]+)" data-level="(\d)"', page)
    tips = dict(re.findall(r'for="([^"]+)"[^>]*>([^<]*)</tool-tip>', page))
    if not cells:
        raise RuntimeError("contribution calendar not found; page layout changed?")
    days = []
    for date, cid, level in cells:
        m = re.match(r"(\d+) contribution", tips.get(cid, ""))
        days.append((dt.date.fromisoformat(date), int(m.group(1)) if m else 0, int(level)))
    days.sort()
    return days


def fmt(d):
    return f"{MONTHS[d.month - 1]} {d.day}"


def stats(days):
    counts = [c for _, c, _ in days]
    total = sum(counts)
    active = sum(1 for c in counts if c)

    longest, run, start, best_range = 0, 0, None, None
    for d, c, _ in days:
        if c:
            run += 1
            start = start or d
            if run > longest:
                longest, best_range = run, (start, d)
        else:
            run, start = 0, None

    i = len(days) - 1
    if i >= 0 and days[i][1] == 0:
        i -= 1
    cur, cur_end = 0, days[i][0] if i >= 0 else None
    while i >= 0 and days[i][1]:
        cur += 1
        i -= 1
    cur_range = (days[i + 1][0], cur_end) if cur else None

    best_day = max(days, key=lambda x: x[1]) if days else None

    last = days[-1][0]
    months = []
    for k in range(11, -1, -1):
        y, m = last.year, last.month - k
        while m <= 0:
            m += 12
            y -= 1
        months.append(((y, m), sum(c for d, c, _ in days if (d.year, d.month) == (y, m))))

    return {
        "total": total,
        "active": active,
        "span": len(days),
        "longest": longest,
        "longest_range": best_range,
        "current": cur,
        "current_range": cur_range,
        "best": best_day[1] if best_day else 0,
        "best_date": best_day[0] if best_day and best_day[1] else None,
        "avg": total / active if active else 0,
        "months": months,
    }


def esc(s):
    return html.escape(s, quote=False)


def typed_prompt(cmd, cx, y, size, clip_id, begin=0.2, dur=0.9):
    text = f"{PROMPT_USER}@github ~ $ {cmd}"
    cw = size * 0.6
    width = len(text) * cw
    x = cx - width / 2
    return f'''
  <clipPath id="{clip_id}"><rect x="{x - 2:.1f}" y="{y - size}" height="{size * 1.5}" width="0">
    <animate attributeName="width" from="0" to="{width + 4:.1f}" begin="{begin}s" dur="{dur}s" fill="freeze"
             calcMode="discrete" values="{';'.join(f'{(i * cw) + 2:.1f}' for i in range(len(text) + 1))}"/>
  </rect></clipPath>
  <text x="{x:.1f}" y="{y}" textLength="{width:.1f}" lengthAdjust="spacingAndGlyphs" clip-path="url(#{clip_id})"
        style="font:700 {size}px {MONO};fill:{INK}">{esc(text)}</text>
  <rect class="cursor" x="{x + width + 4:.1f}" y="{y - size * 0.82:.1f}" width="{size * 0.55:.1f}" height="{size:.1f}"
        fill="{INK}" style="animation-delay:{begin + dur:.2f}s"/>'''


COMMON_CSS = f"""
    .cursor {{ opacity: 0; animation: blink 1.1s steps(1) infinite; }}
    .in {{ opacity: 0; animation: in .5s cubic-bezier(.2,.7,.2,1) forwards; }}
    @keyframes blink {{ 0% {{ opacity: 1; }} 50% {{ opacity: 0; }} }}
    @keyframes in {{ from {{ opacity: 0; transform: translateY(6px); }} to {{ opacity: 1; transform: none; }} }}
    @media (prefers-reduced-motion: reduce) {{
      * {{ animation-duration: .01s !important; animation-delay: 0s !important; animation-iteration-count: 1 !important; }}
    }}"""


def contributions_svg(days, s):
    cell, gap = 14, 3
    pitch = cell + gap
    first = days[0][0]
    sunday = first - dt.timedelta(days=(first.weekday() + 1) % 7)
    cols = (days[-1][0] - sunday).days // 7 + 1
    gw = cols * pitch - gap
    W = 1000
    x0 = (W - gw) / 2 + 14
    y0 = 106
    H = y0 + 7 * pitch + 58

    rects, labels, seen = [], [], set()
    for d, c, lvl in days:
        col = (d - sunday).days // 7
        row = (d.weekday() + 1) % 7
        x, y = x0 + col * pitch, y0 + row * pitch
        delay = 1.25 + col * 0.028 + row * 0.012
        tip = f"{c} contribution{'s' if c != 1 else ''} on {fmt(d)}, {d.year}"
        rects.append(
            f'<rect class="c" x="{x}" y="{y}" width="{cell}" height="{cell}" rx="3" '
            f'fill="{LEVELS[lvl]}" style="animation-delay:{delay:.2f}s"><title>{tip}</title></rect>'
        )
        key = (d.year, d.month)
        if row == 0 and d.day <= 7 and key not in seen and col < cols - 1:
            seen.add(key)
            labels.append(
                f'<text class="lbl in" x="{x}" y="{y0 - 12}" style="animation-delay:1.1s">{MONTHS[d.month - 1]}</text>'
            )
    for row, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        labels.append(
            f'<text class="lbl in" x="{x0 - 10}" y="{y0 + row * pitch + 11}" text-anchor="end" '
            f'style="animation-delay:1.1s">{name}</text>'
        )

    end_delay = 1.25 + cols * 0.028 + 0.3
    total = f"{s['total']:,} contribution{'s' if s['total'] != 1 else ''} in the last year"
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img"
     aria-label="{esc(total)}">
  <title>{esc(total)}</title>
  <style>{COMMON_CSS}
    .lbl {{ font: 500 12px {SANS}; fill: {MUTED}; }}
    .c {{ opacity: 0; transform-box: fill-box; transform-origin: center;
          animation: pop .45s cubic-bezier(.3,1.4,.5,1) forwards; }}
    @keyframes pop {{ from {{ opacity: 0; transform: scale(.2); }} to {{ opacity: 1; transform: scale(1); }} }}
  </style>
  <rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="12" fill="{BG}" stroke="{BORDER}"/>
  {typed_prompt("./contributions.sh", W / 2, 50, 20, "p1")}
  {"".join(labels)}
  {"".join(rects)}
  <text class="in" x="{x0}" y="{y0 + 7 * pitch + 26}" style="font:600 13px {SANS};fill:{INK};animation-delay:{end_delay:.2f}s">{esc(total)}</text>
  <g class="in" style="animation-delay:{end_delay:.2f}s">
    <text x="{x0 + gw - 5 * 13 - 46}" y="{y0 + 7 * pitch + 26}" text-anchor="end" style="font:12px {SANS};fill:{MUTED}">Less</text>
    {"".join(f'<rect x="{x0 + gw - (5 - i) * 13 - 38}" y="{y0 + 7 * pitch + 16}" width="10" height="10" rx="2" fill="{c}"/>' for i, c in enumerate(LEVELS))}
    <text x="{x0 + gw}" y="{y0 + 7 * pitch + 26}" text-anchor="end" style="font:12px {SANS};fill:{MUTED}">More</text>
  </g>
</svg>
'''


def pane(x, y, w, h, title, delay):
    return f'''
  <g class="in" style="animation-delay:{delay}s">
    <rect x="{x + .5}" y="{y + .5}" width="{w - 1}" height="{h - 1}" rx="10" fill="{PANE}" stroke="{BORDER}"/>
    <line x1="{x}" x2="{x + w}" y1="{y + 30}" y2="{y + 30}" stroke="{BORDER}"/>
    <circle cx="{x + 18}" cy="{y + 15}" r="5" fill="#ff5f57"/>
    <circle cx="{x + 34}" cy="{y + 15}" r="5" fill="#febc2e"/>
    <circle cx="{x + 50}" cy="{y + 15}" r="5" fill="#28c840"/>
    <text x="{x + w / 2}" y="{y + 19}" text-anchor="middle" style="font:500 11px {MONO};fill:{DIM}">{esc(title)}</text>
  </g>'''


def stat_box(x, y, w, h, label, value, unit, sub, delay, accent=False):
    color = GREEN if accent else INK
    unit_t = f'<tspan dx="8" style="font:500 13px {MONO};fill:{MUTED}">{esc(unit)}</tspan>' if unit else ""
    return f'''
  <g class="in" style="animation-delay:{delay:.2f}s">
    <rect x="{x + .5}" y="{y + .5}" width="{w - 1}" height="{h - 1}" rx="6" fill="{BOX}" stroke="#21262d"/>
    <text x="{x + 14}" y="{y + 22}" style="font:500 12px {MONO};fill:{MUTED}">$ {esc(label)}</text>
    <text x="{x + 14}" y="{y + 56}" style="font:700 30px {MONO};fill:{color}">{esc(value)}{unit_t}</text>
    <text x="{x + 14}" y="{y + 76}" style="font:500 11px {MONO};fill:{DIM}">{esc(sub)}</text>
  </g>'''


def shaded_runs(text, shade):
    if not shade:
        return esc(text).replace(" ", " ")
    out, run, cur = [], "", None
    for ch, lv in zip(text, shade.ljust(len(text), "0")):
        if ch != " " and lv != cur:
            if run:
                out.append(f'<tspan class="s{cur}">{esc(run)}</tspan>' if cur else esc(run))
            run, cur = "", lv
        run += " " if ch == " " else ch
    if run:
        out.append(f'<tspan class="s{cur}">{esc(run)}</tspan>' if cur else esc(run))
    return "".join(out)


SHADE_COLORS = ["#2b3139", "#3a414b", "#4b535e", "#5e6672", "#737b87",
                "#8a929d", "#a2a9b3", "#bcc2ca", "#d8dce1", "#f4f6f8"]


def whoami_svg(s, ascii_lines, shade_lines=None):
    W, H = 1000, 600
    py, ph = 72, 518
    lx, lw = 10, 485
    rx, rw = 505, 485
    parts = [pane(lx, py, lw, ph, f"{PROMPT_USER}@github: ~/ascii.sh", 0.9),
             pane(rx, py, rw, ph, f"{PROMPT_USER}@github: ~/stats.sh", 0.9)]

    n = max(1, len(ascii_lines))
    cols = max(len(l) for l in ascii_lines) if ascii_lines else 1
    top_pad = 14
    area_w, area_h = lw - 40, ph - 30 - top_pad
    cw = min(area_w / cols, (area_h / n) * 0.62)
    lh = min(area_h / n, cw / 0.55)
    fs = lh * 1.75
    ax = lx + (lw - cols * cw) / 2
    last_baseline = py + ph - 1.5
    ay = last_baseline - (n - 1) * lh
    parts.append(
        f'<clipPath id="art"><rect x="{lx + 1}" y="{py + 31}" width="{lw - 2}" height="{ph - 32}" rx="9"/></clipPath>'
        f'<g clip-path="url(#art)">'
    )
    for i, line in enumerate(ascii_lines):
        stripped = line.lstrip(" ")
        if not stripped:
            continue
        lead = len(line) - len(stripped)
        body = shaded_runs(stripped, shade_lines[i][lead:] if shade_lines else "")
        parts.append(
            f'<text class="a" x="{ax + lead * cw:.1f}" y="{ay + i * lh:.2f}" textLength="{len(stripped) * cw:.1f}" '
            f'lengthAdjust="spacingAndGlyphs" style="font-size:{fs:.2f}px;animation-delay:{1.3 + i * 2.2 / n:.2f}s">{body}</text>'
        )
    parts.append("</g>")

    parts.append(
        f'<defs><linearGradient id="beamg" x1="0" x2="0" y1="0" y2="1">'
        f'<stop offset="0" stop-color="{GREEN}" stop-opacity="0"/>'
        f'<stop offset=".85" stop-color="{GREEN}" stop-opacity=".22"/>'
        f'<stop offset="1" stop-color="{GREEN}" stop-opacity=".9"/></linearGradient>'
        f'<clipPath id="lp"><rect x="{lx + 1}" y="{py + 31}" width="{lw - 2}" height="{ph - 32}" rx="9"/></clipPath></defs>'
        f'<g clip-path="url(#lp)"><rect class="beam" x="{lx}" y="{py + 31 - 38}" width="{lw}" height="40" fill="url(#beamg)"/></g>'
    )

    bw, bh, gx, gy = 224, 88, 9, 9
    bx, by = rx + 14, py + 44

    def rng(r):
        return f"{fmt(r[0])} - {fmt(r[1])}" if r else "no active streak"

    boxes = [
        ("current streak", str(s["current"]), "days", rng(s["current_range"]), True),
        ("longest streak", str(s["longest"]), "days", rng(s["longest_range"]), False),
        ("contributions", f"{s['total']:,}", "", "in the last year", False),
        ("active days", str(s["active"]), f"/ {s['span']}", f"{s['active'] * 100 // max(1, s['span'])}% of the year", False),
        ("best day", str(s["best"]), "", fmt(s["best_date"]) if s["best_date"] else "-", False),
        ("avg / active day", f"{s['avg']:.1f}", "", "contributions", False),
    ]
    for i, (label, value, unit, sub, acc) in enumerate(boxes):
        x = bx + (i % 2) * (bw + gx)
        y = by + (i // 2) * (bh + gy)
        parts.append(stat_box(x, y, bw, bh, label, value, unit, sub, 1.4 + i * 0.12, acc))

    cy = by + 3 * (bh + gy)
    cw2, ch = 2 * bw + gx, py + ph - 14 - cy
    parts.append(f'''
  <g class="in" style="animation-delay:2.1s">
    <rect x="{bx + .5}" y="{cy + .5}" width="{cw2 - 1}" height="{ch - 1}" rx="6" fill="{BOX}" stroke="#21262d"/>
    <text x="{bx + 14}" y="{cy + 22}" style="font:500 12px {MONO};fill:{MUTED}">$ contributions / month</text>
  </g>''')
    months = s["months"]
    peak = max((v for _, v in months), default=0) or 1
    top, bottom = cy + 50, cy + ch - 26
    slot = (cw2 - 28) / len(months)
    bar_w = slot * 0.62
    peak_i = max(range(len(months)), key=lambda i: months[i][1])
    for i, ((y, m), v) in enumerate(months):
        h = max(2, (bottom - top) * v / peak)
        x = bx + 14 + i * slot + (slot - bar_w) / 2
        d = 2.3 + i * 0.06
        fill = GREEN if v else "#21262d"
        parts.append(
            f'<rect class="b" x="{x:.1f}" y="{bottom - h:.1f}" width="{bar_w:.1f}" height="{h:.1f}" rx="2" '
            f'fill="{fill}" style="animation-delay:{d:.2f}s"><title>{MONTHS[m - 1]} {y}: {v}</title></rect>'
            f'<text class="in" x="{x + bar_w / 2:.1f}" y="{bottom + 16}" text-anchor="middle" '
            f'style="font:500 10px {MONO};fill:{DIM};animation-delay:2.2s">{MONTHS[m - 1][0]}</text>'
        )
        if i == peak_i and v:
            parts.append(
                f'<text class="in" x="{x + bar_w / 2:.1f}" y="{bottom - h - 7:.1f}" text-anchor="middle" '
                f'style="font:700 11px {MONO};fill:{INK};animation-delay:{d + .5:.2f}s">{v:,}</text>'
            )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img"
     aria-label="whoami: ascii art and contribution stats">
  <title>{PROMPT_USER}@github ~ $ whoami</title>
  <style>{COMMON_CSS}
    .a {{ font-family: {MONO}; fill: {SHADE_COLORS[5]}; opacity: 0; animation: show .3s ease-out forwards; }}
    {" ".join(f".s{i} {{ fill: {c}; }}" for i, c in enumerate(SHADE_COLORS))}
    .beam {{ opacity: 0; animation: beam 2.4s cubic-bezier(.4,0,.6,1) 1.2s forwards; }}
    @keyframes show {{ to {{ opacity: 1; }} }}
    @keyframes beam {{ 0% {{ opacity: 0; transform: translateY(0); }} 8% {{ opacity: 1; }}
                      90% {{ opacity: 1; }} 100% {{ opacity: 0; transform: translateY({ph - 40}px); }} }}
    .b {{ transform-box: fill-box; transform-origin: bottom; transform: scaleY(0);
          animation: grow .7s cubic-bezier(.2,.8,.2,1) forwards; }}
    @keyframes grow {{ to {{ transform: scaleY(1); }} }}
  </style>
  <rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="12" fill="{BG}" stroke="{BORDER}"/>
  {typed_prompt("whoami", W / 2, 46, 20, "p2", begin=0.15, dur=0.5)}
  {"".join(parts)}
</svg>
'''


STACK = [
    ("~/frontend", "frontend", ["react", "html", "css", "js"],
     "Responsive interfaces, admin panels and dashboards in React, HTML, CSS and JavaScript."),
    ("~/backend", "backend & systems", ["nodejs", "php", "py", "vscode"],
     "APIs, automation tools and server-side systems with Node.js, PHP and Python."),
    ("~/fivem", "fivem & bots", ["lua", "fivem", "discord"],
     "Custom scripts and roleplay mechanics in Lua on QBCore / QBX, plus the Discord bots around them."),
]


def icon_uri(name):
    import base64
    data = (ASSETS / "icons" / f"{name}.svg").read_bytes()
    return "data:image/svg+xml;base64," + base64.b64encode(data).decode()


def wrap(text, width):
    lines, cur = [], ""
    for word in text.split():
        if cur and len(cur) + 1 + len(word) > width:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    return lines + [cur] if cur else lines


def stack_svg():
    W, H = 1000, 310
    py, ph, pw, gap = 72, 226, 320, 10
    parts = []
    for i, (title, label, icons, desc) in enumerate(STACK):
        x = 10 + i * (pw + gap)
        d0 = 0.8 + i * 0.2
        parts.append(pane(x, py, pw, ph, f"{PROMPT_USER}@github: {title}", d0))
        parts.append(
            f'<text class="in" x="{x + 20}" y="{py + 60}" style="font:600 14px {MONO};fill:{INK};'
            f'animation-delay:{d0 + .15:.2f}s"><tspan fill="{GREEN}">$</tspan> {esc(label)}</text>'
        )
        size, igap = 52, 14
        ix = x + 20
        for k, name in enumerate(icons):
            parts.append(
                f'<image class="pop" href="{icon_uri(name)}" x="{ix + k * (size + igap)}" y="{py + 80}" '
                f'width="{size}" height="{size}" style="animation-delay:{d0 + .3 + k * .09:.2f}s"/>'
            )
        for j, line in enumerate(wrap(desc, 38)):
            parts.append(
                f'<text class="in" x="{x + 20}" y="{py + 170 + j * 19}" style="font:500 12.5px {MONO};fill:{MUTED};'
                f'animation-delay:{d0 + .6 + j * .08:.2f}s">{esc(line)}</text>'
            )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img"
     aria-label="Tech stack: React, HTML, CSS, JavaScript, Node.js, PHP, Python, Lua, FiveM, Discord">
  <title>{PROMPT_USER}@github ~ $ ./stack.sh</title>
  <style>{COMMON_CSS}
    .pop {{ opacity: 0; transform-box: fill-box; transform-origin: center;
            animation: pop .5s cubic-bezier(.3,1.5,.5,1) forwards; }}
    @keyframes pop {{ from {{ opacity: 0; transform: scale(.4); }} to {{ opacity: 1; transform: scale(1); }} }}
  </style>
  <rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="12" fill="{BG}" stroke="{BORDER}"/>
  {typed_prompt("./stack.sh", W / 2, 46, 20, "p3", begin=0.15, dur=0.6)}
  {"".join(parts)}
</svg>
'''


def api(path):
    import json
    import os
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "profile-readme-builder"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"https://api.github.com{path}", headers=headers)
    return json.load(urllib.request.urlopen(req, timeout=30))


def ago(iso, now):
    t = dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    sec = int((now - t).total_seconds())
    for unit, size in (("year", 31536000), ("month", 2592000), ("week", 604800),
                       ("day", 86400), ("hour", 3600), ("minute", 60)):
        if sec >= size:
            n = sec // size
            return f"{n} {unit}{'s' if n != 1 else ''} ago"
    return "just now"


def clip(text, width):
    text = " ".join((text or "").split())
    if len(text) <= width:
        return text
    cut = text[: width - 1].rsplit(" ", 1)[0].rstrip(" ,.;:-—")
    return cut + "…"


def live_blocks(user):
    now = dt.datetime.now(dt.timezone.utc)
    profile = api(f"/users/{user}")
    repos = [r for r in api(f"/users/{user}/repos?per_page=100&type=owner")
             if not r["fork"] and not r["archived"] and r["name"].lower() != user.lower()]
    repos.sort(key=lambda r: (-r["stargazers_count"], r["pushed_at"]), reverse=False)

    name_w = max((len(r["name"]) for r in repos), default=10) + 1
    lang_w = max((len(r["language"] or "-") for r in repos), default=4)
    rows = [
        f"★ {r['stargazers_count']:<3} {(r['language'] or '-'):<{lang_w}}  {(r['name'] + '/'):<{name_w}}  "
        f"{clip(r['description'], 58)}"
        for r in repos
    ]
    projects = "\n".join([f"{PROMPT_USER}@github ~ $ ls -l ~/projects", f"total {len(repos)}"] + rows)

    commits = []
    for r in repos:
        try:
            for c in api(f"/repos/{user}/{r['name']}/commits?per_page=5"):
                if (c.get("author") or {}).get("login", "").lower() == user.lower():
                    commits.append((c["commit"]["author"]["date"], r["name"], c["sha"][:7],
                                    c["commit"]["message"].splitlines()[0]))
        except Exception:
            continue
    commits.sort(reverse=True)
    repo_w = max((len(c[1]) for c in commits[:6]), default=10)
    log = [f"{PROMPT_USER}@github ~ $ git log --all --oneline -6"] + [
        f"{sha}  {repo:<{repo_w}}  {clip(msg, 42):<42}  {ago(date, now)}" for date, repo, sha, msg in commits[:6]
    ]
    if len(log) == 1:
        log.append("no public commits yet")

    created = dt.datetime.fromisoformat(profile["created_at"].replace("Z", "+00:00"))
    months = (now.year - created.year) * 12 + now.month - created.month
    age = f"{months // 12}y {months % 12}mo" if months >= 12 else f"{months}mo"
    stars = sum(r["stargazers_count"] for r in repos)
    last_push = max((r["pushed_at"] for r in repos), default=None)
    langs = {}
    for r in repos:
        if r["language"]:
            langs[r["language"]] = langs.get(r["language"], 0) + 1
    uptime = "\n".join([
        f"{PROMPT_USER}@github ~ $ uptime",
        f"up {age} · {len(repos)} public repos · {stars} ★ · {profile['followers']} followers"
        + (f" · last push {ago(last_push, now)}" if last_push else ""),
        f"langs: " + "  ".join(f"{k} ×{v}" for k, v in sorted(langs.items(), key=lambda kv: -kv[1])),
    ])

    return {"projects": projects, "gitlog": "\n".join(log), "uptime": uptime}


def update_readme(blocks):
    path = ROOT / "README.md"
    text = path.read_text(encoding="utf-8")
    for key, body in blocks.items():
        pattern = re.compile(rf"(<!-- live:{key} -->).*?(<!-- /live:{key} -->)", re.S)
        if not pattern.search(text):
            print(f"marker live:{key} missing in README, skipped")
            continue
        text = pattern.sub(lambda m: f"{m.group(1)}\n```console\n{body}\n```\n{m.group(2)}", text)
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    days = fetch_days(USER)
    s = stats(days)
    art = (ASSETS / "ascii.txt").read_text(encoding="utf-8").replace("\r", "").rstrip("\n").split("\n")
    shade_file = ASSETS / "ascii-shade.txt"
    shade = shade_file.read_text(encoding="utf-8").replace("\r", "").rstrip("\n").split("\n") if shade_file.exists() else None
    (ASSETS / "contributions.svg").write_text(contributions_svg(days, s), encoding="utf-8")
    (ASSETS / "whoami.svg").write_text(whoami_svg(s, art, shade), encoding="utf-8")
    (ASSETS / "stack.svg").write_text(stack_svg(), encoding="utf-8")
    try:
        update_readme(live_blocks(USER))
    except Exception as exc:
        print(f"live README blocks skipped: {exc}")
    print(f"{USER}: {s['total']} contributions, {s['active']} active days, "
          f"streak {s['current']} / longest {s['longest']}")
