FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app \
    SIS_VARIANT=secondaire \
    LOG_DIR=/data/logs \
    STATIC_ROOT=/data/static \
    MEDIA_ROOT=/data/media \
    PRIVATE_EXAM_STORAGE_ROOT=/data/private_exam_copies \
    PRIVATE_FINANCIAL_STORAGE_ROOT=/data/private_financial_documents \
    CELERY_BEAT_SCHEDULE_FILENAME=/data/celerybeat-schedule

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 \
    libjpeg62-turbo libopenjp2-7 fonts-dejavu-core \
    && apt-get clean

WORKDIR /app
COPY requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir --require-hashes -r /tmp/requirements.lock \
    && pip check

RUN groupadd --gid 10001 sis && useradd --uid 10001 --gid sis --create-home sis \
    && mkdir /data && chown sis:sis /data
COPY --chown=sis:sis sis_common /app/sis_common
COPY --chown=sis:sis sis_secondaire /app/sis_secondaire
COPY --chown=sis:sis sis_superieur /app/sis_superieur
COPY deploy/entrypoint.sh /usr/local/bin/sis-entrypoint
USER sis
EXPOSE 8000
ENTRYPOINT ["sh", "/usr/local/bin/sis-entrypoint"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--access-logfile", "-", "--error-logfile", "-"]
