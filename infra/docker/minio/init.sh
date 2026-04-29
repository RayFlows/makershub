#!/bin/sh
set -eu

MINIO_ENDPOINT="${MINIO_ENDPOINT:-http://minio:9000}"
MINIO_ACCESS_KEY="${MINIO_ACCESS_KEY:-makershub}"
MINIO_SECRET_KEY="${MINIO_SECRET_KEY:-makershub_minio}"

echo "Waiting for MinIO at ${MINIO_ENDPOINT}..."
until mc alias set makershub "${MINIO_ENDPOINT}" "${MINIO_ACCESS_KEY}" "${MINIO_SECRET_KEY}" >/dev/null 2>&1
do
  sleep 2
done

create_bucket() {
  bucket_name="$1"
  policy="$2"

  if [ -z "${bucket_name}" ]; then
    return 0
  fi

  echo "Ensuring bucket ${bucket_name} (${policy})..."
  mc mb "makershub/${bucket_name}" --ignore-existing
  mc anonymous set "${policy}" "makershub/${bucket_name}"
}

create_bucket "${MINIO_AVATAR_BUCKET:-makershub-avatars-local}" "none"
create_bucket "${MINIO_PUBLIC_BUCKET:-makershub-public-local}" "public"
create_bucket "${MINIO_RESOURCE_BUCKET:-makershub-resources-local}" "none"
create_bucket "${MINIO_PROJECT_BUCKET:-makershub-projects-local}" "none"
create_bucket "${MINIO_TEMP_BUCKET:-makershub-temp-local}" "none"

echo "MinIO development buckets are ready."
