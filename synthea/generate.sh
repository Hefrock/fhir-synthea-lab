#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

SYNTHEA_VERSION="3.3.0"
JAR_PATH="$SCRIPT_DIR/synthea-with-dependencies.jar"
JAR_URL="https://github.com/synthetichealth/synthea/releases/download/v${SYNTHEA_VERSION}/synthea-with-dependencies.jar"

SEED="${SYNTHEA_SEED:-42}"
POPULATION="${SYNTHEA_POPULATION:-50}"
STATE="${SYNTHEA_STATE:-Massachusetts}"

if [ ! -f "$JAR_PATH" ]; then
  echo "Downloading Synthea v${SYNTHEA_VERSION}..."
  curl -fL -o "$JAR_PATH" "$JAR_URL"
else
  echo "Synthea jar already present at $JAR_PATH"
fi

cd "$REPO_ROOT"

java -jar "$JAR_PATH" \
  -s "$SEED" \
  -p "$POPULATION" \
  -c synthea/synthea.properties \
  "$STATE"
