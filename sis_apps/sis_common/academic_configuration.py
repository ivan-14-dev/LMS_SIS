"""Validation helpers for tenant-defined academic structures and rules."""

import re
from copy import deepcopy
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError

DIMENSION_AXES = {
    "institutional": "Institutionnel",
    "academic": "Académique",
    "organizational": "Organisationnel",
    "pedagogical": "Pédagogique",
    "financial": "Financier",
}

DIMENSION_SCOPES = {
    "tenant": "Établissement",
    "academic_year": "Année académique",
    "period": "Période",
    "semester": "Semestre",
    "level": "Niveau",
    "class": "Classe",
    "department": "Département",
    "program": "Filière / formation",
    "section": "Section / parcours",
    "subject": "Matière / ECUE",
    "unit": "UE / unité d'enseignement",
    "payment": "Rubrique de paiement",
}

VALIDATION_POLICY_SCOPES = {
    "tenant": "Établissement",
    "academic_year": "Année académique",
    "level": "Niveau",
    "class": "Classe",
    "formation": "Formation",
    "semester": "Semestre",
}

REPORT_EXPORT_FORMATS = {
    "csv": "CSV",
    "xlsx": "Excel (.xlsx)",
    "pdf": "PDF",
}

IMPORT_TEMPLATE_TYPES = {
    "continuous_assessment_grades": "Notes de contrôle continu",
    "exam_grades": "Notes d'épreuves / examens",
    "final_results": "Résultats finaux",
}

EXAM_RESULT_WORKFLOW_SCOPES = {
    "tenant": "Établissement",
    "academic_year": "Année académique",
    "session": "Session d'examen",
}

SUBMISSION_WINDOW_TYPES = {
    "evaluation": "Évaluations / sujets",
    "exam": "Examens / résultats",
}

SECONDARY_USER_ROLES = {
    "super_admin": "Super administrateur",
    "direction": "Direction",
    "responsable_pedagogique": "Responsable pédagogique",
    "enseignant": "Enseignant",
    "personnel_administratif": "Personnel administratif",
    "comptable": "Comptable",
    "bibliothecaire": "Bibliothécaire",
    "infirmier": "Infirmier",
    "surveillant": "Surveillant",
    "vie_scolaire": "Vie scolaire",
    "eleve": "Élève",
    "parent": "Parent",
}

SUPERIOR_USER_ROLES = {
    "super_admin": "Super administrateur",
    "president": "Président d'université",
    "vice_president": "Vice-président",
    "doyen": "Doyen de faculté",
    "directeur_dept": "Directeur de département",
    "responsable_formation": "Responsable de formation",
    "directeur_etudes": "Directeur des études",
    "enseignant": "Enseignant",
    "chercheur": "Chercheur",
    "personnel_administratif": "Personnel administratif",
    "scolarite": "Service scolarité",
    "service_social": "Service social",
    "service_ri": "Service relations internationales",
    "bibliothecaire": "Bibliothécaire",
    "comptable": "Comptable",
    "etudiant": "Étudiant",
    "doctorant": "Doctorant",
    "parent": "Parent",
}

