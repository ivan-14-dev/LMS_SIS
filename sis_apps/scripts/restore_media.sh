#!/usr/bin/env bash
set -euo pipefail

# Restaure une sauvegarde de fichiers médias (produite par
# scripts/backup_media.sh) dans un répertoire MEDIA_ROOT cible.
#
# ATTENTION : cette opération remplace le contenu du répertoire cible par
# celui de l'archive (les fichiers non présents dans l'archive mais ajoutés
# depuis la sauvegarde sont conservés ; les fichiers dont le nom coïncide
# sont écrasés). Ne jamais restaurer directement sur le MEDIA_ROOT de
# production sans validation préalable dans un environnement de recette.
#
# Variables d'environnement attendues :
#   MEDIA_ROOT (obligatoire) : chemin absolu vers le répertoire média cible
#
# Usage :
#   ./scripts/restore_media.sh chemin/vers/sauvegarde_media.tar.gz [--force]
#
# Voir sis_apps/docs/BACKUP_RESTORE.md pour la procédure complète.

ARCHIVE_FILE="${1:?Usage: restore_media.sh <archive.tar.gz> [--force]}"
FORCE_FLAG="${2:-}"

: "${MEDIA_ROOT:?MEDIA_ROOT doit être défini (chemin vers le répertoire média cible)}"

if [[ ! -f "${ARCHIVE_FILE}" ]]; then
  echo "Fichier de sauvegarde introuvable : ${ARCHIVE_FILE}" >&2
  exit 1
fi

if [[ "${FORCE_FLAG}" != "--force" ]]; then
  read -r -p "Restaurer '${ARCHIVE_FILE}' dans '${MEDIA_ROOT}' va écraser les fichiers médias existants portant le même nom. Continuer ? [o/N] " REPLY
  if [[ ! "${REPLY}" =~ ^[oOyY]$ ]]; then
    echo "Restauration annulée."
    exit 1
  fi
fi

mkdir -p "${MEDIA_ROOT}"

echo "Restauration de ${ARCHIVE_FILE} dans '${MEDIA_ROOT}'..."

tar --extract --gzip \
  --file="${ARCHIVE_FILE}" \
  --directory="$(dirname "${MEDIA_ROOT}")"

echo "Restauration terminée."
