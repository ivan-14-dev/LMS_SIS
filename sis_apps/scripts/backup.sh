#!/usr/bin/env bash
set -euo pipefail

# Sauvegarde complète (schéma public + tous les schémas tenants) d'une base
# SIS (secondaire ou supérieur) via pg_dump au format "custom" (-Fc), qui
# permet une restauration sélective ou complète avec pg_restore.
#
# django-tenants place chaque établissement dans son propre schéma Postgres
# au sein de la même base ; un pg_dump de la base entière couvre donc à la
# fois le schéma public et tous les schémas tenants en une seule opération.
#
# Variables d'environnement attendues (mêmes noms que config/settings.py) :
#   DB_NAME, DB_USER, DB_PASSWORD, DB_HOST (défaut: localhost),
#   DB_PORT (défaut: 5432)
#
# Usage :
#   ./scripts/backup.sh [répertoire_de_sortie]
#
# Voir sis_apps/docs/BACKUP_RESTORE.md pour la procédure complète.

OUTPUT_DIR="${1:-./backups}"
mkdir -p "${OUTPUT_DIR}"

: "${DB_NAME:?DB_NAME doit être défini}"
: "${DB_USER:?DB_USER doit être défini}"
: "${DB_HOST:=localhost}"
: "${DB_PORT:=5432}"

TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUTPUT_FILE="${OUTPUT_DIR}/${DB_NAME}_${TIMESTAMP}.dump"

export PGPASSWORD="${DB_PASSWORD:-}"

echo "Sauvegarde de la base '${DB_NAME}' (hôte ${DB_HOST}:${DB_PORT}) vers ${OUTPUT_FILE}..."

pg_dump \
  --host="${DB_HOST}" \
  --port="${DB_PORT}" \
  --username="${DB_USER}" \
  --format=custom \
  --file="${OUTPUT_FILE}" \
  "${DB_NAME}"

echo "Sauvegarde terminée : ${OUTPUT_FILE}"
echo "Vérification de l'intégrité de l'archive..."
pg_restore --list "${OUTPUT_FILE}" > /dev/null
echo "OK."
