# TODO produit — SIS + Open edX

## Objectif

Construire une plateforme scolaire et universitaire plus complète que Google
Classroom grâce à l'association du LMS Open edX, des workflows SIS et d'une
expérience adaptée aux élèves, étudiants, enseignants, parents et équipes
administratives.

Une fonctionnalité n'est considérée comme terminée que si son API, ses
permissions, son interface, ses tests et son exploitation en production sont
validés.

## P0 — Rendre la plateforme fiable et déployable

### Contrats et parcours critiques

- [ ] Définir et versionner les contrats API consommés par le MFE.
- [ ] Exposer progressivement les ViewSets existants après validation de leurs
  modèles, serializers, permissions et règles multi-tenant.
- [ ] Terminer un premier parcours vertical : identité Open edX, profil,
  établissement, classe ou formation et inscription.
- [x] Exposer une configuration de l'établissement courant, isolée par tenant et
  réservée aux administrateurs.
- [ ] Aligner les routes et les payloads des portails élève, étudiant,
  enseignant et parent.
- [ ] Remplacer toutes les données de démonstration présentes dans les écrans
  d'administration par des API persistantes.
- [ ] Ajouter des états de chargement, d'erreur et de liste vide à chaque écran.

### Identité et sécurité

- [x] Exiger les secrets Django, OAuth et webhook hors environnement de test.
- [x] Désactiver les valeurs permissives de `DEBUG` et `ALLOWED_HOSTS` par défaut.
- [x] Activer la pagination et la limitation globale des requêtes DRF.
- [x] Réserver la supervision et les commandes de synchronisation aux
  administrateurs.
- [x] Mettre en place une fédération d'identité Open edX vers les SIS pour les
  comptes pré-mappés, avec validation cryptographique des jetons, audience,
  émetteur et expiration.
- [ ] Vérifier l'isolation multi-tenant et les permissions objet sur chaque API.
- [ ] Chiffrer au repos les secrets MFA, coordonnées bancaires et données
  médicales.
- [ ] Finaliser l'inscription MFA, la récupération de compte et la révocation
  des sessions.
- [ ] Valider type, taille et contenu des fichiers téléversés.
- [ ] Journaliser les actions sensibles dans une piste d'audit inviolable.

### Données, intégration et exploitation

- [x] Versionner les migrations initiales des applications métier.
- [x] Exposer les contrôles de santé et de disponibilité.
- [x] Exposer une supervision paginée des mappings et de l'outbox Open edX.
- [x] Préparer l'écran d'administration de l'intégration LMS pour les données
  réelles.
- [x] Activer cet écran après la fédération d'identité Open edX vers les SIS.
- [ ] Fiabiliser les webhooks avec validation de schéma, idempotence et
  événements inconnus rejetés.
- [ ] Publier réellement les événements outbox avec verrouillage, reprise et
  file d'échec.
- [ ] Configurer Celery Beat et le routage explicite des files.
- [ ] Aligner `.env.template`, les settings et les modes secondaire, supérieur
  et dual.
- [ ] Fournir les images, manifests, sauvegardes et procédures de restauration.
- [ ] Publier des métriques Prometheus, tableaux de bord et alertes.

### Qualité

- [ ] Remplacer les tests `pass` par des assertions métier.
- [ ] Tester les permissions par rôle et par tenant.
- [ ] Ajouter des tests de contrat backend–frontend et des parcours E2E.
- [ ] Exécuter le lint, les tests et le build du MFE dans la CI SIS.
- [ ] Définir des seuils de couverture progressifs et bloquants.
- [ ] Rendre les scans de dépendances et de sécurité bloquants.
- [ ] Corriger ou archiver les audits devenus obsolètes.

## P1 — Parité fonctionnelle avec Google Classroom

- [x] Permettre le choix d'un type d'établissement personnalisé, des couleurs,
  du fuseau horaire et des modules actifs depuis le panel.
- [ ] Espaces de classe/cours avec enseignants, co-enseignants et apprenants.
- [ ] Flux de classe : annonces, ressources, thèmes et commentaires modérés.
- [ ] Devoirs avec brouillon, planification, échéance, pièces jointes et
  réutilisation.
- [ ] Remises avec états brouillon/remis/en retard/manquant, versions et
  nouvelle soumission.
- [ ] Barèmes, rubriques réutilisables, commentaires privés et notation en lot.
- [ ] Calendrier unifié des cours, devoirs, examens et événements.
- [ ] Notifications temps réel, courriel, push et préférences par utilisateur.
- [ ] Communication enseignants–apprenants–parents avec règles de confidentialité.
- [ ] Recherche globale, filtres enregistrés, imports et exports.
- [ ] Applications accessibles, responsives, multilingues et compatibles RTL.
- [ ] Fonctionnement dégradé pour les connexions lentes et synchronisation
  différée.

### Examens et évaluations

- [x] Exposer les sessions, épreuves, convocations et résultats SIS existants
  avec filtrage des données nominatives selon le rôle.
- [ ] Synchroniser les examens Open edX avec les sessions et épreuves SIS.
- [ ] Exposer dans le SIS les banques de questions, QCM et compositions Open edX
  sans dupliquer le moteur CAPA.
- [ ] Remonter les notes corrigées automatiquement vers les résultats consolidés.
- [ ] Ajouter les copies écrites numérisées, le double anonymat et les circuits de
  correction/modération.
- [ ] Déporter la génération massive de convocations, notifications et exports
  vers Celery.
- [ ] Tester les volumes réels et supprimer les requêtes N+1 sur tous les tableaux
  de résultats.

### Classes virtuelles et partage

- [x] Permettre à chaque tenant d'activer les classes virtuelles et de choisir un
  fournisseur BigBlueButton, Zoom LTI Pro ou LTI générique.
- [ ] Configurer les secrets fournisseurs uniquement côté serveur Open edX.
- [ ] Relier le paramétrage tenant au framework `course_live` d'Open edX.
- [ ] Activer le partage vidéo public par politique d'établissement et par cours.
- [ ] Exposer les bibliothèques de contenu pour partager et réutiliser des cours
  entre équipes autorisées.
- [ ] Ajouter enregistrements, présence, sous-titres et règles de conservation.

## P2 — Dépasser Google Classroom

- [ ] Parcours complet admission → inscription → apprentissage → diplôme.
- [ ] Pilotage intégré des présences, transports, cantine, internat, santé,
  discipline, bibliothèque et finances.
- [ ] Dossiers parent et apprenant unifiés avec consentements granulaires.
- [ ] Alertes précoces explicables basées sur les absences, résultats et
  progression, avec validation humaine.
- [ ] Parcours personnalisés et recommandations pédagogiques explicables.
- [ ] Diplômes et relevés vérifiables, signés et révocables.
- [ ] Mobilité, stages, mémoires, recherche et insertion professionnelle.
- [ ] Classes virtuelles, discussions et évaluations avancées via Open edX.
- [ ] Interopérabilité OneRoster, LTI, QTI, calendriers et API événementielles.
- [ ] Tableaux de bord institutionnels avec indicateurs anonymisés.

## Prochaines tranches recommandées

1. Relier les capacités activées par tenant aux politiques Open edX et aux menus
   visibles dans le MFE.
2. Livrer le parcours « création d'un examen Open edX → QCM/copie → correction →
   résultat SIS ».
3. Intégrer BigBlueButton comme premier fournisseur de classe virtuelle, puis
   Zoom LTI Pro.
4. Ajouter les tests multi-tenant, de permissions et de charge avant ouverture
   à de grands effectifs.
