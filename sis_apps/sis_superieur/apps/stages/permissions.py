"""Permissions for stages."""


def can_manage_stage_applications(user):
    return user.is_staff or getattr(user, "role", "") in (
        "relations_entreprises",
        "scolarite",
        "responsable_formation",
        "doyen",
    )


def is_stage_applicant(user):
    return getattr(user, "role", "") in ("etudiant", "doctorant") and hasattr(
        user, "etudiant_profile"
    )
