#!/usr/bin/env bash
set -euo pipefail

FHIR_BASE=${FHIR_BASE_URL:-http://localhost:8080/fhir}
BUNDLE_DIR=${SYNTHEA_OUTPUT_DIR:-./synthea/output/fhir}

# Load hospital/practitioner bundles first so patient references resolve correctly
infra_bundles=$(find "$BUNDLE_DIR" -name "hospital*.json" -o -name "practitioner*.json" | sort)
patient_bundles=$(find "$BUNDLE_DIR" -name "*.json" | grep -Ev "(hospital|practitioner)" | sort)
bundles=$(printf '%s\n%s' "$infra_bundles" "$patient_bundles" | grep -v '^$')

total=$(echo "$bundles" | wc -l | tr -d ' ')
count=0
errors=0

echo "Loading $total bundles into $FHIR_BASE"

while IFS= read -r bundle; do
  count=$((count + 1))
  filename=$(basename "$bundle")

  http_code=$(curl -s -o /tmp/fhir_response.json -w "%{http_code}" \
    -X POST "$FHIR_BASE" \
    -H "Content-Type: application/fhir+json" \
    -d @"$bundle")

  if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ]; then
    echo "[$count/$total] OK $filename"
  else
    echo "[$count/$total] FAIL $filename (HTTP $http_code)"
    if [ -f /tmp/fhir_response.json ]; then
      echo "  HAPI response: $(head -c 800 /tmp/fhir_response.json)"
    fi
    errors=$((errors + 1))
  fi
done <<< "$bundles"

echo ""
echo "Done. $((total - errors))/$total bundles loaded successfully."
[ "$errors" -eq 0 ] || exit 1
