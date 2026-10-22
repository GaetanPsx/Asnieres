# Guichet citoyen IA — Curious Lab


Les habitants doivent chercher leurs informations administratives (démarches, horaires, arrêtés, équipements) sur plusieurs supports. Les assistants IA classiques posent des risques : réponses inventées, fuites de données, dépendance à des acteurs hors Europe.

## Objectif

Concevoir un **guichet d'orientation intelligent**, accessible depuis des **bornes tactiles** connectées à une **boucle 5G privée**. Il répond en langage naturel, uniquement à partir de documents officiels de la Ville (IA de type RAG), et renvoie vers la bonne démarche de l'espace citoyen existant.

## Contraintes du projet

- LLM **hébergé exclusivement en Europe**, traitement 100 % local, conforme au RGPD
- Base de connaissances **fermée et vérifiée** : portail de la Ville, guides PDF/Word, FAQ de l'accueil
- Réponses **sourcées**, avec refus de répondre hors du corpus
- Infrastructure hébergée sur les outils de la Ville

## Périmètre de la phase 1

| Inclus | Exclu |
|---|---|
| Borne tactile en quartier pilote | Accès mobile (évolution future) |
| Chat texte et voix, cartes de réponse | Authentification des usagers |
| Pipeline RAG, boucle 5G privée | Suivi de dossiers (reste dans l'espace citoyen) |

## Livrables attendus

1. Étude d'architecture et de faisabilité technique
2. Maquette fonctionnelle (démonstrateur web / borne)
3. Analyse d'impact sécurité et conformité (vie privée, étanchéité de la base)
4. Plan de déploiement et d'expérimentation (feuille de route budgétaire et technique, pilote sur un quartier)
5. Test de charge et de latence de la boucle 5G
6. Dossier d'évaluation comparative des modèles (précision en français administratif, latence, impact environnemental)

## Équipe

| Rôle | Responsabilité |
|---|---|
| Chef de projet / IA | Coordination, relation avec la mairie, cas d'usage |
| IA / RAG | LLM local, embeddings, recherche documentaire |
| Backend / données | API, ingestion des PDF, base de données |
| Frontend / UX | Interface citoyenne, affichage des sources, accessibilité |
| Architecture / sécurité / 5G | Architecture réseau, souveraineté, RGPD, déploiement |

## Documentation

- [Architecture technique](ARCHITECTURE.md)