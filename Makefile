.PHONY: validate figures availability campaign posthoc reproduce docker-build docker-validate

validate:
	bash scripts/run_experiments.sh validate

figures:
	bash scripts/run_experiments.sh figures

availability:
	bash scripts/run_experiments.sh availability

campaign:
	bash scripts/run_experiments.sh campaign

posthoc:
	bash scripts/run_experiments.sh posthoc

reproduce:
	bash scripts/run_experiments.sh reproduce

docker-build:
	docker build -t pbt-greenhouse-anomaly-replication:latest .

docker-validate:
	docker run --rm pbt-greenhouse-anomaly-replication:latest bash scripts/run_experiments.sh validate