REPORT_DATASET_SCHEMAS = {
    "notes": {
        "label": "Notes",
        "variants": {
            "secondaire": {
                "fields": [
                    {"code": "matricule", "label": "Matricule"},
                    {"code": "eleve", "label": "Élève"},
                    {"code": "classe", "label": "Classe"},
                    {"code": "matiere", "label": "Matière"},
                    {"code": "evaluation", "label": "Évaluation"},
                    {"code": "note", "label": "Note"},
                    {"code": "bareme", "label": "Barème"},
                    {"code": "appreciation", "label": "Appréciation"},
                    {"code": "enseignant", "label": "Enseignant"},
                    {"code": "periode", "label": "Période"},
                    {"code": "date", "label": "Date"},
                    {"code": "eleve_cible", "label": "Élève ciblé"},
                ],
                "allowed_filters": [
                    {"code": "annee", "label": "Année scolaire"},
                    {"code": "classe", "label": "Classe"},
                    {"code": "matiere", "label": "Matière"},
                    {"code": "enseignant", "label": "Enseignant"},
                    {"code": "periode", "label": "Période"},
                    {"code": "statut", "label": "Statut"},
                ],
                "group_by_options": [
                    {"code": "classe", "label": "Classe"},
                    {"code": "matiere", "label": "Matière"},
                    {"code": "enseignant", "label": "Enseignant"},
                    {"code": "periode", "label": "Période"},
                ],
            },
            "superieur": {
                "fields": [
                    {"code": "matricule", "label": "Matricule"},
                    {"code": "etudiant", "label": "Étudiant"},
                    {"code": "formation", "label": "Formation"},
                    {"code": "ecue", "label": "ECUE"},
                    {"code": "ue", "label": "UE"},
                    {"code": "evaluation", "label": "Évaluation"},
                    {"code": "note", "label": "Note"},
                    {"code": "bareme", "label": "Barème"},
                    {"code": "appreciation", "label": "Appréciation"},
                    {"code": "enseignant", "label": "Enseignant"},
                    {"code": "semestre", "label": "Semestre"},
                    {"code": "date", "label": "Date"},
                    {"code": "parcours_individualise", "label": "Parcours individualisé"},
                ],
                "allowed_filters": [
                    {"code": "annee", "label": "Année universitaire"},
                    {"code": "formation", "label": "Formation"},
                    {"code": "ecue", "label": "ECUE"},
                    {"code": "ue", "label": "UE"},
                    {"code": "enseignant", "label": "Enseignant"},
                    {"code": "semestre", "label": "Semestre"},
                    {"code": "statut", "label": "Statut"},
                ],
                "group_by_options": [
                    {"code": "formation", "label": "Formation"},
                    {"code": "ecue", "label": "ECUE"},
                    {"code": "ue", "label": "UE"},
                    {"code": "enseignant", "label": "Enseignant"},
                    {"code": "semestre", "label": "Semestre"},
                ],
            },
        },
    },
    "evaluations": {
        "label": "Évaluations",
        "variants": {
            "secondaire": {
                "fields": [
                    {"code": "titre", "label": "Titre"},
                    {"code": "type", "label": "Type"},
                    {"code": "classe", "label": "Classe"},
                    {"code": "matiere", "label": "Matière"},
                    {"code": "periode", "label": "Période"},
                    {"code": "enseignant", "label": "Enseignant"},
                    {"code": "date", "label": "Date"},
                    {"code": "bareme", "label": "Barème"},
                    {"code": "coefficient", "label": "Coefficient"},
                    {"code": "ponderation", "label": "Pondération"},
                    {"code": "eleve_cible", "label": "Élève ciblé"},
                ],
                "allowed_filters": [
                    {"code": "classe", "label": "Classe"},
                    {"code": "matiere", "label": "Matière"},
                    {"code": "periode", "label": "Période"},
                    {"code": "type", "label": "Type"},
                    {"code": "enseignant", "label": "Enseignant"},
                    {"code": "eleve_cible", "label": "Élève ciblé"},
                ],
                "group_by_options": [
                    {"code": "classe", "label": "Classe"},
                    {"code": "matiere", "label": "Matière"},
                    {"code": "periode", "label": "Période"},
                    {"code": "enseignant", "label": "Enseignant"},
                    {"code": "type", "label": "Type"},
                ],
            },
            "superieur": {
                "fields": [
                    {"code": "titre", "label": "Titre"},
                    {"code": "modalite", "label": "Modalité"},
                    {"code": "ecue", "label": "ECUE"},
                    {"code": "ue", "label": "UE"},
                    {"code": "formation", "label": "Formation"},
                    {"code": "semestre", "label": "Semestre"},
                    {"code": "enseignant", "label": "Enseignant"},
                    {"code": "date", "label": "Date"},
                    {"code": "bareme", "label": "Barème"},
                    {"code": "coefficient", "label": "Coefficient"},
                    {"code": "ponderation", "label": "Pondération"},
                    {"code": "anonyme", "label": "Anonyme"},
                ],
                "allowed_filters": [
                    {"code": "ecue", "label": "ECUE"},
                    {"code": "ue", "label": "UE"},
                    {"code": "semestre", "label": "Semestre"},
                    {"code": "formation", "label": "Formation"},
                    {"code": "modalite", "label": "Modalité"},
                    {"code": "enseignant", "label": "Enseignant"},
                    {"code": "anonyme", "label": "Anonyme"},
                ],
                "group_by_options": [
                    {"code": "formation", "label": "Formation"},
                    {"code": "ecue", "label": "ECUE"},
                    {"code": "ue", "label": "UE"},
                    {"code": "semestre", "label": "Semestre"},
                    {"code": "enseignant", "label": "Enseignant"},
                    {"code": "modalite", "label": "Modalité"},
                ],
            },
        },
    },
    "bulletins": {
        "label": "Bulletins",
        "variants": {
            "secondaire": {
                "fields": [
                    {"code": "matricule", "label": "Matricule"},
                    {"code": "eleve", "label": "Élève"},
                    {"code": "classe", "label": "Classe"},
                    {"code": "periode", "label": "Période"},
                    {"code": "moyenne_generale", "label": "Moyenne générale"},
                    {"code": "rang", "label": "Rang"},
                    {"code": "effectif_classe", "label": "Effectif classe"},
                    {"code": "decision", "label": "Décision"},
                    {"code": "publie", "label": "Publié"},
                    {"code": "signe", "label": "Signé"},
                    {"code": "nb_matieres_individualisees", "label": "Nb matières individualisées"},
                ],
                "allowed_filters": [
                    {"code": "eleve", "label": "Élève"},
                    {"code": "classe", "label": "Classe"},
                    {"code": "periode", "label": "Période"},
                    {"code": "publie", "label": "Publié"},
                ],
                "group_by_options": [
                    {"code": "classe", "label": "Classe"},
                    {"code": "periode", "label": "Période"},
                    {"code": "publie", "label": "Publié"},
                    {"code": "signe", "label": "Signé"},
                ],
            },
        },
    },
    "financial_invoices": {
        "label": "Factures",
        "variants": {
            "secondaire": {
                "fields": [
                    {"code": "numero", "label": "Numéro"},
                    {"code": "eleve", "label": "Élève"},
                    {"code": "matricule", "label": "Matricule"},
                    {"code": "rubrique", "label": "Rubrique"},
                    {"code": "annee", "label": "Année"},
                    {"code": "montant", "label": "Montant"},
                    {"code": "montant_paye", "label": "Montant payé"},
                    {"code": "statut", "label": "Statut"},
                    {"code": "date_emission", "label": "Date émission"},
                    {"code": "date_echeance", "label": "Date échéance"},
                ],
                "allowed_filters": [
                    {"code": "annee", "label": "Année scolaire"},
                    {"code": "eleve", "label": "Élève"},
                    {"code": "rubrique", "label": "Rubrique"},
                    {"code": "statut", "label": "Statut"},
                ],
                "group_by_options": [
                    {"code": "annee", "label": "Année scolaire"},
                    {"code": "rubrique", "label": "Rubrique"},
                    {"code": "statut", "label": "Statut"},
                ],
            },
            "superieur": {
                "fields": [
                    {"code": "numero", "label": "Numéro"},
                    {"code": "etudiant", "label": "Étudiant"},
                    {"code": "matricule", "label": "Matricule"},
                    {"code": "rubrique", "label": "Rubrique"},
                    {"code": "annee", "label": "Année"},
                    {"code": "montant", "label": "Montant"},
                    {"code": "montant_paye", "label": "Montant payé"},
                    {"code": "statut", "label": "Statut"},
                    {"code": "date_emission", "label": "Date émission"},
                    {"code": "date_echeance", "label": "Date échéance"},
                ],
                "allowed_filters": [
                    {"code": "annee", "label": "Année universitaire"},
                    {"code": "etudiant", "label": "Étudiant"},
                    {"code": "rubrique", "label": "Rubrique"},
                    {"code": "statut", "label": "Statut"},
                ],
                "group_by_options": [
                    {"code": "annee", "label": "Année universitaire"},
                    {"code": "rubrique", "label": "Rubrique"},
                    {"code": "statut", "label": "Statut"},
                ],
            },
        },
    },
    "financial_payments": {
        "label": "Paiements",
        "variants": {
            "secondaire": {
                "fields": [
                    {"code": "numero", "label": "Numéro"},
                    {"code": "eleve", "label": "Élève"},
                    {"code": "matricule", "label": "Matricule"},
                    {"code": "facture", "label": "Facture"},
                    {"code": "rubrique", "label": "Rubrique"},
                    {"code": "annee", "label": "Année"},
                    {"code": "mode", "label": "Mode"},
                    {"code": "montant", "label": "Montant"},
                    {"code": "statut", "label": "Statut"},
                    {"code": "date_paiement", "label": "Date de paiement"},
                ],
                "allowed_filters": [
                    {"code": "annee", "label": "Année scolaire"},
                    {"code": "rubrique", "label": "Rubrique"},
                    {"code": "facture", "label": "Facture"},
                    {"code": "mode", "label": "Mode"},
                    {"code": "statut", "label": "Statut"},
                ],
                "group_by_options": [
                    {"code": "annee", "label": "Année scolaire"},
                    {"code": "rubrique", "label": "Rubrique"},
                    {"code": "mode", "label": "Mode"},
                    {"code": "statut", "label": "Statut"},
                ],
            },
            "superieur": {
                "fields": [
                    {"code": "numero", "label": "Numéro"},
                    {"code": "etudiant", "label": "Étudiant"},
                    {"code": "matricule", "label": "Matricule"},
                    {"code": "facture", "label": "Facture"},
                    {"code": "rubrique", "label": "Rubrique"},
                    {"code": "annee", "label": "Année"},
                    {"code": "mode", "label": "Mode"},
                    {"code": "montant", "label": "Montant"},
                    {"code": "statut", "label": "Statut"},
                    {"code": "date_paiement", "label": "Date de paiement"},
                ],
                "allowed_filters": [
                    {"code": "annee", "label": "Année universitaire"},
                    {"code": "rubrique", "label": "Rubrique"},
                    {"code": "facture", "label": "Facture"},
                    {"code": "mode", "label": "Mode"},
                    {"code": "statut", "label": "Statut"},
                ],
                "group_by_options": [
                    {"code": "annee", "label": "Année universitaire"},
                    {"code": "rubrique", "label": "Rubrique"},
                    {"code": "mode", "label": "Mode"},
                    {"code": "statut", "label": "Statut"},
                ],
            },
        },
    },
    "averages_ecue": {
        "label": "Moyennes ECUE",
        "variants": {
            "superieur": {
                "fields": [
                    {"code": "matricule", "label": "Matricule"},
                    {"code": "etudiant", "label": "Étudiant"},
                    {"code": "formation", "label": "Formation"},
                    {"code": "ecue", "label": "ECUE"},
                    {"code": "ue", "label": "UE"},
                    {"code": "semestre", "label": "Semestre"},
                    {"code": "moyenne", "label": "Moyenne"},
                    {"code": "valide", "label": "Validé"},
                    {"code": "parcours_individualise", "label": "Parcours individualisé"},
                ],
                "allowed_filters": [
                    {"code": "etudiant", "label": "Étudiant"},
                    {"code": "formation", "label": "Formation"},
                    {"code": "ecue", "label": "ECUE"},
                    {"code": "ue", "label": "UE"},
                    {"code": "semestre", "label": "Semestre"},
                    {"code": "valide", "label": "Validé"},
                ],
                "group_by_options": [
                    {"code": "formation", "label": "Formation"},
                    {"code": "ecue", "label": "ECUE"},
                    {"code": "ue", "label": "UE"},
                    {"code": "semestre", "label": "Semestre"},
                    {"code": "valide", "label": "Validé"},
                ],
            },
        },
    },
    "averages_ue": {
        "label": "Moyennes UE",
        "variants": {
            "superieur": {
                "fields": [
                    {"code": "matricule", "label": "Matricule"},
                    {"code": "etudiant", "label": "Étudiant"},
                    {"code": "formation", "label": "Formation"},
                    {"code": "ue", "label": "UE"},
                    {"code": "semestre", "label": "Semestre"},
                    {"code": "moyenne", "label": "Moyenne"},
                    {"code": "credits_obtenus", "label": "Crédits obtenus"},
                    {"code": "capitalisee", "label": "Capitalisée"},
                    {"code": "parcours_individualise", "label": "Parcours individualisé"},
                ],
                "allowed_filters": [
                    {"code": "etudiant", "label": "Étudiant"},
                    {"code": "formation", "label": "Formation"},
                    {"code": "ue", "label": "UE"},
                    {"code": "semestre", "label": "Semestre"},
                    {"code": "capitalisee", "label": "Capitalisée"},
                ],
                "group_by_options": [
                    {"code": "formation", "label": "Formation"},
                    {"code": "ue", "label": "UE"},
                    {"code": "semestre", "label": "Semestre"},
                    {"code": "capitalisee", "label": "Capitalisée"},
                ],
            },
        },
    },
    "exam_results": {
        "label": "Résultats d'examen",
        "variants": {
            "secondaire": {
                "fields": [
                    {"code": "session", "label": "Session"},
                    {"code": "matiere", "label": "Matière"},
                    {"code": "classe", "label": "Classe"},
                    {"code": "matricule", "label": "Matricule"},
                    {"code": "eleve", "label": "Élève"},
                    {"code": "note", "label": "Note"},
                    {"code": "appreciation", "label": "Appréciation"},
                    {"code": "statut", "label": "Statut"},
                    {"code": "type_resultat", "label": "Type de résultat"},
                    {"code": "admis", "label": "Admis"},
                    {"code": "mention", "label": "Mention"},
                    {"code": "publie_le", "label": "Publié le"},
                ],
                "allowed_filters": [
                    {"code": "annee", "label": "Année scolaire"},
                    {"code": "session", "label": "Session"},
                    {"code": "classe", "label": "Classe"},
                    {"code": "matiere", "label": "Matière"},
                    {"code": "statut", "label": "Statut"},
                    {"code": "type_resultat", "label": "Type de résultat"},
                ],
                "group_by_options": [
                    {"code": "session", "label": "Session"},
                    {"code": "classe", "label": "Classe"},
                    {"code": "matiere", "label": "Matière"},
                    {"code": "statut", "label": "Statut"},
                    {"code": "type_resultat", "label": "Type de résultat"},
                ],
            },
            "superieur": {
                "fields": [
                    {"code": "session", "label": "Session"},
                    {"code": "formation", "label": "Formation"},
                    {"code": "semestre", "label": "Semestre"},
                    {"code": "ue", "label": "UE"},
                    {"code": "ecue", "label": "ECUE"},
                    {"code": "matricule", "label": "Matricule"},
                    {"code": "etudiant", "label": "Étudiant"},
                    {"code": "note", "label": "Note"},
                    {"code": "appreciation", "label": "Appréciation"},
                    {"code": "statut", "label": "Statut"},
                    {"code": "type_resultat", "label": "Type de résultat"},
                    {"code": "admis", "label": "Admis"},
                    {"code": "mention", "label": "Mention"},
                    {"code": "publie_le", "label": "Publié le"},
                ],
                "allowed_filters": [
                    {"code": "annee", "label": "Année universitaire"},
                    {"code": "session", "label": "Session"},
                    {"code": "formation", "label": "Formation"},
                    {"code": "semestre", "label": "Semestre"},
                    {"code": "ue", "label": "UE"},
                    {"code": "ecue", "label": "ECUE"},
                    {"code": "statut", "label": "Statut"},
                    {"code": "type_resultat", "label": "Type de résultat"},
                ],
                "group_by_options": [
                    {"code": "session", "label": "Session"},
                    {"code": "formation", "label": "Formation"},
                    {"code": "semestre", "label": "Semestre"},
                    {"code": "ue", "label": "UE"},
                    {"code": "ecue", "label": "ECUE"},
                    {"code": "statut", "label": "Statut"},
                    {"code": "type_resultat", "label": "Type de résultat"},
                ],
            },
        },
    },
    "workflow_events": {
        "label": "Historique workflows",
        "variants": {
            "secondaire": {
                "fields": [
                    {"code": "action", "label": "Action"},
                    {"code": "title", "label": "Titre"},
                    {"code": "app_label", "label": "Module"},
                    {"code": "model", "label": "Modèle"},
                    {"code": "object_repr", "label": "Objet"},
                    {"code": "actor", "label": "Acteur"},
                    {"code": "tenant_id", "label": "Tenant"},
                    {"code": "request_id", "label": "Requête"},
                    {"code": "created_at", "label": "Date"},
                ],
                "allowed_filters": [
                    {"code": "action", "label": "Action"},
                    {"code": "app_label", "label": "Module"},
                    {"code": "model", "label": "Modèle"},
                ],
                "group_by_options": [
                    {"code": "action", "label": "Action"},
                    {"code": "app_label", "label": "Module"},
                    {"code": "model", "label": "Modèle"},
                ],
            },
            "superieur": {
                "fields": [
                    {"code": "action", "label": "Action"},
                    {"code": "title", "label": "Titre"},
                    {"code": "app_label", "label": "Module"},
                    {"code": "model", "label": "Modèle"},
                    {"code": "object_repr", "label": "Objet"},
                    {"code": "actor", "label": "Acteur"},
                    {"code": "tenant_id", "label": "Tenant"},
                    {"code": "request_id", "label": "Requête"},
                    {"code": "created_at", "label": "Date"},
                ],
                "allowed_filters": [
                    {"code": "action", "label": "Action"},
                    {"code": "app_label", "label": "Module"},
                    {"code": "model", "label": "Modèle"},
                ],
                "group_by_options": [
                    {"code": "action", "label": "Action"},
                    {"code": "app_label", "label": "Module"},
                    {"code": "model", "label": "Modèle"},
                ],
            },
        },
    },
}
REPORT_DATASET_LABELS = {
    code: details["label"] for code, details in REPORT_DATASET_SCHEMAS.items()
}

