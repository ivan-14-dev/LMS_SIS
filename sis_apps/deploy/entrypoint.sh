#!/bin/sh
set -eu

case "${SIS_VARIANT:-}" in
    secondaire|superieur) cd "/app/sis_${SIS_VARIANT}" ;;
    *) echo "SIS_VARIANT must be secondaire or superieur." >&2; exit 1 ;;
esac

mkdir -p "$LOG_DIR" "$STATIC_ROOT" "$MEDIA_ROOT" \
    "$PRIVATE_EXAM_STORAGE_ROOT" "$PRIVATE_FINANCIAL_STORAGE_ROOT"
exec "$@"
