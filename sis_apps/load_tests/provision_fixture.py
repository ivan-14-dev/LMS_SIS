"""Provision ONLY the explicitly named disposable SIS load-test database.

Run inside the new, resource-limited fixture API container after shared migrations.
No application setting, password hasher, permission or throttle is overridden.
"""

import json
import os
import secrets
from datetime import date, timedelta
from pathlib import Path

FIXTURE = "sis-load-d0c25c75"
SCHEMA = "load_d0c25c75"


def protected_json(path, value):
    with path.open("x", encoding="utf-8") as stream:
        os.chmod(path, 0o600)
        json.dump(value, stream, indent=2)
        stream.write("\n")


def main():
    if (
        os.environ.get("SIS_LOAD_FIXTURE") != FIXTURE
        or os.environ.get("DB_HOST") != FIXTURE + "-postgres"
        or os.environ.get("DB_NAME") != "sis_load_d0c25c75"
        or os.environ.get("DJANGO_ALLOWED_HOSTS") != "load-secondaire.localhost"
    ):
        raise SystemExit("Refused: this provisioner is restricted to the named disposable fixture.")
    import django

    django.setup()

    from apps.classes.models import Classe, Matiere, ProgrammeMatiere
    from apps.core.models import Reclamation, ReclamationEntry
    from apps.eleves.models import Eleve, Inscription
    from apps.enseignants.models import AffectationEnseignant, MatiereEnseignee, Personnel
    from apps.etablissement.models import AnneeScolaire, Domain, Etablissement, Niveau, Periode
    from apps.notes.models import Evaluation, Note
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from django.contrib.auth.hashers import identify_hasher
    from django.contrib.auth.password_validation import validate_password
    from django.db import connection, transaction
    from django_tenants.utils import tenant_context

    if settings.DEBUG or settings.PASSWORD_HASHERS[0] != "django.contrib.auth.hashers.Argon2PasswordHasher":
        raise SystemExit("Refused: normal production security and Argon2 must remain enabled.")
    if settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] != {"anon": "10/minute", "user": "100/minute"}:
        raise SystemExit("Refused: default throttles must remain unchanged.")
    output = Path(os.environ["SIS_LOAD_ARTIFACTS"])
    if (output / "seed-500.json").exists() or Etablissement.objects.exists():
        raise SystemExit("Refused: provision only a new empty fixture, never overwrite a tenant or seed.")
    seed = json.loads(Path("/app/load_tests/seed.example.json").read_text())
    seed["environment"] = {
        "id": FIXTURE, "origin": os.environ["SIS_LOAD_ORIGIN"], "isolated": True, "synthetic": True,
    }
    seed["accounts"] = []
    tenant = Etablissement.objects.create(
        schema_name=SCHEMA, nom="Fixture synthétique 500 sessions", type="college",
        adresse="Aucune adresse réelle", code_postal="00000", ville="Synthétique",
        telephone="0000000000", email="fixture@example.invalid",
    )
    Domain.objects.create(domain="load-secondaire.localhost", tenant=tenant, is_primary=True)
    today = date.today()
    user_model = get_user_model()
    with tenant_context(tenant), transaction.atomic():
        year = AnneeScolaire.objects.create(
            etablissement=tenant, libelle="Qualification synthétique",
            date_debut=today - timedelta(days=30), date_fin=today + timedelta(days=330), en_cours=True,
        )
        period = Periode.objects.create(
            annee_scolaire=year, type="trimestre", numero=1, libelle="Qualification",
            date_debut=today - timedelta(days=15), date_fin=today + timedelta(days=90),
        )
        level = Niveau.objects.create(etablissement=tenant, code="6e", libelle="Sixième", ordre=1)
        subject = Matiere.objects.create(etablissement=tenant, code="SYNTH", nom="Matière synthétique")
        groups = [
            Classe.objects.create(
                etablissement=tenant, annee_scolaire=year, niveau=level, nom=f"SYNTH-{index + 1}",
                effectif_max=30,
            )
            for index in range(10)
        ]
        programs = {
            group.pk: ProgrammeMatiere.objects.create(classe=group, matiere=subject, coefficient=1)
            for group in groups
        }
        learners, teachers, staff = [], [], []
        for index in range(500):
            role = "eleve" if index < 300 else "enseignant" if index < 450 else "direction"
            password = secrets.token_urlsafe(24)
            username = f"synthetic-{role}-{index + 1:04}"
            user = user_model(
                username=username, email=f"{username}@example.invalid", role=role,
                etablissement=tenant, first_name="Synthétique", last_name=f"{index + 1:04}",
                is_active=True, is_staff=False, is_superuser=False,
            )
            validate_password(password, user)
            user.set_password(password)
            user.save()
            if identify_hasher(user.password).algorithm != "argon2":
                raise RuntimeError("Unexpected password hasher.")
            account = {
                "synthetic": True, "username": username, "password": password, "user_id": user.pk,
                "tenant_id": tenant.pk, "role": role, "variables": {}, "owned_resources": [],
            }
            if role == "eleve":
                group = groups[index % len(groups)]
                learner = Eleve.objects.create(
                    etablissement=tenant, user=user, matricule=f"SYNTH-E-{index + 1:04}",
                    date_naissance=date(2012, 1, 1), lieu_naissance="Synthétique", sexe="F",
                    classe_actuelle=group, date_inscription=today,
                )
                Inscription.objects.create(
                    eleve=learner, classe=group, annee_scolaire=year,
                    date_inscription=today, statut="validee",
                )
                complaint = Reclamation.objects.create(
                    etablissement=tenant, demandeur=user, categorie="autre",
                    objet=f"Qualification synthétique {index + 1:04}",
                    description="Dossier jetable sans données personnelles.",
                )
                ReclamationEntry.objects.create(
                    reclamation=complaint, auteur=user, action="depot",
                    message="Fixture synthétique initiale.", statut="soumise",
                )
                account.update(
                    scenario="learner-complaint",
                    variables={"complaint_id": str(complaint.pk)},
                    owned_resources=["/api/v1/core/reclamations/{{complaint_id}}/"],
                )
                learners.append(learner)
            else:
                personnel = Personnel.objects.create(
                    user=user, matricule=f"SYNTH-P-{index + 1:04}", date_embauche=today,
                )
                (teachers if role == "enseignant" else staff).append((user, personnel, account))
                account.update(scenario="grade-feedback", owned_resources=["/api/v1/notes/notes/{{note_id}}/"])
            seed["accounts"].append(account)
            if (index + 1) % 100 == 0:
                print(json.dumps({"synthetic_accounts_hashed": index + 1}), flush=True)
        for index, (user, personnel, account) in enumerate(teachers):
            learner = learners[index]
            group = learner.classe_actuelle
            MatiereEnseignee.objects.create(enseignant=personnel, matiere=subject)
            assignment = AffectationEnseignant.objects.create(
                enseignant=personnel, matiere=subject, annee_scolaire=year, heures_semaine=1,
            )
            assignment.classes.add(group)
            program = programs[group.pk]
            program.enseignants.add(user)
            if program.enseignant_principal_id is None:
                program.enseignant_principal = user
                program.save(update_fields=["enseignant_principal"])
            evaluation = Evaluation.objects.create(
                matiere=subject, classe=group, type="ds", titre=f"Synthétique enseignant {index + 1}",
                date=today, periode=period, enseignant=personnel,
            )
            note = Note.objects.create(evaluation=evaluation, eleve=learner, valeur=12, saisi_par=personnel)
            account["variables"]["note_id"] = note.pk
        for index, (_, _, account) in enumerate(staff):
            learner = learners[index + 150]
            teacher = teachers[index]
            evaluation = Evaluation.objects.create(
                matiere=subject, classe=learner.classe_actuelle, type="ds",
                titre=f"Synthétique direction {index + 1}", date=today, periode=period,
                enseignant=teacher[1],
            )
            note = Note.objects.create(evaluation=evaluation, eleve=learner, valeur=12, saisi_par=teacher[1])
            account["variables"]["note_id"] = note.pk
        counts = {
            "users": user_model.objects.filter(username__startswith="synthetic-", etablissement=tenant).count(),
            "total_local_accounts": user_model.objects.count(),
            "argon2_users": user_model.objects.filter(password__startswith="argon2$").count(),
            "learners": Eleve.objects.count(), "enrollments": Inscription.objects.count(),
            "teachers": len(teachers), "staff": len(staff), "teacher_assignments": AffectationEnseignant.objects.count(),
            "classes": Classe.objects.count(), "evaluations": Evaluation.objects.count(),
            "notes": Note.objects.count(), "complaints": Reclamation.objects.count(),
            "schema": connection.schema_name,
        }
        if counts["users"] != 500 or counts["enrollments"] != 300 or counts["notes"] != 200:
            raise RuntimeError("Synthetic fixture integrity check failed: " + json.dumps(counts))
    from load_tests.sessions import validate_seed

    validate_seed(seed, 500)
    protected_json(output / "seed-500.json", seed)
    smoke = {**seed, "accounts": [seed["accounts"][0], seed["accounts"][300]]}
    validate_seed(smoke, 2)
    protected_json(output / "seed-smoke-2.json", smoke)
    protected_json(output / "fixture-counts.json", counts)
    print(json.dumps({"fixture_ready": True, **counts}), flush=True)


if __name__ == "__main__":
    main()
