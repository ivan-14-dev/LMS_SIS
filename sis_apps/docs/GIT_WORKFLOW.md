# Workflow Git - SIS Secondaire & Supérieur

## Structure des branches

```
main                          # Branche principale (production)
├── develop                   # Branche de développement
├── feature/sis-secondaire/*  # Features spécifiques au SIS Secondaire
├── feature/sis-superieur/*   # Features spécifiques au SIS Supérieur
├── feature/shared/*          # Features partagées (core, integration)
├── bugfix/*                  # Corrections de bugs
└── release/*                 # Branches de release
```

## Conventions de nommage

| Type | Pattern | Exemple |
|------|---------|---------|
| Feature SIS Secondaire | `feature/sis-secondaire/<description>` | `feature/sis-secondaire/add-cantine-module` |
| Feature SIS Supérieur | `feature/sis-superieur/<description>` | `feature/sis-superieur/add-ects-calculator` |
| Feature partagée | `feature/shared/<description>` | `feature/shared/improve-edx-sync` |
| Bugfix | `bugfix/<issue-id>-<description>` | `bugfix/42-fix-enrollment-sync` |
| Hotfix | `hotfix/<description>` | `hotfix/critical-auth-fix` |
| Release | `release/v<version>` | `release/v1.0.0` |

## Workflow quotidien

### 1. Créer une nouvelle feature

```bash
# Toujours partir de main à jour
git checkout main
git pull origin main

# Créer la branche selon le SIS concerné
git checkout -b feature/sis-secondaire/add-bulletin-pdf

# Travailler sur la feature...
git add .
git commit -m "feat(sis-secondaire): add PDF bulletin generation"

# Pousser la branche
git push -u origin feature/sis-secondaire/add-bulletin-pdf
```

### 2. Créer une Pull Request

1. Aller sur GitHub
2. Créer une PR vers `main` (ou `develop` si configuré)
3. Ajouter les reviewers
4. Attendre la validation CI/CD
5. Merger (squash recommandé)

### 3. Après le merge

```bash
# Supprimer la branche locale
git checkout main
git pull origin main
git branch -d feature/sis-secondaire/add-bulletin-pdf

# Supprimer la branche distante (si pas fait automatiquement)
git push origin --delete feature/sis-secondaire/add-bulletin-pdf
```

## Exemples de commits conventionnels

```bash
# Features
git commit -m "feat(sis-secondaire): add attendance tracking module"
git commit -m "feat(sis-superieur): implement ECTS calculation"
git commit -m "feat(integration): add webhook signature validation"

# Fixes
git commit -m "fix(sis-secondaire): correct grade calculation formula"
git commit -m "fix(sis-superieur): handle null enrollment date"

# Documentation
git commit -m "docs: update API documentation for notes endpoint"

# Refactoring
git commit -m "refactor(core): simplify middleware chain"

# Tests
git commit -m "test(integration): add sync service unit tests"

# Chores
git commit -m "chore: update dependencies to latest versions"
```

## Protection de branche (recommandé)

Configurer sur GitHub (`Settings > Branches > Branch protection rules`) :

### Pour `main` :
- ✅ Require pull request before merging
- ✅ Require approvals (1 minimum)
- ✅ Require status checks to pass (CI)
- ✅ Require branches to be up to date
- ✅ Do not allow bypassing the above settings

## Scripts utiles

### Créer une branche feature rapidement

```bash
# Ajouter à ~/.bashrc ou ~/.zshrc
function sis-feature() {
    local sis=$1
    local name=$2
    if [[ -z "$sis" || -z "$name" ]]; then
        echo "Usage: sis-feature <secondaire|superieur|shared> <feature-name>"
        return 1
    fi
    git checkout main
    git pull origin main
    git checkout -b "feature/sis-$sis/$name"
    echo "Created branch: feature/sis-$sis/$name"
}

# Usage:
# sis-feature secondaire add-transport-module
# sis-feature superieur fix-jury-calculation
# sis-feature shared improve-logging
```

### Synchroniser avec upstream (Open edX)

```bash
# Récupérer les mises à jour d'Open edX
git fetch upstream

# Voir les différences
git log main..upstream/master --oneline

# Merger les mises à jour (avec précaution)
git checkout main
git merge upstream/master

# Résoudre les conflits si nécessaire, puis pousser
git push origin main
```

## CI/CD (GitHub Actions suggéré)

Créer `.github/workflows/ci.yml` :

```yaml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  test-sis-secondaire:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: |
          cd sis_apps/sis_secondaire
          pip install -r requirements/base.txt
      - name: Run tests
        run: |
          cd sis_apps/sis_secondaire
          pytest --cov=apps

  test-sis-superieur:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: |
          cd sis_apps/sis_superieur
          pip install -r requirements/base.txt
      - name: Run tests
        run: |
          cd sis_apps/sis_superieur
          pytest --cov=apps

  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run flake8
        run: |
          pip install flake8
          flake8 sis_apps/ --max-line-length=120
```
