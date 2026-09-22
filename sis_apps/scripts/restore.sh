#!/usr/bin/env bash
set -euo pipefail

# Restaure une sauvegarde SIS (produite par scripts/backup.sh) dans une base
# Postgres cible.
#
# ATTENTION : la restauration s'effectue avec --clean --if-exists, ce qui
# supprime les objets existants de la base cible (tous schémas, y compris les
# schémas tenants) avant de les recréer à partir de l'archive. Ne jamais
# restaurer directement sur une base de production sans validation préalable
# dans un environnement de recette.
#
# Variables d'environnement attendues (mêmes noms que config/settings.py) :
#   DB_NAME, DB_USER, DB_PASSWORD, DB_HOST (défaut: localhost),
#   DB_PORT (défaut: 5432)
#
# Usage :
#   ./scripts/restore.sh chemin/vers/sauvegarde.dump [--force]
#
# Voir sis_apps/docs/BACKUP_RESTORE.md pour la procédure complète.

DUMP_FILE="${1:?Usage: restore.sh <fichier.dump> [--force]}"
FORCE_FLAG="${2:-}"

: "${DB_NAME:?DB_NAME doit être défini}"
: "${DB_USER:?DB_USER doit être défini}"
: "${DB_HOST:=localhost}"
: "${DB_PORT:=5432}"

if [[ ! -f "${DUMP_FILE}" ]]; then
  echo "Fichier de sauvegarde introuvable : ${DUMP_FILE}" >&2
  exit 1
fi

if [[ "${FORCE_FLAG}" != "--force" ]]; then
  read -r -p "Restaurer '${DUMP_FILE}' dans la base '${DB_NAME}' sur ${DB_HOST}:${DB_PORT} va ÉCRASER les données existantes. Continuer ? [o/N] " REPLY
  if [[ ! "${REPLY}" =~ ^[oOyY]$ ]]; then
    echo "Restauration annulée."
    exit 1
  fi
fi

export PGPASSWORD="${DB_PASSWORD:-}"

echo "Restauration de ${DUMP_FILE} dans '${DB_NAME}' (hôte ${DB_HOST}:${DB_PORT})..."

pg_restore \
  --host="${DB_HOST}" \
  --port="${DB_PORT}" \
  --username="${DB_USER}" \
  --dbname="${DB_NAME}" \
  --clean \
  --if-exists \
  --no-owner \
  "${DUMP_FILE}"

echo "Restauration terminée."