FINANCIAL_WORKFLOW_SCOPES = {
    "tenant": "Établissement",
    "academic_year": "Année académique",
    "payment_rubric": "Rubrique de paiement",
}

DEFAULT_ACADEMIC_CONFIGURATION = {
    "language": "fr",
    "framework": "custom",
    "grading_scale": {"minimum": 0, "maximum": 20, "pass_mark": 10},
    "evaluation_types": [
        {"code": "controle", "label": "Contrôle continu"},
        {"code": "composition", "label": "Composition"},
        {"code": "examen", "label": "Examen"},
    ],
    "import_templates": [
        {
            "code": "continuous_assessment_grades",
            "label": "Import notes de contrôle continu",
            "type": "continuous_assessment_grades",
            "allowed_extensions": ["xlsx", "xls"],
            "columns": ["matricule", "note", "appreciation", "statut"],
            "strict_columns": True,
        },
        {
            "code": "exam_grades",
            "label": "Import notes d'examen",
            "type": "exam_grades",
            "allowed_extensions": ["xlsx", "xls"],
            "columns": [
                "epreuve_id",
                "eleve_matricule",
                "note",
                "appreciation",
                "type_resultat",
            ],
            "strict_columns": True,
        },
        {
            "code": "final_results",
            "label": "Import résultats finaux",
            "type": "final_results",
            "allowed_extensions": ["xlsx", "xls"],
            "columns": ["session_id", "matricule", "resultat", "mention"],
            "strict_columns": True,
        },
    ],
    "exam_result_workflows": [
        {
            "code": "default_secondary_exam_results",
            "label": "Workflow examens secondaire",
            "scope": "tenant",
            "variants": ["secondaire"],
            "verification_group_codes": [
                "class_council_manager_secondary",
                "exam_manager_secondary",
            ],
            "validation_group_codes": ["exam_manager_secondary"],
            "publication_group_codes": ["exam_manager_secondary"],
            "allowed_export_formats": ["csv", "xlsx", "pdf"],
            "import_template_codes": ["exam_grades", "final_results"],
            "correction_window_days": 0,
            "allow_retake_after_closure": True,
            "allow_student_submission": False,
        },
        {
            "code": "default_superior_exam_results",
            "label": "Workflow examens supérieur",
            "scope": "tenant",
            "variants": ["superieur"],
            "verification_group_codes": [
                "exam_manager_superieur",
            ],
            "validation_group_codes": ["exam_manager_superieur"],
            "publication_group_codes": ["exam_manager_superieur"],
            "allowed_export_formats": ["csv", "xlsx", "pdf"],
            "import_template_codes": ["exam_grades", "final_results"],
            "correction_window_days": 0,
            "allow_retake_after_closure": True,
            "allow_student_submission": False,
        },
    ],
    "submission_windows": {
        "evaluation": {
            "enabled": True,
            "default_open_offset_hours": 0,
            "default_close_offset_hours": 72,
            "reminder_hours": [24, 2],
            "notify_assigned_users": True,
            "recipient_role_codes": [],
            "recipient_group_codes": [],
        },
        "exam": {
            "enabled": True,
            "default_open_offset_hours": 0,
            "default_close_offset_hours": 48,
            "reminder_hours": [24, 2],
            "notify_assigned_users": True,
            "recipient_role_codes": [],
            "recipient_group_codes": [],
        },
    },
    "catalogs": {
        "institution_types": [],
        "period_types": [],
        "group_types": [],
        "subject_types": [],
        "formation_types": [],
        "formation_levels": [],
        "study_regimes": [],
        "teaching_modalities": [],
        "ue_types": [],
    },
    "dimensions": [
        {
            "code": "institution_type",
            "label": "Type d'établissement",
            "axis": "institutional",
            "scope": "tenant",
            "applicable_to": ["secondaire", "superieur"],
        },
        {
            "code": "academic_year",
            "label": "Année académique",
            "axis": "academic",
            "scope": "academic_year",
            "applicable_to": ["secondaire", "superieur"],
        },
        {
            "code": "period",
            "label": "Période",
            "axis": "academic",
            "scope": "period",
            "applicable_to": ["secondaire", "superieur"],
        },
        {
            "code": "semester",
            "label": "Semestre",
            "axis": "academic",
            "scope": "semester",
            "applicable_to": ["superieur"],
        },
        {
            "code": "level",
            "label": "Niveau",
            "axis": "academic",
            "scope": "level",
            "applicable_to": ["secondaire", "superieur"],
        },
        {
            "code": "class",
            "label": "Classe",
            "axis": "organizational",
            "scope": "class",
            "applicable_to": ["secondaire"],
        },
        {
            "code": "department",
            "label": "Département",
            "axis": "organizational",
            "scope": "department",
            "applicable_to": ["superieur"],
        },
        {
            "code": "program",
            "label": "Filière / formation",
            "axis": "organizational",
            "scope": "program",
            "applicable_to": ["superieur"],
        },
        {
            "code": "subject",
            "label": "Matière / ECUE",
            "axis": "pedagogical",
            "scope": "subject",
            "applicable_to": ["secondaire", "superieur"],
        },
        {
            "code": "teaching_unit",
            "label": "UE / unité d'enseignement",
            "axis": "pedagogical",
            "scope": "unit",
            "applicable_to": ["superieur"],
        },
        {
            "code": "payment_rubric",
            "label": "Rubrique de paiement",
            "axis": "financial",
            "scope": "payment",
            "applicable_to": ["secondaire", "superieur"],
        },
    ],
    "custom_dimensions": [],
    "permission_groups": [
        {
            "code": "academic_admin_secondary",
            "label": "Administration pédagogique secondaire",
            "permissions": [
                "notes.change_reglevalidation",
                "utilisateurs.view_utilisateur",
                "etablissement.change_etablissement",
            ],
            "attributes": {},
        },
        {
            "code": "academic_admin_superieur",
            "label": "Administration pédagogique supérieur",
            "permissions": [
                "notes.change_reglevalidation",
                "utilisateurs.view_utilisateur",
                "etablissement.change_universite",
            ],
            "attributes": {},
        },
        {
            "code": "finance_manager_secondary",
            "label": "Gestion financière secondaire",
            "permissions": [
                "paiements.change_paiement",
            ],
            "attributes": {},
        },
        {
            "code": "finance_manager_superieur",
            "label": "Gestion financière supérieur",
            "permissions": [
                "paiements.change_paiementfrais",
            ],
            "attributes": {},
        },
        {
            "code": "academic_registry_superieur",
            "label": "Scolarité et registres supérieur",
            "permissions": [
                "releves.change_relevenotes",
                "releves.change_transcript",
                "releves.change_attestation",
            ],
            "attributes": {},
        },
        {
            "code": "document_signatory_superieur",
            "label": "Signataire documentaire supérieur",
            "permissions": [
                "releves.change_relevenotes",
                "releves.change_transcript",
                "releves.change_attestation",
                "diplomes.change_cessiondiplome",
            ],
            "attributes": {},
        },
        {
            "code": "exam_manager_secondary",
            "label": "Gestion examens secondaire",
            "permissions": [
                "examens.change_sessionexamen",
                "examens.change_epreuveexamen",
                "examens.change_convocationexamen",
                "examens.change_resultatexamen",
            ],
            "attributes": {},
        },
        {
            "code": "exam_manager_superieur",
            "label": "Gestion examens supérieur",
            "permissions": [
                "examens.change_sessionexamen",
                "examens.change_epreuveexamen",
                "examens.change_convocationexamen",
            ],
            "attributes": {},
        },
        {
            "code": "registration_manager_superieur",
            "label": "Gestion inscriptions supérieur",
            "permissions": [
                "etudiants.change_inscriptionadministrative",
            ],
            "attributes": {},
        },
        {
            "code": "stage_manager_secondary",
            "label": "Gestion stages secondaire",
            "permissions": [
                "stages.change_conventionstage",
                "stages.change_entreprise",
                "stages.change_suivistage",
                "stages.change_evaluationstage",
            ],
            "attributes": {},
        },
        {
            "code": "jury_manager_superieur",
            "label": "Gestion jurys supérieur",
            "permissions": [
                "jurys.change_jury",
                "jurys.change_deliberation",
                "jurys.change_decisionjury",
                "jurys.change_decisionglobale",
            ],
            "attributes": {},
        },
        {
            "code": "class_council_manager_secondary",
            "label": "Gestion conseils de classe secondaire",
            "permissions": [
                "conseil_classe.change_conseilclasse",
                "conseil_classe.change_decisionconseil",
                "conseil_classe.change_appreciationconseil",
            ],
            "attributes": {},
        },
        {
            "code": "attendance_manager_secondary",
            "label": "Gestion présences secondaire",
            "permissions": [
                "presences.change_appel",
                "presences.change_presence",
                "presences.change_justificatif",
            ],
            "attributes": {},
        },
        {
            "code": "memoire_manager_superieur",
            "label": "Gestion mémoires supérieur",
            "permissions": [
                "memoires.change_sujetmemoire",
                "memoires.change_memoire",
                "memoires.change_jurymemoire",
            ],
            "attributes": {},
        },
        {
            "code": "class_manager_secondary",
            "label": "Gestion classes secondaire",
            "permissions": [
                "classes.change_classe",
                "classes.change_groupe",
                "classes.change_matiere",
                "classes.change_programmematiere",
            ],
            "attributes": {},
        },
        {
            "code": "student_manager_secondary",
            "label": "Gestion élèves secondaire",
            "permissions": [
                "eleves.change_eleve",
                "eleves.change_inscription",
                "eleves.change_tuteur",
                "eleves.change_elevetuteur",
            ],
            "attributes": {},
        },
        {
            "code": "schedule_manager_secondary",
            "label": "Gestion emplois du temps secondaire",
            "permissions": [
                "emplois_du_temps.change_creneau",
                "emplois_du_temps.change_contrainte",
            ],
            "attributes": {},
        },
        {
            "code": "student_manager_superieur",
            "label": "Gestion étudiants supérieur",
            "permissions": [
                "etudiants.change_etudiant",
                "etudiants.change_inscriptionadministrative",
            ],
            "attributes": {},
        },
        {
            "code": "mobility_manager_superieur",
            "label": "Gestion mobilité supérieur",
            "permissions": [
                "mobilite.change_programmemobilite",
                "mobilite.change_candidaturemobilite",
                "mobilite.change_accordetudes",
            ],
            "attributes": {},
        },
        {
            "code": "retake_manager_superieur",
            "label": "Gestion rattrapages supérieur",
            "permissions": [
                "rattrapages.change_inscriptionrattrapage",
            ],
            "attributes": {},
        },
        {
            "code": "boarding_manager_secondary",
            "label": "Gestion internat secondaire",
            "permissions": [
                "internat.change_batimentinternat",
                "internat.change_chambre",
                "internat.change_occupantchambre",
                "internat.change_etudesurveillee",
            ],
            "attributes": {},
        },
        {
            "code": "canteen_manager_secondary",
            "label": "Gestion cantine secondaire",
            "permissions": [
                "cantine.change_menu",
                "cantine.change_inscriptioncantine",
                "cantine.change_presencecantine",
            ],
            "attributes": {},
        },
        {
            "code": "transport_manager_secondary",
            "label": "Gestion transport secondaire",
            "permissions": [
                "transport.change_lignetransport",
                "transport.change_arret",
                "transport.change_vehicule",
                "transport.change_inscriptiontransport",
            ],
            "attributes": {},
        },
        {
            "code": "library_manager_secondary",
            "label": "Gestion bibliothèque secondaire",
            "permissions": [
                "bibliotheque.change_livre",
                "bibliotheque.change_exemplaire",
                "bibliotheque.change_emprunt",
            ],
            "attributes": {},
        },
        {
            "code": "health_manager_secondary",
            "label": "Gestion infirmerie secondaire",
            "permissions": [
                "infirmerie.change_dossiermedical",
                "infirmerie.change_visiteinfirmerie",
                "infirmerie.change_stockmedicament",
            ],
            "attributes": {},
        },
        {
            "code": "club_manager_secondary",
            "label": "Gestion clubs secondaire",
            "permissions": [
                "clubs.change_club",
                "clubs.change_membreclub",
                "clubs.change_seanceclub",
            ],
            "attributes": {},
        },
        {
            "code": "ects_manager_superieur",
            "label": "Gestion ECTS supérieur",
            "permissions": [
                "ects.change_bilanects",
            ],
            "attributes": {},
        },
        {
            "code": "curriculum_manager_superieur",
            "label": "Gestion maquettes supérieur",
            "permissions": [
                "formations.change_maquetteformation",
            ],
            "attributes": {},
        },
        {
            "code": "enterprise_relations_manager_superieur",
            "label": "Gestion relations entreprises supérieur",
            "permissions": [
                "entreprises.change_entreprise",
                "entreprises.change_contactentreprise",
            ],
            "attributes": {},
        },
        {
            "code": "research_manager_superieur",
            "label": "Gestion recherche supérieur",
            "permissions": [
                "recherche.change_laboratoire",
                "recherche.change_projetrecherche",
                "recherche.change_productionscientifique",
                "recherche.change_these",
            ],
            "attributes": {},
        },
    ],
    "validation_policies": [],
    "financial_workflows": [
        {
            "code": "payment_review",
            "label": "Validation des paiements",
            "scope": "tenant",
            "steps": [
                {"code": "submitted", "label": "Soumis"},
                {"code": "under_review", "label": "En contrôle"},
                {"code": "validated", "label": "Validé", "terminal": True},
                {"code": "rejected", "label": "Rejeté", "terminal": True},
                {"code": "refunded", "label": "Remboursé", "terminal": True},
            ],
            "required_permissions": ["paiements.change_paiement", "paiements.change_paiementfrais"],
            "transitions": [
                {"action": "valider", "from": "en_attente", "to": "valide"},
                {"action": "rejeter", "from": "en_attente", "to": "rejete"},
                {"action": "rembourser", "from": "valide", "to": "rembourse"},
            ],
        }
    ],
    "reports": [],
}


