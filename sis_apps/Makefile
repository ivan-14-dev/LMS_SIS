# =============================================================================
# Makefile - SIS Secondaire & Supérieur
# =============================================================================
# Usage: make <target>
# =============================================================================

.PHONY: help install migrations migrate test lint run-secondaire run-superieur run-dual celery clean

# Variables
PYTHON = python
PIP = pip
PYTEST = pytest

# Couleurs
GREEN  := $(shell tput setaf 2)
YELLOW := $(shell tput setaf 3)
RED    := $(shell tput setaf 1)
RESET  := $(shell tput sgr0)

# =============================================================================
# AIDE
# =============================================================================

help: ## Affiche cette aide
	@echo "$(GREEN)SIS - Commandes disponibles$(RESET)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(RESET) %s\n", $$1, $$2}'

# =============================================================================
# INSTALLATION
# =============================================================================

install-secondaire: ## Installe les dépendances SIS Secondaire
	cd sis_secondaire && $(PIP) install -r requirements/base.txt

install-superieur: ## Installe les dépendances SIS Supérieur
	cd sis_superieur && $(PIP) install -r requirements/base.txt

install: install-secondaire install-superieur ## Installe toutes les dépendances

# =============================================================================
# MIGRATIONS
# =============================================================================

migrations-secondaire: ## Génère les migrations SIS Secondaire
	@echo "$(GREEN)Génération des migrations SIS Secondaire...$(RESET)"
	cd sis_secondaire && $(PYTHON) manage.py makemigrations core
	cd sis_secondaire && $(PYTHON) manage.py makemigrations etablissement
	cd sis_secondaire && $(PYTHON) manage.py makemigrations utilisateurs
	cd sis_secondaire && $(PYTHON) manage.py makemigrations classes
	cd sis_secondaire && $(PYTHON) manage.py makemigrations enseignants
	cd sis_secondaire && $(PYTHON) manage.py makemigrations eleves
	cd sis_secondaire && $(PYTHON) manage.py makemigrations salles
	cd sis_secondaire && $(PYTHON) manage.py makemigrations emplois_du_temps
	cd sis_secondaire && $(PYTHON) manage.py makemigrations presences
	cd sis_secondaire && $(PYTHON) manage.py makemigrations evaluations
	cd sis_secondaire && $(PYTHON) manage.py makemigrations notes
	cd sis_secondaire && $(PYTHON) manage.py makemigrations bulletins
	cd sis_secondaire && $(PYTHON) manage.py makemigrations examens
	cd sis_secondaire && $(PYTHON) manage.py makemigrations conseil_classe
	cd sis_secondaire && $(PYTHON) manage.py makemigrations discipline
	cd sis_secondaire && $(PYTHON) manage.py makemigrations paiements
	cd sis_secondaire && $(PYTHON) manage.py makemigrations cantine
	cd sis_secondaire && $(PYTHON) manage.py makemigrations transport
	cd sis_secondaire && $(PYTHON) manage.py makemigrations internat
	cd sis_secondaire && $(PYTHON) manage.py makemigrations bibliotheque
	cd sis_secondaire && $(PYTHON) manage.py makemigrations infirmerie
	cd sis_secondaire && $(PYTHON) manage.py makemigrations clubs
	cd sis_secondaire && $(PYTHON) manage.py makemigrations stages
	cd sis_secondaire && $(PYTHON) manage.py makemigrations portail_parent
	cd sis_secondaire && $(PYTHON) manage.py makemigrations portail_enseignant
	cd sis_secondaire && $(PYTHON) manage.py makemigrations portail_eleve
	cd sis_secondaire && $(PYTHON) manage.py makemigrations integration
	@echo "$(GREEN)✓ Migrations SIS Secondaire générées$(RESET)"

