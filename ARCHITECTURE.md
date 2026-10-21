## Guichet citoyen IA — Asnières-sur-Seine

**Statut : propistion en attente de validation**

**Périmètre de la phase 1 : borne tactile uniquement** (l'accès mobile est une évolution future).
> Le même socle logiciel servira ensuite le mobile sans changement d'architecture.


### 1. Principes directeurs

+--------------------------+----------------------------------------------------------------+
| PRINCIPE                 | APPLICATION CONCRETE                                           |
+==========================+================================================================+
| Souveraineté et          | Traitement 100 % local sur l'infrastructure de la Ville. LLM   |
| étanchéité               | hébergé en Europe, sans accès à Internet. La base de           |
|                          | connaissances n'est alimentée que par un processus d'ingestion |
|                          | validé.                                                        |
+--------------------------+----------------------------------------------------------------+
| Séparer le factuel du    | Démarches, pièces justificatives, horaires, adresses et liens  |
| rédactionnel             | vers l'espace citoyen sont stockés dans des tables             |
|                          | structurées. Les cartes affichées sont rendues depuis la base, |
|                          | jamais générées par le LLM. Le modèle ne produit que la phrase |
|                          | d'orientation, avec citations obligatoires.                    |
+--------------------------+----------------------------------------------------------------+
| Refus plutôt             | Si la pertinence de la recherche est sous un seuil, ou si une  |
| qu'invention             | citation est absente du contexte fourni, l'assistant répond    |
|                          | "je ne sais pas" et affiche une carte de contact vers le       |
|                          | service compétent.                                             |
+--------------------------+----------------------------------------------------------------+
| Modèle interchangeable   | Le LLM est appelé via une API compatible OpenAI (vLLM en       |
|                          | local, ou API européenne souveraine). Le benchmark (français   |
|                          | administratif / latence / impact environnemental) se fait sans |
|                          | toucher au code.                                               |
+--------------------------+----------------------------------------------------------------+
| Aucune donnée            | Pas d'authentification (hors périmètre), masquage des données  |
| personnelle conservée    | personnelles avant tout journal, pas d'enregistrement audio    |
|                          | conservé, rétention courte.                                    |
+--------------------------+----------------------------------------------------------------+
| Dégradation maîtrisée    | Si l'inférence tombe, l'API bascule sur la recherche + les     |
|                          | cartes structurées, sans phrase rédigée. L'usager reçoit       |
|                          | toujours la bonne démarche et les bons horaires.               |
+--------------------------+----------------------------------------------------------------+


### 2. Schéma d'ensemble

                    GUICHET CITOYEN IA
                   ASNIÈRES-SUR-SEINE
=============================================================

  1. ACCÈS CITOYEN
  ----------------
  +----------------------------------------------------+
  | Citoyen / Borne tactile                            |
  | Navigateur en mode kiosque                         |
  +--------------------------+-------------------------+
                             |
                             v
  2. RÉSEAU
  ---------
  +----------------------------------------------------+
  | Routeur 5G industriel (CPE)                        |
  | Boucle 5G privée (APN dédié, antenne Axians)       |
  +--------------------------+-------------------------+
                             |
                             v
  +----------------------------------------------------+
  | Passerelle sécurisée                               |
  | Reverse proxy + TLS                                |
  +--------------------------+-------------------------+
                             |
                             v
  3. SERVICES APPLICATIFS
  -----------------------
  +----------------------------------------------------+
  | Front (interface web)                              |
  +--------------------------+-------------------------+
                             |
                             v
  +----------------------------------------------------+
  | Backend / API sécurisée                            |
  +--------------------------+-------------------------+
                             |
                             v
  +----------------------------------------------------+
  | Pipeline RAG                                       |
  | Recherche des passages, génération, sources        |
  +--------------------------+-------------------------+
                             |
               +-------------+-------------+
               |                           |
               v                           v
  +------------------------+  +------------------------+
  | Base vectorielle       |  |        LLM             |
  | municipale             |  |                        |
  +------------+-----------+  +------------------------+
               ^
               |  alimentation à sens unique
               |  (validation humaine avant mise en ligne)
  +------------+-----------+
  | Corpus municipal       |
  | portail, PDF, FAQ      |
  | ingestion validée      |
  +------------------------+




### 3. Rôle des composants

+--------------------------+----------------------------------------------------------------+
| COMPOSANT                | ROLE                                                           |
+==========================+================================================================+
| Borne / Front            | Affiche l'interface web dans un navigateur verrouillé. Aucune  |
|                          | logique métier sur la borne.                                   |
+--------------------------+----------------------------------------------------------------+
| Passerelle               | Seul point d'entrée du serveur. Chiffre les échanges (TLS) et  |
|                          | filtre les requêtes.                                           |
+--------------------------+----------------------------------------------------------------+
| Backend / API            | Reçoit les questions, applique les contrôles et coordonne le   |
|                          | traitement.                                                    |
+--------------------------+----------------------------------------------------------------+
| Pipeline RAG             | Cherche les passages pertinents dans la base, puis demande au  |
|                          | LLM de rédiger la réponse à partir de ces seuls passages.      |
+--------------------------+----------------------------------------------------------------+
| Base vectorielle         | Stocke les documents de la Ville découpés en passages, avec    |
|                          | leur source.                                                   |
+--------------------------+----------------------------------------------------------------+
| LLM                      | Rédige la réponse. Hébergé en Europe, sans accès à Internet.   |
+--------------------------+----------------------------------------------------------------+


### 4. Flux d'une requête

1. Le citoyen pose sa question sur la borne tactile.
2. La requête transite par le routeur 5G, la boucle 5G privée, puis la passerelle.
3. Le front transmet la question au backend / API.
Le backend lance le pipeline RAG.
Le RAG recherche les passages pertinents dans la base vectorielle municipale.
Le RAG envoie ces passages et la question au LLM, qui rédige la réponse.
La réponse revient avec ses sources et s'affiche sur la borne



### 5. Sécurité

- Aucune exposition à Internet : le serveur n'est joignable que par la boucle 5G.
- Navigateur de la borne verrouillé sur l'URL du service.
Le LLM n'a pas d'accès sortant à Internet.
La base n'est jamais accessible directement depuis la borne.
Journaux anonymisés, sauvegardes, mises à jour de sécurité.