def default_academic_configuration():
    return deepcopy(DEFAULT_ACADEMIC_CONFIGURATION)


def _decimal(value, path):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError(f"{path} doit être un nombre.") from exc


def _validate_code_items(items, path):
    if not isinstance(items, list):
        raise ValidationError(f"{path} doit être une liste.")
    codes = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValidationError(f"{path}[{index}] doit être un objet.")
        code = str(item.get("code", "")).strip()
        label = str(item.get("label", "")).strip()
        if not code or not label:
            raise ValidationError(f"{path}[{index}] exige code et label.")
        if code in codes:
            raise ValidationError(f"Le code {code!r} est dupliqué dans {path}.")
        codes.add(code)


def _validate_string_list(items, path, *, empty_allowed=True):
    if not isinstance(items, list):
        raise ValidationError(f"{path} doit être une liste.")
    if not empty_allowed and not items:
        raise ValidationError(f"{path} ne peut pas être vide.")
    for index, item in enumerate(items):
        if not isinstance(item, str) or not item.strip():
            raise ValidationError(f"{path}[{index}] doit être une chaîne non vide.")


def _validate_targets(value, path):
    if not isinstance(value, dict):
        raise ValidationError(f"{path} doit être un objet.")
    for key, target in value.items():
        if not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", key):
            raise ValidationError(f"{path}.{key} est invalide.")
        if isinstance(target, list):
            if not target:
                raise ValidationError(f"{path}.{key} ne peut pas être vide.")
        elif isinstance(target, (str, int, float, bool)) or target is None:
            continue
        else:
            raise ValidationError(f"{path}.{key} doit être scalaire ou une liste.")


