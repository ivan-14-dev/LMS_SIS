# SIS Secondaire

Système d'Information Scolaire pour Lycées, Collèges et Lycées professionnels/professionnels.

## Démarrage rapide

```bash
# Activer l'environnement
python3 -m venv venv && source venv/bin/activate
pip install -r requirements/base.txt

# Variables d'environnement
export DJANGO_SECRET_KEY="$(python -c 'import secrets;print(secrets.token_urlsafe(50))')"
export DB_NAME=sis_secondaire
export DB_USER=postgres
export DB_PASSWORD=postgres
export DB_HOST=localhost
export REDIS_URL=redis://127.0.0.1:6379

# Migrations
python manage.py migrate_schemas --shared
python manage.py create_tenant  # interactif

# Serveur
python manage.py runserver 0.0.0.0:8001
```

## Ports

- SIS Secondaire : `8001`
- SIS Supérieur : `8002`
- LMS Open edX : `8000`

## Documentation

Voir le Tome 2 dans `/home/ivan/specs/tome2-sis-lycee/` et le Tome 8 pour l'architecture micro-frontend.
