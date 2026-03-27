#!/usr/bin/env bash
#
# pull_s3_data.sh — One-time script to pull HTML and CSV from S3 into app/data.
# Run on any VM that has AWS CLI configured (credentials + region).
#
# Usage:
#   ./pull_s3_data.sh [TARGET_DIR]
#   or
#   DATA_DIR=/path/to/app/data ./pull_s3_data.sh
#
# Examples:
#   cd /home/ubuntu/email-marketing-api && ./scripts/pull_s3_data.sh
#   ./pull_s3_data.sh /home/ubuntu/email-marketing-api/app/data
#

set -e

# Target directory: first argument, or DATA_DIR env, or ./app/data relative to current dir
TARGET_DIR="${1:-${DATA_DIR:-./app/data}}"
S3_BUCKET="${S3_DATA_BUCKET:-${S3_BUCKET:-data.valtunox-ai.com}}"

echo "=============================================="
echo "  S3 data pull → app/data (HTML + CSV only)"
echo "=============================================="
echo "  Bucket:  s3://${S3_BUCKET}/"
echo "  Target:  ${TARGET_DIR}"
echo "=============================================="

if ! command -v aws &>/dev/null; then
  echo "❌ AWS CLI not found. Install it first (e.g. apt install awscli / pip install awscli)."
  exit 1
fi

mkdir -p "${TARGET_DIR}"
echo "📥 Syncing *.html and *.csv from S3 to ${TARGET_DIR} ..."
aws s3 sync "s3://${S3_BUCKET}/" "${TARGET_DIR}/" \
  --exclude "*" \
  --include "*.html" \
  --include "*.csv" \
  --include "job_descriptions/*"

echo "📋 Contents of ${TARGET_DIR}:"
ls -la "${TARGET_DIR}/" || true
echo "✅ Done."
