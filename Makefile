IMAGE_NAME ?= shipit-demo
IMAGE_TAG ?= local
VENV ?= .venv
PYTHON ?= $(VENV)/bin/python

KIND_CLUSTER ?= ato-demo

.PHONY: venv run test lint image scan clean localstack-up localstack-down tf-plan tf-apply tf-destroy \
	kind-up kind-down policy-test deploy-dev demo drift-check

venv:
	python3.12 -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip
	$(VENV)/bin/pip install -r requirements-dev.txt

run:
	DATABASE_URL=$${DATABASE_URL:-sqlite:///./readiness.db} \
	LOG_LEVEL=$${LOG_LEVEL:-INFO} \
	$(VENV)/bin/uvicorn app.main:app --host 0.0.0.0 --port $${PORT:-8000} --reload

test:
	$(PYTHON) -m pytest

lint:
	$(VENV)/bin/ruff check app

image:
	docker build -t $(IMAGE_NAME):$(IMAGE_TAG) .

scan: image
	trivy image --exit-code 1 --severity CRITICAL $(IMAGE_NAME):$(IMAGE_TAG)

clean:
	rm -rf $(VENV) .pytest_cache .ruff_cache **/__pycache__ readiness.db

localstack-up:
	docker run -d --name localstack -p 4566:4566 \
		-e SERVICES=ec2,sts,iam,s3,dynamodb localstack/localstack:3.8
	until curl -s http://localhost:4566/_localstack/health | grep -q '"s3"'; do sleep 1; done

localstack-down:
	docker rm -f localstack

tf-plan:
	cd terraform && terraform init && terraform plan

tf-apply:
	cd terraform && terraform init && terraform apply

tf-destroy:
	cd terraform && terraform destroy

# Phase 5 — CA-7 continuous monitoring. Same check the scheduled CI job
# runs: exit 0 = clean, exit 2 = drift (see docs/continuous-monitoring.md).
drift-check:
	cd terraform && terraform init && terraform plan -detailed-exitcode

# Phase 4 — kind cluster + Kyverno policy enforcement. Use k3s instead of
# kind here if you already have it running locally (same manifests/policies
# either way); see docs/adr/0005-kind-and-kyverno.md.
kind-up:
	kind create cluster --name $(KIND_CLUSTER) --wait 120s
	helm repo add kyverno https://kyverno.github.io/kyverno/ --force-update
	helm repo update
	helm install kyverno kyverno/kyverno -n kyverno --create-namespace --wait --timeout 180s
	kubectl apply -f policy/
	kubectl wait --for=condition=Ready clusterpolicy --all --timeout=60s

kind-down:
	kind delete cluster --name $(KIND_CLUSTER)

policy-test:
	./policy-tests/run.sh

deploy-dev:
	kubectl create namespace readiness-board-dev --dry-run=client -o yaml | kubectl apply -f -
	kustomize build k8s/overlays/dev | kubectl apply -f -
	kubectl -n readiness-board-dev wait --for=condition=Available deployment/readiness-board --timeout=120s

# End-to-end: spin up kind, enforce Kyverno policy, deploy the real signed
# GHCR image through it. Tears the cluster down after.
demo: kind-up policy-test deploy-dev
	kubectl -n readiness-board-dev get pods -o wide
	@echo
	@echo "Readiness Board is deployed and passed all 5 Kyverno policies."
	@echo "Run 'make kind-down' to tear the cluster down."
