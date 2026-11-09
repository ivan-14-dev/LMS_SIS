"""Country-independent transitions for an existing annual enrollment."""

TRANSITIONS = {
    "suspendre": {"validee": "suspendue"},
    "abandonner": {"validee": "abandonnee", "suspendue": "abandonnee"},
    "reprendre": {"suspendue": "validee"},
}


def transition_status(current, operation):
    destination = TRANSITIONS.get(operation, {}).get(current)
    if destination is None:
        raise ValueError("Cette transition n'est pas autorisée depuis l'état actuel de l'inscription.")
    return destination


def validate_enrollment_dates(start, end, today, *, ongoing=False):
    if today > end:
        raise ValueError("L'année est terminée. Créez une réinscription pour une année ouverte.")
    if ongoing and today < start:
        raise ValueError("L'année n'a pas encore commencé.")
