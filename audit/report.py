"""
GuiGazer — HTML Audit Report Generator
=======================================
Produces a self-contained, dark-themed HTML report from the results of
:func:`audit.accessibility.run_full_audit`.

The generated file embeds all CSS inline so it can be opened stand-alone in
any browser and optionally includes the original screenshot as a base64 image.
"""

from __future__ import annotations

import base64
from pathlib import Path

from loguru import logger


# ── grading ──────────────────────────────────────────────────────────────

def _grade(score: int) -> tuple[str, str]:
    """Return (letter_grade, badge_colour) for a 0-100 score."""
    if score >= 90:
        return "A", "#22c55e"
    if score >= 75:
        return "B", "#8b5cf6"
    if score >= 50:
        return "C", "#f59e0b"
    return "F", "#ef4444"


# ── badge helper ─────────────────────────────────────────────────────────

def _pass_badge(passed: bool) -> str:
    if passed:
        return '<span class="badge pass">PASS</span>'
    return '<span class="badge fail">FAIL</span>'


# ── main template ────────────────────────────────────────────────────────

_CSS = """\
:root{--bg:#0f1115;--surface:#16181d;--glass:rgba(255,255,255,.04);
--border:rgba(255,255,255,.06);--accent:#8b5cf6;--text:#e2e8f0;
--muted:#94a3b8;--green:#22c55e;--red:#ef4444;--amber:#f59e0b;}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--text);font-family:'Inter',system-ui,sans-serif;
padding:2rem;line-height:1.6}
h1{font-size:1.8rem;font-weight:700;margin-bottom:.25rem}
h2{font-size:1.25rem;font-weight:600;margin:2rem 0 .75rem;color:var(--accent)}
.subtitle{color:var(--muted);font-size:.9rem;margin-bottom:2rem}
.grade-wrap{display:flex;align-items:center;gap:1.5rem;margin-bottom:2rem}
.grade-circle{width:80px;height:80px;border-radius:50%;display:flex;
align-items:center;justify-content:center;font-size:2rem;font-weight:800;
color:#fff;box-shadow:0 0 30px var(--glow)}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:1rem;margin-bottom:2rem}
.card{background:var(--glass);border:1px solid var(--border);border-radius:14px;
padding:1.25rem;backdrop-filter:blur(12px)}
.card .num{font-size:1.6rem;font-weight:700}
.card .lbl{color:var(--muted);font-size:.8rem;margin-top:.25rem}
table{width:100%;border-collapse:collapse;margin-bottom:2rem;font-size:.85rem}
thead th{text-align:left;padding:.6rem .8rem;border-bottom:1px solid var(--border);
color:var(--muted);font-weight:500;text-transform:uppercase;font-size:.72rem;letter-spacing:.04em}
tbody td{padding:.55rem .8rem;border-bottom:1px solid var(--border)}
tbody tr:hover{background:var(--glass)}
.badge{display:inline-block;padding:2px 10px;border-radius:9999px;font-size:.72rem;
font-weight:600;text-transform:uppercase;letter-spacing:.03em}
.badge.pass{background:rgba(34,197,94,.15);color:var(--green)}
.badge.fail{background:rgba(239,68,68,.15);color:var(--red)}
.screenshot{max-width:100%;border-radius:12px;border:1px solid var(--border);margin:1.5rem 0}
@media(max-width:640px){.cards{grid-template-columns:1fr 1fr}body{padding:1rem}}
"""


