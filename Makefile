SHELL := /usr/bin/env bash
.PHONY: help setup start run infra build deploy stop status logs clean models reset test smoke uml

help:
	@echo "QuantumBio-LocalMoE - available targets:"
	@echo "  make setup    Create venv, install deps, prepare .env"
	@echo "  make start    Run the API locally with uvicorn"
	@echo "  make run      One-click: setup (if needed) + optional infra + start"
	@echo "  make infra    Start postgres/redis/qdrant via docker compose"
	@echo "  make build    Build the Docker image"
	@echo "  make deploy   Full docker compose stack up"
	@echo "  make stop     Tear down the docker stack"
	@echo "  make status   Show stack + API health"
	@echo "  make logs     Tail engine container logs"
	@echo "  make clean    Stop containers and remove caches/venv"
	@echo "  make reset    Full teardown (-v) + setup + rebuild + deploy"
	@echo "  make test     Run the pytest suite"
	@echo "  make models   List the detected local GGUF/AWQ models"
	@echo "  make smoke    Smoke-test a running API on localhost:8000"
	@echo "  make uml      Render PlantUML diagrams (requires plantuml)"

setup:
	./scripts/unix/setup.sh

start:
	./scripts/unix/start.sh

run:
	./scripts/unix/run.sh

infra:
	./scripts/unix/start_infra.sh

build:
	./scripts/unix/build.sh

deploy:
	./scripts/unix/deploy.sh

stop:
	./scripts/unix/stop.sh

status:
	./scripts/unix/status.sh

logs:
	./scripts/unix/logs.sh

clean:
	./scripts/unix/clean.sh

reset:
	./scripts/unix/reset.sh

test:
	./scripts/unix/test.sh

models:
	./scripts/unix/models.sh list

smoke:
	python scripts/smoke_test.py

uml:
	plantuml -tsvg docs/uml/*.puml -o rendered
	plantuml -tpng docs/uml/*.puml -o rendered