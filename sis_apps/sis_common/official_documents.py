"""Helpers for rendering and accessing institutional documents."""

from functools import wraps

from django.http import HttpResponse
from django.utils.html import escape
from rest_framework.permissions import IsAuthenticated

from sis_common.authorization import filter_queryset_by_scopes, request_has_business_access
from sis_common.workflow_tracking import record_workflow_event


class DocumentTenantPermission(IsAuthenticated):
    message = "Les documents sont réservés aux comptes actifs de cet établissement."

    def has_permission(self, request, view):
        tenant = getattr(request, "tenant", None)
        return (
            super().has_permission(request, view)
            and request.user.is_active
            and tenant is not None
            and request.user.etablissement_id == tenant.pk
            and (
                request.method in ("GET", "HEAD", "OPTIONS")
                or request.user.is_superuser
                or request.user.role not in ("eleve", "etudiant", "doctorant", "parent")
            )
        )


def scope_student_documents(view, queryset, approved, scopes):
    request = view.request
    user = request.user
    queryset = queryset.filter(etudiant__universite_id=request.tenant.pk)
    if user.role in ("etudiant", "doctorant") and not user.is_superuser:
        return queryset.filter(etudiant__user=user, **approved)
    if user.role == "parent" and not user.is_superuser:
        return queryset.none()
    permission = view.required_change_permission
    if request.method in ("GET", "HEAD", "OPTIONS"):
        permission = permission.replace(".change_", ".view_")
    if not (
        user.has_perm(permission)
        or request_has_business_access(
            request,
            permission,
            ("president", "vice_president", "doyen", "vice_doyen", "directeur_etudes", "scolarite", "chef_departement"),
            tenant_group_codes=("academic_registry_superieur", "document_signatory_superieur"),
        )
    ):
        return queryset.none()
    return filter_queryset_by_scopes(queryset, user, permission, {"etudiants": "etudiant_id", **scopes})


def private_document_download(method):
    @wraps(method)
    def wrapped(view, request, *args, **kwargs):
        document = view.get_object()
        response = method(view, request, *args, **kwargs)
        if response.status_code == 200:
            record_workflow_event(
                request, document, "telechargement", "Document téléchargé", metadata={"format": "pdf"}
            )
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response

    wrapped.render_document = method
    return wrapped


def tenant_identity_rows(request, document_label, serial=None, issue_date=None):
    """Build standard institutional rows for official documents."""

    tenant = getattr(request, "tenant", None)
    rows = [
        ("Établissement", getattr(tenant, "nom", "")),
        (
            "Type d'établissement",
            (
                tenant.get_type_display()
                if tenant and hasattr(tenant, "get_type_display")
                else getattr(tenant, "type", "")
            ),
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

    footer_rows = [
        *(footer_rows or []),
        ("Authentification", "Copie générée à la demande. Aucune signature cryptographique embarquée."),
    ]
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
        sections_html_parts.append(f"""
        <section>
          <h2>{section_title}</h2>
          <table>{section_rows}</table>
        </section>
        """)
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
    HTML(string=html).write_pdf(response, presentational_hints=False)
    return response