def generate_html_report(
    audit_results: dict,
    screenshot_path: str | None = None,
) -> str:
    """Build a self-contained HTML string from *audit_results*.

    Parameters
    ----------
    audit_results:
        Dict returned by :func:`audit.accessibility.run_full_audit`.
    screenshot_path:
        Optional filesystem path to the screenshot; it will be embedded as
        a base64 ``<img>`` tag.

    Returns
    -------
    str
        Complete HTML document.
    """
    summary = audit_results["summary"]
    details = audit_results["details"]
    score = summary["overall_score"]
    grade, grade_colour = _grade(score)

    # ── optional screenshot ──────────────────────────────────────────
    screenshot_tag = ""
    if screenshot_path:
        try:
            raw = Path(screenshot_path).read_bytes()
            b64 = base64.b64encode(raw).decode()
            ext = Path(screenshot_path).suffix.lstrip(".") or "png"
            screenshot_tag = (
                f'<img class="screenshot" src="data:image/{ext};base64,{b64}" '
                f'alt="Audited screenshot" />'
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not embed screenshot: {}", exc)

    # ── contrast table ───────────────────────────────────────────────
    contrast_rows = ""
    for c in details.get("contrast", []):
        contrast_rows += (
            f"<tr><td>{c['element_id']}</td><td>{c['class_name']}</td>"
            f"<td>{c['contrast_ratio']}</td>"
            f"<td>{_pass_badge(c['passes_aa'])}</td>"
            f"<td>{_pass_badge(c['passes_aaa'])}</td></tr>\n"
        )

    # ── touch-target table ───────────────────────────────────────────
    touch_rows = ""
    for t in details.get("touch_targets", []):
        touch_rows += (
            f"<tr><td>{t['element_id']}</td><td>{t['class_name']}</td>"
            f"<td>{t['width']}×{t['height']}</td>"
            f"<td>{_pass_badge(t['passes'])}</td></tr>\n"
        )

    # ── label table ──────────────────────────────────────────────────
    label_rows = ""
    for l in details.get("labels", []):
        label_rows += (
            f"<tr><td>{l['element_id']}</td>"
            f"<td>{_pass_badge(l['has_label'])}</td>"
            f"<td>{l['label_text'] or '—'}</td></tr>\n"
        )

    html = f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>GuiGazer Accessibility Report</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet" />
<style>{_CSS}</style>
</head>
<body>
<h1>🔍 GuiGazer Accessibility Report</h1>
<p class="subtitle">Automated WCAG 2.1 audit powered by GuiGazer</p>

<div class="grade-wrap">
  <div class="grade-circle" style="background:{grade_colour};--glow:{grade_colour}55">{grade}</div>
  <div>
    <div style="font-size:1.4rem;font-weight:700">{score}/100</div>
    <div style="color:var(--muted);font-size:.85rem">Overall Accessibility Score</div>
  </div>
</div>

<div class="cards">
  <div class="card"><div class="num">{summary['total_elements']}</div><div class="lbl">Elements Scanned</div></div>
  <div class="card"><div class="num" style="color:{'var(--green)' if summary['contrast_issues'] == 0 else 'var(--red)'}">{summary['contrast_issues']}</div><div class="lbl">Contrast Issues</div></div>
  <div class="card"><div class="num" style="color:{'var(--green)' if summary['touch_target_issues'] == 0 else 'var(--amber)'}">{summary['touch_target_issues']}</div><div class="lbl">Touch-Target Issues</div></div>
  <div class="card"><div class="num" style="color:{'var(--green)' if summary['label_issues'] == 0 else 'var(--amber)'}">{summary['label_issues']}</div><div class="lbl">Label Issues</div></div>
</div>

{screenshot_tag}

<h2>Contrast Ratios</h2>
<table>
<thead><tr><th>Element</th><th>Class</th><th>Ratio</th><th>AA</th><th>AAA</th></tr></thead>
<tbody>{contrast_rows if contrast_rows else '<tr><td colspan="5" style="color:var(--muted)">No elements analysed</td></tr>'}</tbody>
</table>

<h2>Touch Targets</h2>
<table>
<thead><tr><th>Element</th><th>Class</th><th>Size</th><th>Passes</th></tr></thead>
<tbody>{touch_rows if touch_rows else '<tr><td colspan="4" style="color:var(--muted)">No interactive elements found</td></tr>'}</tbody>
</table>

<h2>Input Labels</h2>
<table>
<thead><tr><th>Element</th><th>Has Label</th><th>Label Text</th></tr></thead>
<tbody>{label_rows if label_rows else '<tr><td colspan="3" style="color:var(--muted)">No text inputs found</td></tr>'}</tbody>
</table>

<p style="color:var(--muted);font-size:.75rem;margin-top:3rem;text-align:center">
  Generated by GuiGazer · WCAG 2.1 automated audit
</p>
</body>
</html>"""

    logger.info("Generated HTML report — grade={} score={}", grade, score)
    return html


def save_report(html: str, path: str) -> None:
    """Write the HTML report to *path*, creating parent dirs as needed."""
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(html, encoding="utf-8")
    logger.info("Audit report saved → {}", dest.resolve())
