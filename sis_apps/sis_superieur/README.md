# SIS Supérieur

Système d'Information pour Universités, Grandes Écoles, Instituts.

## Démarrage rapide

```bash
# Activer l'environnement
python3 -m venv venv && source venv/bin/activate
pip install -r requirements/base.txt

# Variables d'environnement
export DJANGO_SECRET_KEY="$(python -c 'import secrets;print(secrets.token_urlsafe(50))')"
export DB_NAME=sis_superieur
export DB_USER=postgres
export DB_PASSWORD=postgres
export DB_HOST=localhost
export REDIS_URL=redis://127.0.0.1:6379

# Migrations
python manage.py migrate_schemas --shared
python manage.py create_tenant  # interactif

# Serveur
python manage.py runserver 0.0.0.0:8002
```

## Modules clés

- ECTS + capitalisation
- Prérequis
- Inscription pédagogique
- Jurys de délibération
- Mémoires & soutenances
- Mobilité internationale (ERASMUS+)
- Recherche (HAL, ORCID)
- Stages & conventions

## Documentation

Voir le Tome 3 dans `/home/ivan/specs/tome3-sis-universite/`.
