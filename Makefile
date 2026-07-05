IMAGE_NAME ?= shipit-demo
IMAGE_TAG ?= local
VENV ?= .venv
PYTHON ?= $(VENV)/bin/python

.PHONY: venv run test lint image scan clean localstack-up localstack-down tf-plan tf-apply tf-destroy

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
