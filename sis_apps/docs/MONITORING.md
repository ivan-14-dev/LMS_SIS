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

Chaque variante (secondaire, supérieur) sert tous ses établissements
(tenants django-tenants) depuis le même processus applicatif : un seul point
de scrape par variante couvre donc l'ensemble de ses tenants.

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
