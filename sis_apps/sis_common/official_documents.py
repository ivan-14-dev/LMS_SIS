"""Helpers for rendering official institutional PDFs."""

from django.http import HttpResponse
from django.utils.html import escape


def tenant_identity_rows(request, document_label, serial=None, issue_date=None):
    """Build standard institutional rows for official documents."""

    tenant = getattr(request, "tenant", None)
    rows = [
        ("Établissement", getattr(tenant, "nom", "")),
        (
            "Type d'établissement",
            tenant.get_type_display() if tenant and hasattr(tenant, "get_type_display") else getattr(tenant, "type", ""),
        ),
        ("Document", document_label),
        ("Numéro / série", serial or ""),
        ("Date d'émission", issue_date or ""),
    ]
    return [(label, value) for label, value in rows if value not in (None, "")]


def render_official_pdf(filename, title, identity_rows, sections, footer_rows=None):
    """Render a simple official PDF document with institutional metadata."""

    try:
        from weasyprint import HTML
    except ImportError as exc:
        from rest_framework.exceptions import ValidationError

        raise ValidationError({"format": "Le support PDF n'est pas disponible."}) from exc

    footer_rows = footer_rows or []
    identity_html = "".join(
        f"<tr><th>{escape(str(label))}</th><td>{escape(str(value))}</td></tr>"
        for label, value in identity_rows
        if value not in (None, "")
    )
    sections_html_parts = []
    for section in sections:
        section_title = escape(str(section["title"]))
        section_rows = "".join(
            f"<tr><th>{escape(str(label))}</th><td>{escape(str(value))}</td></tr>"
            for label, value in section.get("rows", [])
            if value not in (None, "")
        )
        sections_html_parts.append(
            f"""
        <section>
          <h2>{section_title}</h2>
          <table>{section_rows}</table>
        </section>
        """
        )
    sections_html = "".join(sections_html_parts)
    footer_html = "".join(
        f"<li><strong>{escape(str(label))}:</strong> {escape(str(value))}</li>"
        for label, value in footer_rows
        if value not in (None, "")
    )
    html = f"""
    <html>
      <head>
        <meta charset="utf-8" />
        <style>
          body {{ font-family: sans-serif; color: #1f2933; font-size: 12px; margin: 24px; }}
          header {{ border-bottom: 2px solid #d9e2ec; margin-bottom: 18px; padding-bottom: 12px; }}
          h1 {{ margin: 0 0 8px; font-size: 20px; }}
          h2 {{ margin: 18px 0 8px; font-size: 15px; }}
          table {{ width: 100%; border-collapse: collapse; margin-bottom: 12px; }}
          th, td {{ border: 1px solid #d9e2ec; padding: 6px 8px; text-align: left; vertical-align: top; }}
          th {{ background: #f5f7fa; width: 32%; }}
          footer {{ margin-top: 18px; font-size: 11px; color: #52606d; }}
          ul {{ margin: 8px 0 0 16px; padding: 0; }}
        </style>
      </head>
      <body>
        <header>
          <h1>{escape(str(title))}</h1>
          <table>{identity_html}</table>
        </header>
        {sections_html}
        <footer><ul>{footer_html}</ul></footer>
      </body>
    </html>
    """
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    HTML(string=html).write_pdf(response)
    return response