def _validate_dimensions(items):
    _validate_code_items(items, "dimensions")
    for index, item in enumerate(items):
        axis = item.get("axis")
        scope = item.get("scope")
        if axis not in DIMENSION_AXES:
            raise ValidationError(f"dimensions[{index}].axis est invalide.")
        if scope not in DIMENSION_SCOPES:
            raise ValidationError(f"dimensions[{index}].scope est invalide.")
        applicable_to = item.get("applicable_to", [])
        _validate_string_list(applicable_to, f"dimensions[{index}].applicable_to")


def _validate_permission_groups(items):
    _validate_code_items(items, "permission_groups")
    for index, item in enumerate(items):
        _validate_string_list(
            item.get("permissions", []),
            f"permission_groups[{index}].permissions",
            empty_allowed=False,
        )
        attributes = item.get("attributes", {})
        if not isinstance(attributes, dict):
            raise ValidationError(f"permission_groups[{index}].attributes doit être un objet.")


def _validate_validation_policies(items):
    _validate_code_items(items, "validation_policies")
    for index, item in enumerate(items):
        scope = item.get("scope")
        if scope not in VALIDATION_POLICY_SCOPES:
            raise ValidationError(f"validation_policies[{index}].scope est invalide.")
        if "targets" in item:
            _validate_targets(item["targets"], f"validation_policies[{index}].targets")
        if "criteria" in item:
            validate_rule_criteria(item["criteria"])
        thresholds = item.get("thresholds", {})
        if not isinstance(thresholds, dict):
            raise ValidationError(f"validation_policies[{index}].thresholds doit être un objet.")
        for name, threshold in thresholds.items():
            if isinstance(threshold, bool):
                continue
            _decimal(threshold, f"validation_policies[{index}].thresholds.{name}")
        publication = item.get("publication", {})
        if not isinstance(publication, dict):
            raise ValidationError(f"validation_policies[{index}].publication doit être un objet.")
        for key in ("requires_financial_clearance", "auto_publish", "manual_review_required"):
            if key in publication and not isinstance(publication[key], bool):
                raise ValidationError(f"validation_policies[{index}].publication.{key} doit être booléen.")


