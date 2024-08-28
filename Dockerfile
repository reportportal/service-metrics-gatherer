FROM --platform=${BUILDPLATFORM} bitnami/python:3.10.14 as test
RUN apt-get update && apt-get install -y build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && python -m venv /venv \
    && mkdir /build
ENV VIRTUAL_ENV=/venv
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"
WORKDIR /build
COPY ./ ./
RUN "${VIRTUAL_ENV}/bin/pip" install --upgrade pip \
    && LIBRARY_PATH=/lib:/usr/lib /bin/sh -c "${VIRTUAL_ENV}/bin/pip install --no-cache-dir -r requirements.txt"
RUN "${VIRTUAL_ENV}/bin/pip" install --no-cache-dir -r requirements-dev.txt
RUN make test-all


FROM --platform=${BUILDPLATFORM} bitnami/python:3.10.14 as builder
RUN apt-get update && apt-get install -y build-essential libpcre3 libpcre3-dev libpq-dev\
    && rm -rf /var/lib/apt/lists/* \
    && python -m venv /venv \
    && mkdir /build
ENV VIRTUAL_ENV=/venv
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"
WORKDIR /build
COPY ./ ./
RUN "${VIRTUAL_ENV}/bin/pip" install --upgrade pip \
    && LIBRARY_PATH=/lib:/usr/lib /bin/sh -c "${VIRTUAL_ENV}/bin/pip install --no-cache-dir -r requirements.txt"
ARG APP_VERSION=""
ARG RELEASE_MODE=false
ARG GITHUB_TOKEN
RUN if [ "${RELEASE_MODE}" = "true" ]; then make release v=${APP_VERSION} githubtoken=${GITHUB_TOKEN}; else if [ "${APP_VERSION}" != "" ]; then make build-release v=${APP_VERSION}; fi ; fi
RUN mkdir /backend \
    && cp /build/VERSION /backend \
    && cp -r /build/app /backend/ \
    && cp -r /build/res /backend/


FROM --platform=${BUILDPLATFORM} bitnami/python:3.10.14
RUN apt-get update && apt-get -y upgrade \
    && apt-get install -y libxml2 libgomp1 tzdata curl libpq5 libpcre3 libpcre3-dev\
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /venv /venv
WORKDIR /backend/
COPY --from=builder /backend ./

# Create a group and user
RUN groupadd uwsgi && useradd -g uwsgi uwsgi
USER uwsgi

EXPOSE 5000
ENV VIRTUAL_ENV="/venv"
# uWSGI configuration (customize as needed):
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}" PYTHONPATH=/backend \
    FLASK_APP=app/main.py UWSGI_WSGI_FILE=app/main.py UWSGI_SOCKET=:3031 UWSGI_HTTP=:5000 \
    UWSGI_VIRTUALENV=${VIRTUAL_ENV} UWSGI_MASTER=1 UWSGI_WORKERS=1 UWSGI_THREADS=1s UWSGI_MAX_FD=10000 UWSGI_LAZY_APPS=1 \
    UWSGI_WSGI_ENV_BEHAVIOR=holy PYTHONDONTWRITEBYTECODE=1
# Start uWSGI
CMD ["/venv/bin/uwsgi", "--http-auto-chunked", "--http-keepalive"]
HEALTHCHECK --interval=1m --timeout=5s --retries=2 CMD ["curl", "-s", "-f", "--show-error", "http://localhost:5000/"]