migrations-superieur: ## Génère les migrations SIS Supérieur
	@echo "$(GREEN)Génération des migrations SIS Supérieur...$(RESET)"
	cd sis_superieur && $(PYTHON) manage.py makemigrations core
	cd sis_superieur && $(PYTHON) manage.py makemigrations etablissement
	cd sis_superieur && $(PYTHON) manage.py makemigrations utilisateurs
	cd sis_superieur && $(PYTHON) manage.py makemigrations structure
	cd sis_superieur && $(PYTHON) manage.py makemigrations formations
	cd sis_superieur && $(PYTHON) manage.py makemigrations ue_ecue
	cd sis_superieur && $(PYTHON) manage.py makemigrations etudiants
	cd sis_superieur && $(PYTHON) manage.py makemigrations inscriptions
	cd sis_superieur && $(PYTHON) manage.py makemigrations ects
	cd sis_superieur && $(PYTHON) manage.py makemigrations mobilite
	cd sis_superieur && $(PYTHON) manage.py makemigrations emplois_du_temps
	cd sis_superieur && $(PYTHON) manage.py makemigrations notes
	cd sis_superieur && $(PYTHON) manage.py makemigrations examens
	cd sis_superieur && $(PYTHON) manage.py makemigrations rattrapages
	cd sis_superieur && $(PYTHON) manage.py makemigrations jurys
	cd sis_superieur && $(PYTHON) manage.py makemigrations releves
	cd sis_superieur && $(PYTHON) manage.py makemigrations diplomes
	cd sis_superieur && $(PYTHON) manage.py makemigrations memoires
	cd sis_superieur && $(PYTHON) manage.py makemigrations stages
	cd sis_superieur && $(PYTHON) manage.py makemigrations bourses
	cd sis_superieur && $(PYTHON) manage.py makemigrations paiements
	cd sis_superieur && $(PYTHON) manage.py makemigrations recherche
	cd sis_superieur && $(PYTHON) manage.py makemigrations bibliotheque
	cd sis_superieur && $(PYTHON) manage.py makemigrations entreprises
	cd sis_superieur && $(PYTHON) manage.py makemigrations enseignants
	cd sis_superieur && $(PYTHON) manage.py makemigrations maquettes
	cd sis_superieur && $(PYTHON) manage.py makemigrations portail_etudiant
	cd sis_superieur && $(PYTHON) manage.py makemigrations portail_enseignant
	cd sis_superieur && $(PYTHON) manage.py makemigrations portail_doyen
	cd sis_superieur && $(PYTHON) manage.py makemigrations portail_scolarite
	cd sis_superieur && $(PYTHON) manage.py makemigrations integration
	@echo "$(GREEN)✓ Migrations SIS Supérieur générées$(RESET)"

migrations: migrations-secondaire migrations-superieur ## Génère toutes les migrations

migrate-secondaire: ## Applique les migrations SIS Secondaire
	@echo "$(GREEN)Application des migrations SIS Secondaire...$(RESET)"
	cd sis_secondaire && $(PYTHON) manage.py migrate_schemas --shared
	cd sis_secondaire && $(PYTHON) manage.py migrate_schemas --tenant
	@echo "$(GREEN)✓ Migrations SIS Secondaire appliquées$(RESET)"

migrate-superieur: ## Applique les migrations SIS Supérieur
	@echo "$(GREEN)Application des migrations SIS Supérieur...$(RESET)"
	cd sis_superieur && $(PYTHON) manage.py migrate_schemas --shared
	cd sis_superieur && $(PYTHON) manage.py migrate_schemas --tenant
	@echo "$(GREEN)✓ Migrations SIS Supérieur appliquées$(RESET)"

migrate: migrate-secondaire migrate-superieur ## Applique toutes les migrations

# =============================================================================
# TESTS
# =============================================================================

test-secondaire: ## Lance les tests SIS Secondaire
	cd sis_secondaire && $(PYTEST) -v

test-superieur: ## Lance les tests SIS Supérieur
	cd sis_superieur && $(PYTEST) -v

test: test-secondaire test-superieur ## Lance tous les tests

test-coverage: ## Lance les tests avec couverture
	cd sis_secondaire && $(PYTEST) --cov=apps --cov-report=html
	cd sis_superieur && $(PYTEST) --cov=apps --cov-report=html

# =============================================================================
# QUALITÉ CODE
# =============================================================================

lint-secondaire: ## Vérifie le code SIS Secondaire
	cd sis_secondaire && flake8 apps/ --max-line-length=120

lint-superieur: ## Vérifie le code SIS Supérieur
	cd sis_superieur && flake8 apps/ --max-line-length=120

lint: lint-secondaire lint-superieur ## Vérifie tout le code

# =============================================================================
# SERVEURS DE DÉVELOPPEMENT
# =============================================================================