def _validate_financial_workflows(items):
    _validate_code_items(items, "financial_workflows")
    for index, workflow in enumerate(items):
        scope = workflow.get("scope")
        if scope not in FINANCIAL_WORKFLOW_SCOPES:
            raise ValidationError(f"financial_workflows[{index}].scope est invalide.")
        if "targets" in workflow:
            _validate_targets(workflow["targets"], f"financial_workflows[{index}].targets")
        _validate_string_list(
            workflow.get("required_permissions", []),
            f"financial_workflows[{index}].required_permissions",
        )
        steps = workflow.get("steps", [])
        _validate_code_items(steps, f"financial_workflows[{index}].steps")
        for step_index, step in enumerate(steps):
            if "terminal" in step and not isinstance(step["terminal"], bool):
                raise ValidationError(
                    f"financial_workflows[{index}].steps[{step_index}].terminal doit être booléen."
                )
        transitions = workflow.get("transitions", [])
        if not isinstance(transitions, list):
            raise ValidationError(f"financial_workflows[{index}].transitions doit être une liste.")
        for transition_index, transition in enumerate(transitions):
            if not isinstance(transition, dict):
                raise ValidationError(
                    f"financial_workflows[{index}].transitions[{transition_index}] doit être un objet."
                )
            for key in ("action", "from", "to"):
                value = str(transition.get(key, "")).strip()
                if not value:
                    raise ValidationError(
                        f"financial_workflows[{index}].transitions[{transition_index}].{key} est requis."
                    )


def _validate_reports(items):
    _validate_code_items(items, "reports")
    for index, report in enumerate(items):
        dataset = report.get("dataset")
        if dataset not in REPORT_DATASET_LABELS:
            raise ValidationError(
                f"reports[{index}].dataset doit être l'un de: {', '.join(sorted(REPORT_DATASET_LABELS))}."
            )
        if not isinstance(report.get("fields"), list) or not report["fields"]:
            raise ValidationError(f"reports[{index}].fields doit être une liste non vide.")
        if not isinstance(report.get("allowed_filters", []), list):
            raise ValidationError(f"reports[{index}].allowed_filters doit être une liste.")
        formats = report.get("formats", ["csv"])
        _validate_string_list(formats, f"reports[{index}].formats", empty_allowed=False)
        unknown_formats = set(formats) - set(REPORT_EXPORT_FORMATS)
        if unknown_formats:
            raise ValidationError(
                f"reports[{index}].formats doit être parmi: {', '.join(sorted(REPORT_EXPORT_FORMATS))}."
            )
        if "required_permissions" in report:
            _validate_string_list(
                report["required_permissions"],
                f"reports[{index}].required_permissions",
                empty_allowed=False,
            )
        default_group_by = report.get("default_group_by")
        if default_group_by is not None and (not isinstance(default_group_by, str) or not default_group_by.strip()):
            raise ValidationError(f"reports[{index}].default_group_by doit être une chaîne non vide.")


def _validate_import_templates(items):
    _validate_code_items(items, "import_templates")
    for index, template in enumerate(items):
        template_type = template.get("type")
        if template_type not in IMPORT_TEMPLATE_TYPES:
            raise ValidationError(
                f"import_templates[{index}].type doit être l'un de: {', '.join(sorted(IMPORT_TEMPLATE_TYPES))}."
            )
        columns = template.get("columns", [])
        _validate_string_list(
            columns,
            f"import_templates[{index}].columns",
            empty_allowed=False,
        )
        extensions = template.get("allowed_extensions", ["xlsx"])
        _validate_string_list(
            extensions,
            f"import_templates[{index}].allowed_extensions",
            empty_allowed=False,
        )
        unknown_extensions = set(extensions) - {"xlsx", "xls"}
        if unknown_extensions:
            raise ValidationError(
                f"import_templates[{index}].allowed_extensions doit être parmi: xls, xlsx."
            )
        strict_columns = template.get("strict_columns", True)
        if not isinstance(strict_columns, bool):
            raise ValidationError(
                f"import_templates[{index}].strict_columns doit être booléen."
            )


