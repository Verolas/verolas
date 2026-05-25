# Custom PostgreSQL 17 image for Verolas with the pgvector extension.
# The CloudNativePG project distributes vanilla and minimal images; pgvector is
# not pre installed. We extend the standard CNPG image and add the official
# Debian packaged extension build at the same major version.
#
# Built and pushed by the image workflow at .github/workflows/image.yml.
# Image is consumed by infra/k8s/postgres/cluster-*.yaml via the imageName field.

FROM ghcr.io/cloudnative-pg/postgresql:17

USER root

# Upgrade the base packages so OS-level CVEs in the upstream cloudnative-pg
# image (libgnutls30 etc.) get the latest Debian security patches, then add
# pgvector. The upstream image lags patches by days; --pull on the build action
# only refreshes the FROM layer, not the packages inside it.
RUN apt-get update \
  && apt-get -y upgrade \
  && apt-get install -y --no-install-recommends postgresql-17-pgvector \
  && pip install --upgrade --no-cache-dir 'urllib3>=2.7.0' 'requests>=2.32.6' \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

USER 26
