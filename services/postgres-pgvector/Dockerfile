# Custom PostgreSQL 17 image for Verolas with the pgvector extension.
# The CloudNativePG project distributes vanilla and minimal images; pgvector is
# not pre installed. We extend the standard CNPG image and add the official
# Debian packaged extension build at the same major version.
#
# Built and pushed by the image workflow at .github/workflows/image.yml.
# Image is consumed by infra/k8s/postgres/cluster-*.yaml via the imageName field.

FROM ghcr.io/cloudnative-pg/postgresql:17

USER root

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    postgresql-17-pgvector \
  && rm -rf /var/lib/apt/lists/*

USER 26