def _validate_exam_result_workflows(items, template_codes=None):
    _validate_code_items(items, "exam_result_workflows")
    for index, workflow in enumerate(items):
        scope = workflow.get("scope")
        if scope not in EXAM_RESULT_WORKFLOW_SCOPES:
            raise ValidationError(
                f"exam_result_workflows[{index}].scope doit être l'un de: {', '.join(sorted(EXAM_RESULT_WORKFLOW_SCOPES))}."
            )
        variants = workflow.get("variants", [])
        _validate_string_list(
            variants,
            f"exam_result_workflows[{index}].variants",
            empty_allowed=False,
        )
        unknown_variants = set(variants) - {"secondaire", "superieur"}
        if unknown_variants:
            raise ValidationError(
                f"exam_result_workflows[{index}].variants contient une valeur invalide."
            )
        for key in (
            "verification_group_codes",
            "validation_group_codes",
            "publication_group_codes",
            "allowed_export_formats",
            "import_template_codes",
        ):
            _validate_string_list(workflow.get(key, []), f"exam_result_workflows[{index}].{key}")
        unknown_formats = set(workflow.get("allowed_export_formats", [])) - set(
            REPORT_EXPORT_FORMATS
        )
        if unknown_formats:
            raise ValidationError(
                f"exam_result_workflows[{index}].allowed_export_formats contient un format invalide."
            )
        configured_template_codes = set(template_codes or ())
        unknown_templates = set(workflow.get("import_template_codes", [])) - configured_template_codes
        if unknown_templates:
            raise ValidationError(
                f"exam_result_workflows[{index}].import_template_codes contient un modèle invalide."
            )
        correction_window_days = workflow.get("correction_window_days", 0)
        if not isinstance(correction_window_days, int) or correction_window_days < 0:
            raise ValidationError(
                f"exam_result_workflows[{index}].correction_window_days doit être un entier positif."
            )
        for key in ("allow_retake_after_closure", "allow_student_submission"):
            if key in workflow and not isinstance(workflow[key], bool):
                raise ValidationError(
                    f"exam_result_workflows[{index}].{key} doit être booléen."
                )
        if "targets" in workflow:
            _validate_targets(workflow["targets"], f"exam_result_workflows[{index}].targets")


def _validate_submission_windows(value):
    if not isinstance(value, dict):
        raise ValidationError("submission_windows doit être un objet.")
    unknown_types = set(value) - set(SUBMISSION_WINDOW_TYPES)
    if unknown_types:
        raise ValidationError(
            "submission_windows contient un type invalide: "
            + ", ".join(sorted(unknown_types))
            + "."
        )
    for code, settings in value.items():
        if not isinstance(settings, dict):
            raise ValidationError(f"submission_windows.{code} doit être un objet.")
        enabled = settings.get("enabled", True)
        if not isinstance(enabled, bool):
            raise ValidationError(f"submission_windows.{code}.enabled doit être booléen.")
        notify_assigned_users = settings.get("notify_assigned_users", True)
        if not isinstance(notify_assigned_users, bool):
            raise ValidationError(f"submission_windows.{code}.notify_assigned_users doit être booléen.")
        for key in ("default_open_offset_hours", "default_close_offset_hours"):
            if key in settings and not isinstance(settings[key], int):
                raise ValidationError(f"submission_windows.{code}.{key} doit être un entier.")
        reminder_hours = settings.get("reminder_hours", [])
        if not isinstance(reminder_hours, list):
            raise ValidationError(f"submission_windows.{code}.reminder_hours doit être une liste.")
        for index, item in enumerate(reminder_hours):
            if not isinstance(item, int) or item < 0:
                raise ValidationError(
                    f"submission_windows.{code}.reminder_hours[{index}] doit être un entier positif ou nul."
                )
        for key in ("recipient_role_codes", "recipient_group_codes"):
            values = settings.get(key, [])
            if not isinstance(values, list):
                raise ValidationError(f"submission_windows.{code}.{key} doit être une liste.")
            for index, item in enumerate(values):
                if not isinstance(item, str) or not item.strip():
                    raise ValidationError(
                        f"submission_windows.{code}.{key}[{index}] doit être une chaîne non vide."
                    )


def _report_dataset_schema(variant=None):
    datasets = []
    for code, details in REPORT_DATASET_SCHEMAS.items():
        variants = details.get("variants", {})
        applicable_to = sorted(variants)
        if variant:
            if variant not in variants:
                continue
            dataset = variants[variant]
        else:
            dataset = {}
        datasets.append(
            {
                "code": code,
                "label": details["label"],
                "applicable_to": applicable_to,
                "fields": dataset.get("fields", []),
                "allowed_filters": dataset.get("allowed_filters", []),
                "group_by_options": dataset.get("group_by_options", []),
                "export_formats": [
                    {"code": code, "label": label}
                    for code, label in REPORT_EXPORT_FORMATS.items()
                ],
            }
        )
    return datasets


def academic_configuration_schema(variant=None):
    role_options = {
        "secondaire": SECONDARY_USER_ROLES,
        "superieur": SUPERIOR_USER_ROLES,
    }.get(variant, {**SECONDARY_USER_ROLES, **SUPERIOR_USER_ROLES})
    return {
        "dimension_axes": [{"code": code, "label": label} for code, label in DIMENSION_AXES.items()],
        "dimension_scopes": [{"code": code, "label": label} for code, label in DIMENSION_SCOPES.items()],
        "validation_scopes": [{"code": code, "label": label} for code, label in VALIDATION_POLICY_SCOPES.items()],
        "report_datasets": _report_dataset_schema(variant),
        "financial_workflow_scopes": [
            {"code": code, "label": label} for code, label in FINANCIAL_WORKFLOW_SCOPES.items()
        ],
        "report_export_formats": [
            {"code": code, "label": label} for code, label in REPORT_EXPORT_FORMATS.items()
        ],
        "import_template_types": [
            {"code": code, "label": label} for code, label in IMPORT_TEMPLATE_TYPES.items()
        ],
        "exam_result_workflow_scopes": [
            {"code": code, "label": label}
            for code, label in EXAM_RESULT_WORKFLOW_SCOPES.items()
        ],
        "submission_window_types": [
            {"code": code, "label": label}
            for code, label in SUBMISSION_WINDOW_TYPES.items()
        ],
        "submission_window_recipient_roles": [
            {"code": code, "label": label} for code, label in role_options.items()
        ],
    }


def _target_matches(targets, context):
    context = context or {}
    for key, expected in (targets or {}).items():
        actual = context.get(key)
        if isinstance(expected, list):
            if actual not in expected:
                return False
        elif actual != expected:
            return False
    return True


def resolve_validation_policy(configuration, candidates):
    policies = (configuration or {}).get("validation_policies", [])
    candidates = candidates if isinstance(candidates, list) else [candidates]
    for candidate in candidates:
        scope = candidate.get("scope")
        context = candidate.get("context", {})
        matching = [
            policy
            for policy in policies
            if policy.get("scope") == scope
            and policy.get("active", True)
            and _target_matches(policy.get("targets", {}), context)
        ]
        if matching:
            return sorted(
                matching,
                key=lambda item: (-len(item.get("targets", {})), item.get("priority", 100)),
            )[0]
    return None


