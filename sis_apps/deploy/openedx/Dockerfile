ARG OPENEDX_BASE_IMAGE=overhangio/openedx:22.0.4-indigo
FROM ${OPENEDX_BASE_IMAGE}
COPY --chown=app:app patches /openedx/sis-patches
RUN patch --batch --forward --fuzz=0 -p1 < /openedx/sis-patches/jquery-all-loaded.patch && \
    ./manage.py lms collectstatic --noinput --settings=tutor.assets && \
    ./manage.py cms collectstatic --noinput --settings=tutor.assets
COPY --chown=app:app sis-provisioning /openedx/sis-provisioning
RUN pip install --no-deps /openedx/sis-provisioning
