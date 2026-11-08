# syntax=docker/dockerfile:1

# A runtime, not an installation. This image carries the interpreter and the two
# binaries tier 2 needs (ssh, git) and nothing else: the checkout is mounted at
# /repo, so REPO_ROOT resolves to the mount and `instance/` stays the operator's
# files under their own git history. Copying the toolkit in would give the image
# a second `instance/` and a second source of truth; see docs/decisions/D14.
#
#   docker run --rm -v "$PWD:/repo" ghcr.io/niels-emmer/runsheet:1.0.0 status

FROM python:3.12-alpine

# openssh-client is tier 2's transport. git is only for the audit entry's commit
# column (without it apply records an em dash rather than failing).
# ca-certificates keeps an https station reachable.
RUN apk add --no-cache ca-certificates git openssh-client \
    && adduser -D -u 10001 -h /home/runsheet runsheet

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /repo

# Unprivileged by default: the tool never needs root, and the station it reads
# is remote. On Linux, pass --user "$(id -u):$(id -g)" so files it writes into
# the mounted checkout stay yours.
USER 10001:10001

LABEL org.opencontainers.image.title="runsheet" \
      org.opencontainers.image.description="Operate a SUB/WAVE station from an agent session" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.source="https://github.com/niels-emmer/runsheet" \
      org.opencontainers.image.documentation="https://github.com/niels-emmer/runsheet#readme"

ENTRYPOINT ["python3", "scripts/runsheet.py"]