def resolve_financial_workflow(configuration, candidates):
    workflows = (configuration or {}).get("financial_workflows", [])
    candidates = candidates if isinstance(candidates, list) else [candidates]
    for candidate in candidates:
        scope = candidate.get("scope")
        context = candidate.get("context", {})
        matching = [
            workflow
            for workflow in workflows
            if workflow.get("scope") == scope
            and workflow.get("active", True)
            and _target_matches(workflow.get("targets", {}), context)
        ]
        if matching:
            return sorted(
                matching,
                key=lambda item: (-len(item.get("targets", {})), item.get("priority", 100)),
            )[0]
    return None


def resolve_exam_result_workflow(configuration, candidates, variant=None):
    workflows = (configuration or {}).get("exam_result_workflows", [])
    candidates = candidates if isinstance(candidates, list) else [candidates]
    for candidate in candidates:
        scope = candidate.get("scope")
        context = candidate.get("context", {})
        matching = [
            workflow
            for workflow in workflows
            if workflow.get("scope") == scope
            and workflow.get("active", True)
            and _target_matches(workflow.get("targets", {}), context)
            and (variant is None or variant in workflow.get("variants", []))
        ]
        if matching:
            return sorted(
                matching,
                key=lambda item: (-len(item.get("targets", {})), item.get("priority", 100)),
            )[0]
    return None


def resolve_submission_window_settings(configuration, window_type):
    defaults = deepcopy(
        DEFAULT_ACADEMIC_CONFIGURATION.get("submission_windows", {}).get(window_type, {})
    )
    current = (configuration or {}).get("submission_windows", {}).get(window_type, {})
    if not isinstance(current, dict):
        return defaults
    return {**defaults, **current}


def workflow_transition_allowed(workflow, action, current_status, next_status):
    transitions = (workflow or {}).get("transitions", [])
    if not transitions:
        return True
    return any(
        transition.get("action") == action
        and transition.get("from") == current_status
        and transition.get("to") == next_status
        for transition in transitions
    )


def validate_academic_configuration(value):
    if not isinstance(value, dict):
        raise ValidationError("La configuration académique doit être un objet.")
    unknown = set(value) - set(DEFAULT_ACADEMIC_CONFIGURATION)
    if unknown:
        raise ValidationError(f"Clés de configuration académique inconnues: {', '.join(sorted(unknown))}.")

    scale = value.get("grading_scale", {})
    if not isinstance(scale, dict):
        raise ValidationError("grading_scale doit être un objet.")
    required = {"minimum", "maximum", "pass_mark"}
    if set(scale) != required:
        raise ValidationError("grading_scale exige uniquement minimum, maximum et pass_mark.")
    minimum = _decimal(scale["minimum"], "grading_scale.minimum")
    maximum = _decimal(scale["maximum"], "grading_scale.maximum")
    pass_mark = _decimal(scale["pass_mark"], "grading_scale.pass_mark")
    if minimum >= maximum or not minimum <= pass_mark <= maximum:
        raise ValidationError("L'échelle de notation ou le seuil de réussite est invalide.")

    _validate_code_items(value.get("evaluation_types", []), "evaluation_types")
    catalogs = value.get("catalogs", {})
    if not isinstance(catalogs, dict):
        raise ValidationError("catalogs doit être un objet.")
    for name, items in catalogs.items():
        if not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", name):
            raise ValidationError(f"Nom de catalogue invalide: {name!r}.")
        _validate_code_items(items, f"catalogs.{name}")
    _validate_dimensions(value.get("dimensions", []))
    _validate_code_items(value.get("custom_dimensions", []), "custom_dimensions")
    _validate_permission_groups(value.get("permission_groups", []))
    _validate_validation_policies(value.get("validation_policies", []))
    _validate_financial_workflows(value.get("financial_workflows", []))
    import_templates = value.get("import_templates", [])
    _validate_import_templates(import_templates)
    _validate_exam_result_workflows(
        value.get("exam_result_workflows", []),
        template_codes={template["code"] for template in import_templates},
    )
    _validate_submission_windows(value.get("submission_windows", {}))
    _validate_reports(value.get("reports", []))


def merge_academic_configuration(current, updates):
    merged = default_academic_configuration()
    merged.update(current or {})
    merged.update(updates or {})
    if "grading_scale" in updates:
        merged["grading_scale"] = {
            **DEFAULT_ACADEMIC_CONFIGURATION["grading_scale"],
            **(current or {}).get("grading_scale", {}),
            **updates["grading_scale"],
        }
    if "catalogs" in updates:
        merged["catalogs"] = {
            **DEFAULT_ACADEMIC_CONFIGURATION["catalogs"],
            **(current or {}).get("catalogs", {}),
            **updates["catalogs"],
        }
    if "submission_windows" in updates:
        merged["submission_windows"] = deepcopy(DEFAULT_ACADEMIC_CONFIGURATION["submission_windows"])
        for source in ((current or {}).get("submission_windows", {}), updates["submission_windows"]):
            for window_type, settings in (source or {}).items():
                merged["submission_windows"][window_type] = {
                    **merged["submission_windows"].get(window_type, {}),
                    **(settings or {}),
                }
    validate_academic_configuration(merged)
    return merged


def catalog_options(configuration, name, fallback=()):
    items = (configuration or {}).get("catalogs", {}).get(name, [])
    if items:
        return deepcopy(items)
    return [{"code": code, "label": label} for code, label in fallback]


def catalog_label(configuration, name, code, fallback=()):
    options = catalog_options(configuration, name, fallback)
    return next(
        (item["label"] for item in options if item["code"] == code),
        code,
    )


def validate_rule_criteria(value):
    if not isinstance(value, dict):
        raise ValidationError("Les critères doivent être un objet.")
    for code, criterion in value.items():
        if not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", code):
            raise ValidationError(f"Code de critère invalide: {code!r}.")
        if not isinstance(criterion, dict):
            raise ValidationError(f"Le critère {code!r} doit être un objet.")
        operator = criterion.get("operator")
        if operator not in {"gte", "lte", "eq", "in"}:
            raise ValidationError(f"Opérateur invalide pour le critère {code!r}.")
        if "value" not in criterion:
            raise ValidationError(f"Le critère {code!r} exige une valeur.")
        if operator == "in" and not isinstance(criterion["value"], list):
            raise ValidationError(f"La valeur du critère {code!r} doit être une liste.")


def evaluate_rule_criteria(criteria, data):
    validate_rule_criteria(criteria)
    data = data or {}
    failures = []
    for code, criterion in criteria.items():
        actual = data.get(code)
        expected = criterion["value"]
        operator = criterion["operator"]
        passed = False
        if actual is not None:
            if operator == "in":
                passed = actual in expected
            elif operator == "eq":
                passed = actual == expected
            else:
                try:
                    actual_number = _decimal(actual, code)
                    expected_number = _decimal(expected, code)
                    passed = actual_number >= expected_number if operator == "gte" else actual_number <= expected_number
                except ValidationError:
                    passed = False
        if not passed:
            failures.append(f"critere:{code}")
    return failures
