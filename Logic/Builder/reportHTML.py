from typing import Dict, Any
from ..render import html_safe
from Logic.converter import coerce_bias_list
import json
import os

APP_TITLE = os.getenv("APP_TITLE")


def build_report_html(report: Dict[str, Any]) -> str:
    """
    Build a standalone HTML report from the current panel state.
    The report can be opened in a browser and printed/saved as PDF.
    """

    snapshot = report.get("snapshot") if isinstance(report.get("snapshot"), dict) else {}
    prompts = report.get("prompts") if isinstance(report.get("prompts"), dict) else {}
    matrix = report.get("matrix") if isinstance(report.get("matrix"), dict) else {}
    top_records = snapshot.get("top_records") if isinstance(snapshot.get("top_records"), list) else []
    biases = coerce_bias_list(prompts.get("detected_biases"))

    top_records_html = ""
    for record in top_records:
        record_dict = record if isinstance(record, dict) else {}
        title = html_safe(record_dict.get("title", "Untitled"))
        url = html_safe(record_dict.get("url", ""))
        source = html_safe(record_dict.get("source", ""))
        score = html_safe(record_dict.get("score", ""))

        if url:
            top_records_html += (
                f'<li><a href="{url}" target="_blank">{title}</a>'
                f'<br><small>{source} · Score: {score}</small></li>'
            )
        else:
            top_records_html += (
                f"<li>{title}<br><small>{source} · Score: {score}</small></li>"
            )

    biases_html = ""
    if biases:
        for bias in biases:
            if isinstance(bias, dict):
                name = html_safe(bias.get("bias", ""))
                explanation = html_safe(bias.get("explanation", ""))
            else:
                name = html_safe(str(bias))
                explanation = ""

            biases_html += f"""
            <div class="risk">
                <strong>{name}</strong>
                <p>{explanation}</p>
            </div>
            """
    else:
        biases_html = "<p>No translation risk patterns detected.</p>"

    prompt_sections = ""
    for label, key in [
        ("Master Prompt", "master_prompt"),
        ("Counter Prompt", "counter_prompt"),
        ("Uncertainty Mapping", "uncertainty_prompt"),
        ("Redesign Prompt", "redesign_prompt"),
    ]:
        value = html_safe(prompts.get(key, ""))
        if value:
            prompt_sections += f"""
            <h3>{label}</h3>
            <pre>{value}</pre>
            """
    look_for_items = prompts.get("look_for") if isinstance(prompts.get("look_for"), list) else []
    look_for_html = ""
    if look_for_items:
        items = "".join(f"<li>{html_safe(item)}</li>" for item in look_for_items)
        look_for_html = f"""
        <h2>Checklist for AI Response</h2>
        <ul>{items}</ul>
        """

    matrix_rows = ""
    for lens_name, result in matrix.items():
        result_dict = result if isinstance(result, dict) else {}
        support = html_safe(result_dict.get("support_level", "none"))
        risk_list = coerce_bias_list(result_dict.get("detected_biases"))
        risk_text = (
            ", ".join(
                b.get("bias", "") if isinstance(b, dict) else str(b)
                for b in risk_list
            )
            if risk_list
            else "None"
        )

        query_used = html_safe(result_dict.get("query_used", ""))

        matrix_rows += f"""
        <tr>
            <td>{html_safe(lens_name.capitalize())}</td>
            <td>{support}</td>
            <td>{html_safe(risk_text)}</td>
            <td>{query_used}</td>
        </tr>
        """

    report_json = html_safe(json.dumps(report, indent=2, ensure_ascii=False))

    html = f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>{html_safe(APP_TITLE)} Report - {html_safe(report.get("panel_id", ""))}</title>
<style>
body {{
    font-family: Inter, Arial, sans-serif;
    margin: 40px;
    color: #17191d;
    line-height: 1.6;
}}
h1, h2, h3 {{
    color: #17191d;
}}
a {{
    color: #b86f5d;
}}
.meta {{
    color: #6e7683;
    font-size: 13px;
    margin-bottom: 24px;
}}
.box {{
    border: 1px solid #e5e7eb;
    border-left: 4px solid #d88d7a;
    border-radius: 10px;
    padding: 14px 16px;
    margin: 14px 0;
    background: #fafafa;
}}
pre {{
    white-space: pre-wrap;
    word-break: break-word;
    background: #f7f7f8;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 12px;
    font-size: 13px;
}}
table {{
    width: 100%;
    border-collapse: collapse;
    margin-top: 12px;
}}
th, td {{
    border: 1px solid #e5e7eb;
    padding: 10px;
    text-align: left;
    vertical-align: top;
}}
th {{
    background: #f3f4f6;
}}
.risk {{
    border: 1px solid #e5e7eb;
    border-left: 4px solid #cf8695;
    padding: 10px 12px;
    border-radius: 8px;
    margin: 8px 0;
}}
.print-button {{
    padding: 8px 14px;
    border: 1px solid #d88d7a;
    background: #fff;
    color: #d88d7a;
    border-radius: 8px;
    cursor: pointer;
    font-weight: 600;
}}
@media print {{
    body {{
        margin: 20mm;
    }}
    .no-print {{
        display: none;
    }}
}}
</style>
</head>
<body>

<button class="print-button no-print" onclick="window.print()">Print / Save as PDF</button>

<h1>{html_safe(APP_TITLE)} Report</h1>

<div class="meta">
    App: {html_safe(report.get("app"))} ·
    Version: {html_safe(report.get("version"))} ·
    Exported at: {html_safe(report.get("exported_at"))} ·
    Panel: {html_safe(report.get("panel_id"))}
</div>

<h2>Design Claim</h2>
<div class="box">{html_safe(report.get("claim"))}</div>

<h2>Active Query</h2>
<div class="box">{html_safe(report.get("active_query"))}</div>

<h2>Refined Query</h2>
<div class="box">{html_safe(report.get("refined_query"))}</div>

<h2>Evidence Snapshot</h2>
<table>
<tr><th>Total Records</th><td>{html_safe(snapshot.get("combined_count", 0))}</td></tr>
<tr><th>Direct Matches</th><td>{html_safe(snapshot.get("direct_hits", 0))}</td></tr>
<tr><th>Support Level</th><td>{html_safe(snapshot.get("support_level", "none"))}</td></tr>
<tr><th>Summary</th><td>{html_safe(snapshot.get("summary", "No summary available."))}</td></tr>
</table>

<h2>Top Retrieved Records</h2>
<ol>{top_records_html if top_records_html else "<li>No records available.</li>"}</ol>

<h2>Detected Translation Risk Patterns</h2>
{biases_html}

<h2>Generated Prompts</h2>
{prompt_sections if prompt_sections else "<p>No prompts generated.</p>"}

{look_for_html}

<h2>Multi-Lens Audit Matrix</h2>
<table>
<thead>
<tr>
    <th>Lens</th>
    <th>Support</th>
    <th>Risk Patterns</th>
    <th>Query Used</th>
</tr>
</thead>
<tbody>
{matrix_rows if matrix_rows else '<tr><td colspan="4">No multi-lens audit available.</td></tr>'}
</tbody>
</table>

<h2>Raw JSON Snapshot</h2>
<pre>{report_json}</pre>

</body>
</html>
"""
    return html
