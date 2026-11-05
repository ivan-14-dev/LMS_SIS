# Monitoring Prometheus / Grafana (SIS Secondaire / SIS Supérieur)

Les deux variantes SIS exposent des métriques métier réelles au format
d'exposition Prometheus sur `GET /metrics/` (voir
`sis_secondaire/apps/core/healthcheck.py` et
`sis_superieur/apps/core/healthcheck.py`, dépendance `prometheus_client`).
Ce document décrit comment les exploiter avec Prometheus et Grafana à partir
des artefacts fournis dans `sis_apps/monitoring/`.

## Métriques exposées

| Métrique | Type | Description |
| --- | --- | --- |
| `sis_users_total` | Gauge | Nombre total d'utilisateurs du tenant courant. |
| `sis_users_active` | Gauge | Nombre d'utilisateurs actifs (`is_active=True`). |
| `sis_edx_mappings_active` | Gauge | Mappings d'identité Open edX actifs. |
| `sis_edx_enrollments_active` | Gauge | Inscriptions Open edX actives. |
| `sis_outbox_events_pending` | Gauge | Événements outbox en attente de publication. |
| `sis_outbox_events_failed` | Gauge | Événements outbox en échec (retentables). |
| `sis_outbox_events_dead` | Gauge | Événements outbox en échec définitif (file morte). |
| `sis_metrics_scrape_timestamp_seconds` | Gauge | Horodatage Unix de la génération de la réponse `/metrics/`. |

Chaque réponse décrit **uniquement le tenant sélectionné par le Host HTTP**.
Il faut une cible par établissement et par variante ; partager un processus ne
rend pas les métriques globales. Un Host inconnu renvoie 404.

La distribution Compose bloque `/metrics/` sur le proxy public. Le collecteur
doit rejoindre le réseau privé, avec une résolution DNS du nom du tenant vers
l'API interne, ou passer par un proxy de supervision privé qui fixe le Host et
`X-Forwarded-Proto: https` lorsque la redirection HTTPS est activée. Ne publiez
pas le port Gunicorn pour contourner cette protection.

## Supervision manuelle de la file LMS

Dans **Intégration LMS → File d'attente**, un administrateur peut demander le
traitement des événements admissibles de l'établissement courant :
`POST /api/v1/integration/outbox/process/` avec le corps JSON `{}` (aucun
paramètre de sélection de tenant, d'événement ou de version accepté).
Une réponse **202** et un `task_id` confirment uniquement la mise en file Celery,
pas l'exécution ni la synchronisation. Une indisponibilité du broker renvoie
**503**, est journalisée et ne supprime aucun événement.

Le worker réutilise le publisher durable existant, limité à 100 événements par
appel et au tenant enregistré. Les réservations unitaires, verrous de décision,
versions, clôtures conditionnelles et délais de reprise sont conservés.
Les échecs définitifs ne sont pas rejoués ; aucune purge n'est exposée.
Actualiser la table permet de suivre les résultats.

**Voir les échecs** applique un filtre paginé côté serveur
(`GET /api/v1/integration/outbox/?statut=failed&statut=dead&page=1`).
Les reprises transitoires, dont les retraits d'accès en attente, restent dans
la vue de tous les événements. Les détails affichent l'erreur complète en
lecture seule, sans créer une nouvelle décision d'accès.

## Artefacts fournis

- `monitoring/prometheus/scrape_config.yml` : fragment `scrape_configs` +
  `rule_files` à fusionner dans la configuration Prometheus de
  l'environnement cible (adapter les `targets` aux adresses réelles des
  services `sis-secondaire` / `sis-superieur`).
- `monitoring/prometheus/alerts.yml` : règles d'alerte Prometheus portant
  uniquement sur les métriques ci-dessus (disponibilité des cibles, file
  outbox en échec/morte/en accumulation, perte de la fédération d'identité
  EDX).
- `monitoring/grafana/sis-dashboard.json` : tableau de bord Grafana
  (schemaVersion 39) à importer via *Dashboards > Import*, avec une variable
  de gabarit `job` filtrant entre `sis-secondaire` et `sis-superieur`.

## Installation

```bash
# 1. Copier/fusionner les fragments dans la configuration Prometheus
cp sis_apps/monitoring/prometheus/alerts.yml /etc/prometheus/rules/sis-alerts.yml
# fusionner scrape_configs et rule_files de scrape_config.yml dans prometheus.yml,
# en adaptant les `targets` à l'environnement (Kubernetes Service, IP, etc.)

# 2. Recharger Prometheus
curl -X POST http://localhost:9090/-/reload

# 3. Importer le tableau de bord dans Grafana
# Interface web : Dashboards > New > Import > coller le contenu de
# monitoring/grafana/sis-dashboard.json, puis sélectionner la source de
# données Prometheus correspondante.
```

## Limites actuelles

- Les API ont une sonde PostgreSQL/Redis ; les workers ont une sonde Celery
  ciblant leur propre nœud. Beat reste à superviser par ses journaux et
  l'exécution effective des tâches planifiées : un processus vivant ne prouve
  pas qu'une tâche métier s'exécute.
- Surveiller aussi disque libre, expiration TLS, erreurs SMTP, ancienneté du
  dernier snapshot réussi et copie hors machine. Définir responsables,
  destinataires et délais d'intervention avant l'ouverture aux utilisateurs.
- Ces alertes couvrent uniquement les métriques métier déjà instrumentées.
  Aucune métrique de latence/volume HTTP par vue (`django_prometheus` ou
  équivalent) n'est actuellement exposée ; en ajouter si un suivi des temps
  de réponse par endpoint est requis.
- `SISEdxMappingsDroppedToZero` peut se déclencher par erreur avant la mise
  en place initiale de la fédération d'identité Open edX sur un nouvel
  environnement : désactiver ou ajuster cette règle tant que la fédération
  n'est pas encore configurée.
- Les cibles (`targets`), l'organisation des dossiers Grafana, et la
  politique de notification (Alertmanager, routes, destinataires) restent à
  définir par environnement de déploiement ; ces artefacts fournissent le
  socle applicatif, pas l'orchestration d'exploitation complète.