run-secondaire: ## Lance le serveur SIS Secondaire (port 8000)
	cd sis_secondaire && $(PYTHON) manage.py runserver 0.0.0.0:8000

run-superieur: ## Lance le serveur SIS Supérieur (port 8001)
	cd sis_superieur && $(PYTHON) manage.py runserver 0.0.0.0:8001

run-dual: ## Lance les deux serveurs en parallèle
	@echo "$(YELLOW)Lancement des deux SIS...$(RESET)"
	@echo "  SIS Secondaire: http://localhost:8000"
	@echo "  SIS Supérieur:  http://localhost:8001"
	cd sis_secondaire && $(PYTHON) manage.py runserver 0.0.0.0:8000 & \
	cd sis_superieur && $(PYTHON) manage.py runserver 0.0.0.0:8001

# =============================================================================
# CELERY
# =============================================================================

celery-secondaire: ## Lance Celery worker SIS Secondaire
	cd sis_secondaire && celery -A config worker -l info -Q secondaire

celery-superieur: ## Lance Celery worker SIS Supérieur
	cd sis_superieur && celery -A config worker -l info -Q superieur

celery-beat: ## Lance Celery Beat (scheduler)
	cd sis_superieur && celery -A config beat -l info

# =============================================================================
# UTILITAIRES
# =============================================================================

shell-secondaire: ## Shell Django SIS Secondaire
	cd sis_secondaire && $(PYTHON) manage.py shell

shell-superieur: ## Shell Django SIS Supérieur
	cd sis_superieur && $(PYTHON) manage.py shell

superuser-secondaire: ## Crée un superuser SIS Secondaire
	cd sis_secondaire && $(PYTHON) manage.py createsuperuser

superuser-superieur: ## Crée un superuser SIS Supérieur
	cd sis_superieur && $(PYTHON) manage.py createsuperuser

static-secondaire: ## Collecte les fichiers statiques SIS Secondaire
	cd sis_secondaire && $(PYTHON) manage.py collectstatic --noinput

static-superieur: ## Collecte les fichiers statiques SIS Supérieur
	cd sis_superieur && $(PYTHON) manage.py collectstatic --noinput

static: static-secondaire static-superieur ## Collecte tous les fichiers statiques

schema-secondaire: ## Génère le schéma OpenAPI SIS Secondaire
	cd sis_secondaire && $(PYTHON) manage.py spectacular --file ../docs/openapi_secondaire.yaml

schema-superieur: ## Génère le schéma OpenAPI SIS Supérieur
	cd sis_superieur && $(PYTHON) manage.py spectacular --file ../docs/openapi_superieur.yaml

schema: schema-secondaire schema-superieur ## Génère tous les schémas OpenAPI

# =============================================================================
# NETTOYAGE
# =============================================================================

clean: ## Nettoie les fichiers temporaires
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name "htmlcov" -exec rm -rf {} +
	find . -type f -name ".coverage" -delete

clean-migrations: ## Supprime les migrations (ATTENTION: perte de données)
	@echo "$(RED)ATTENTION: Cette commande supprime toutes les migrations!$(RESET)"
	@read -p "Êtes-vous sûr? [y/N] " confirm && [ "$$confirm" = "y" ]
	find sis_secondaire/apps -path "*/migrations/*.py" -not -name "__init__.py" -delete
	find sis_superieur/apps -path "*/migrations/*.py" -not -name "__init__.py" -delete

# =============================================================================
# DOCKER
# =============================================================================

docker-build: ## Construit les images Docker
	docker-compose build

docker-up: ## Lance les containers Docker
	docker-compose up -d

docker-down: ## Arrête les containers Docker
	docker-compose down

docker-logs: ## Affiche les logs Docker
	docker-compose logs -f

# =============================================================================
# HEALTH CHECK
# =============================================================================

check-db: ## Vérifie la connexion à la base de données
	cd sis_secondaire && $(PYTHON) manage.py check --database default
	cd sis_superieur && $(PYTHON) manage.py check --database default

check-edx: ## Vérifie la connexion à Open edX
	cd sis_superieur && $(PYTHON) manage.py shell -c "from apps.integration.edx_client import get_edx_client; print(get_edx_client().health_check())"

check: check-db check-edx ## Vérifie toutes les connexions
