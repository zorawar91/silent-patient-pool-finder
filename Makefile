.PHONY: help setup db-up db-down db-reset synthea-download synthea-run ingest simulate pipeline clean

SYNTHEA_VERSION = 3.2.0
SYNTHEA_JAR     = synthea/synthea-with-dependencies.jar
SYNTHEA_URL     = https://github.com/synthetichealth/synthea/releases/download/master-branch-latest/synthea-with-dependencies.jar
DATA_DIR        = data/synthetic

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

setup:  ## First-time setup: copy .env, install Python deps
	@[ -f .env ] || cp .env.example .env && echo "Created .env — edit it before continuing"
	pip install -r requirements.txt
	mkdir -p synthea $(DATA_DIR)

db-up:  ## Start PostgreSQL + pgAdmin via Docker
	docker compose up -d
	@echo "PostgreSQL ready on localhost:5432"
	@echo "pgAdmin UI at http://localhost:5050  (admin@sppf.local / admin)"

db-down:  ## Stop containers (data preserved)
	docker compose down

db-reset:  ## ⚠️  Wipe and recreate the database
	docker compose down -v
	docker compose up -d

synthea-download:  ## Download the Synthea JAR (~150 MB)
	@mkdir -p synthea
	@[ -f $(SYNTHEA_JAR) ] && echo "Synthea already downloaded" || \
		(echo "Downloading Synthea..." && curl -L $(SYNTHEA_URL) -o $(SYNTHEA_JAR) && echo "Done")

synthea-run: synthea-download  ## Generate synthetic patients (uses SYNTHEA_PATIENT_COUNT from .env)
	@export $$(cat .env | grep -v '^#' | xargs) && \
	java -jar $(SYNTHEA_JAR) \
		-p $${SYNTHEA_PATIENT_COUNT:-1000} \
		$${SYNTHEA_STATE:-Massachusetts} \
		-c synthea/synthea.properties \
		--exporter.csv.export=true \
		--exporter.baseDirectory=$(DATA_DIR) \
		--exporter.fhir.export=false \
		--exporter.ccda.export=false \
		--exporter.text.export=false
	@echo "Synthetic data written to $(DATA_DIR)/csv/"

ingest:  ## Load Synthea CSVs into PostgreSQL
	python3 src/ingestion/ingest_synthea.py

simulate:  ## Generate synthetic OTC pharmacy transactions
	python3 src/ingestion/simulate_otc.py

pipeline: synthea-run ingest simulate  ## Run the full M1 pipeline end-to-end

clean:  ## Remove generated data files (keeps DB)
	rm -rf $(DATA_DIR)/csv $(DATA_DIR)/fhir
