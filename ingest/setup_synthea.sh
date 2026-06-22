#!/usr/bin/env bash
# Download the Synthea jar and generate 1,000 synthetic patients.
# Run from the ingest/ directory. Outputs patients.csv + conditions.csv to ../data/synthea/
set -e

JAR="synthea-with-dependencies.jar"
POPULATION=1000
DATA_DIR="../data/synthea"

if [ ! -f "$JAR" ]; then
    echo "Downloading Synthea jar..."
    curl -L -o "$JAR" \
        "https://github.com/synthetichealth/synthea/releases/latest/download/synthea-with-dependencies.jar"
fi

echo "Generating $POPULATION synthetic patients (CSV output only)..."
java -jar "$JAR" \
    -p $POPULATION \
    --exporter.csv.export=true \
    --exporter.fhir.export=false \
    --exporter.hospital.fhir.export=false \
    --exporter.practitioner.fhir.export=false

mkdir -p "$DATA_DIR"
cp output/csv/patients.csv "$DATA_DIR/"
cp output/csv/conditions.csv "$DATA_DIR/"

echo "Done. Files written to $DATA_DIR/"
echo "  $(wc -l < "$DATA_DIR/patients.csv") patient rows"
echo "  $(wc -l < "$DATA_DIR/conditions.csv") condition rows"
