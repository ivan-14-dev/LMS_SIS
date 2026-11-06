"""Vérification des chevauchements entre créneaux et indisponibilités."""

from datetime import timedelta

from .models import IndisponibiliteSalle


def creneau_recoupe_periode(creneau, debut, fin):
    """Un créneau ponctuel ou hebdomadaire tombe-t-il dans ces jours inclusifs ?"""
    if creneau.date_specifique:
        return debut <= creneau.date_specifique <= fin

    annee = creneau.classe.annee_scolaire
    debut = max(debut, annee.date_debut)
    fin = min(fin, annee.date_fin)
    if debut > fin:
        return False
    premier_jour = debut + timedelta(days=(creneau.jour - debut.isoweekday()) % 7)
    # Le repère des semaines alternées n'est pas daté : ne pas considérer
    # arbitrairement une semaine 1 ou 2 comme disponible.
    return premier_jour <= fin


def salle_indisponible_pour_creneau(creneau):
    if not creneau.actif or not creneau.salle_id:
        return False
    periodes = IndisponibiliteSalle.objects.filter(salle_id=creneau.salle_id)
    if creneau.date_specifique:
        periodes = periodes.filter(
            date_debut__lte=creneau.date_specifique,
            date_fin__gte=creneau.date_specifique,
        )
    else:
        annee = creneau.classe.annee_scolaire
        periodes = periodes.filter(
            date_debut__lte=annee.date_fin, date_fin__gte=annee.date_debut
        )
    return any(
        creneau_recoupe_periode(creneau, periode.date_debut, periode.date_fin)
        for periode in periodes
    )


def periode_recoupe_creneau(salle, debut, fin):
    from apps.emplois_du_temps.models import Creneau

    creneaux = Creneau.objects.filter(
        salle=salle, actif=True
    ).select_related("classe__annee_scolaire")
    return any(
        creneau_recoupe_periode(creneau, debut, fin) for creneau in creneaux
    )
