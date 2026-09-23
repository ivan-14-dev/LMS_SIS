#!/usr/bin/env bash
set -euo pipefail

# Sauvegarde des fichiers médias (MEDIA_ROOT) d'une variante SIS (secondaire
# ou supérieur) : copies d'examens scannées, documents officiels générés,
# exports, pièces jointes, etc. — tout ce qui n'est pas stocké dans la base
# Postgres et qui est donc absent de scripts/backup.sh.
#
# django-tenants ne segmente pas MEDIA_ROOT par schéma : les fichiers de tous
# les établissements d'une même variante partagent le même répertoire média
# (organisé en sous-dossiers applicatifs). Une archive du répertoire complet
# couvre donc automatiquement tous les tenants de la variante.
#
# Variables d'environnement attendues :
#   MEDIA_ROOT (obligatoire) : chemin absolu vers le répertoire média de la
#     variante (valeur de `config/settings.py:MEDIA_ROOT`, ex.
#     /srv/sis_secondaire/media)
#
# Usage :
#   ./scripts/backup_media.sh [répertoire_de_sortie]
#
# Voir sis_apps/docs/BACKUP_RESTORE.md pour la procédure complète.

OUTPUT_DIR="${1:-./backups}"
mkdir -p "${OUTPUT_DIR}"

: "${MEDIA_ROOT:?MEDIA_ROOT doit être défini (chemin vers le répertoire média)}"

if [[ ! -d "${MEDIA_ROOT}" ]]; then
  echo "Répertoire média introuvable : ${MEDIA_ROOT}" >&2
  exit 1
fi

VARIANT_NAME="$(basename "$(cd "${MEDIA_ROOT}/.." && pwd)")"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUTPUT_FILE="${OUTPUT_DIR}/${VARIANT_NAME}_media_${TIMESTAMP}.tar.gz"

echo "Sauvegarde du répertoire média '${MEDIA_ROOT}' vers ${OUTPUT_FILE}..."

tar --create --gzip \
  --file="${OUTPUT_FILE}" \
  --directory="$(dirname "${MEDIA_ROOT}")" \
  "$(basename "${MEDIA_ROOT}")"

echo "Sauvegarde terminée : ${OUTPUT_FILE}"
echo "Vérification de l'intégrité de l'archive..."
tar --test --gzip --file="${OUTPUT_FILE}" > /dev/null
echo "OK."
