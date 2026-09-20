# Déploiement des intégrations LMS/SIS

## BigBlueButton

Configurer côté LMS les variables `BIG_BLUE_BUTTON_GLOBAL_URL`,
`BIG_BLUE_BUTTON_GLOBAL_KEY` et `BIG_BLUE_BUTTON_GLOBAL_SECRET`. Ne jamais
enregistrer ces secrets dans un établissement SIS ni les transmettre au
navigateur.

Dans le cours Open edX :

1. activer l'application avancée `big_blue_button` ;
2. autoriser le partage du nom d'utilisateur LTI ;
3. depuis le panel SIS, activer les classes virtuelles, sélectionner
   `bigbluebutton`, puis lancer la synchronisation du cours mappé ;
4. vérifier la création et l'accès à une réunion avec un compte enseignant et
   un compte apprenant.

Les enregistrements et leur durée de conservation doivent être configurés sur
le serveur BigBlueButton selon la politique de l'établissement.

## Notes détaillées Open edX

Activer le signal dans la configuration LMS :

```yaml
FEATURES:
  ENABLE_COURSE_ASSESSMENT_GRADE_CHANGE_SIGNAL: true
```

Déclarer les destinations dans les tokens LMS. Le secret doit correspondre au
secret webhook du tenant SIS :

```yaml
SIS_GRADE_WEBHOOK_TARGETS:
  - url: https://sis.example.org/api/v1/integration/webhook/lms/
    secret: valeur-fournie-par-le-gestionnaire-de-secrets
    course_ids:
      - course-v1:Organisation+Cours+Session
```

`course_ids` est facultatif. Sans ce champ, la destination reçoit tous les
cours. Hors mode debug, les URL non HTTPS sont ignorées. Redémarrer LMS et les
workers Celery après modification, puis contrôler les retries et la file
d'échec. Le mapping cours, utilisateur et sous-section vers évaluation doit
exister dans le tenant avant l'import.

## Copies écrites

Définir `PRIVATE_EXAM_STORAGE_ROOT` sur un volume non servi par le proxy web et
`EXAM_COPY_MAX_SIZE` selon la capacité retenue. Le téléchargement doit
exclusivement passer par l'API authentifiée ; aucune route `/media/` ne doit
exposer ce volume.

Sauvegarder et chiffrer ce volume séparément, limiter ses permissions au
processus SIS et tester régulièrement une restauration. Le contrôle antivirus
est requis avant une ouverture à des fichiers provenant directement
d'utilisateurs non fiables.

Le parcours d'exploitation est : candidat présent, dépôt PDF, affectation
anonyme d'un ou deux correcteurs, soumission de toutes les corrections,
modération, puis publication du résultat. Une note de modération différente de
la moyenne exige un motif.

## Tests de charge

Exécuter uniquement sur une plateforme de test isolée avec des données
synthétiques. Le script ne requiert aucune dépendance supplémentaire.

```bash
export SIS_LOAD_BEARER_TOKEN='jeton-de-test'
python sis_apps/load_tests/run.py exam-list \
  --url https://sis-test.example.org/api/v1/examens/convocations/ \
  --requests 10000 --concurrency 100 --max-p95-ms 2000

export SIS_LOAD_WEBHOOK_SECRET='secret-de-test'
python sis_apps/load_tests/run.py grade-webhook \
  --url https://sis-test.example.org/api/v1/integration/webhook/lms/ \
  --requests 1000 --concurrency 20 --max-p95-ms 1000
```

Une campagne échoue si le succès descend sous 99 % ou si le p95 dépasse le
seuil fourni. Surveiller simultanément PostgreSQL, Redis, les workers Celery,
la mémoire et la profondeur des files. Les 5 000 copies doivent utiliser des
PDF synthétiques sans données personnelles et être supprimées après le test.
