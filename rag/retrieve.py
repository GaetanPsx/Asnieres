"""
Étape 4 du RAG : la recherche des chunks pertinents pour une question.

  1. Embedding de la question (même modèle que les chunks, préfixe "query: ")
  2. Recherche VECTORIELLE  : les chunks les plus proches par le sens   (opérateur <=> de pgvector)
  3. Recherche MOTS-CLÉS    : les chunks qui contiennent les mots exacts (colonne tsv, en français)
  4. FUSION des listes (méthode RRF)
  5. RERANKER : relit chaque paire (question reformulée, chunk) et donne un score de pertinence précis
  6. SEUIL : si le meilleur score est trop faible -> on considère que l'info n'est pas dans les documents

  Si rien ne passe le seuil avec la question d'origine -> 2e essai : le LLM REFORMULE la question
  (ex : "Où faire mon passeport ?" -> question plus explicite) et on refait les étapes 1 à 6.
  La reformulation ne sert donc QUE pour les questions difficiles : les autres gardent leur précision
  et ne paient pas le temps d'un appel au LLM.

Lancer depuis le dossier rag/ (Docker + rag-db démarrés, Ollama lancé) :
    python retrieve.py                              -> lance les questions de test
    python retrieve.py "Où faire mon passeport ?"   -> teste une question précise
"""
import sys
import time

import psycopg
from pgvector.psycopg import register_vector

# On réutilise la config d'index.py : c'est OBLIGATOIREMENT le même modèle d'embedding
from index import DB_URL, DEVICE, MODELE_EMBEDDING

MODELE_RERANKER = "BAAI/bge-reranker-v2-m3"   # multilingue, ~2,3 Go téléchargés au 1er lancement
# Alternative plus légère (~0,5 Go) si ton disque est plein : "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
MODELE_LLM = "ministral-3:3b"                 # via Ollama, sert ici à reformuler la question

REFORMULER = True    # 2e essai avec reformulation si le 1er échoue (False pour comparer)
K_CANDIDATS = 20     # nb de chunks récupérés par chaque recherche (vectorielle / mots-clés)
K_FINAL = 3          # nb de chunks gardés après le reranker (ceux qu'on donnera au LLM)
SEUIL = 0.30         # score reranker minimum (entre 0 et 1) pour considérer qu'on a trouvé. À ajuster avec les tests !

MESSAGE_PAS_TROUVE = "je ne suis pas en mesure de vous aider"

PROMPT_REFORMULATION = """Tu reformules des questions d'usagers pour le moteur de recherche de la mairie d'Asnières-sur-Seine.
Réécris la question en UNE phrase courte (20 mots maximum), plus explicite, qui garde EXACTEMENT le même sens.

Règles strictes :
- garde tous les mots importants de l'usager (noms de lieux, de démarches, de documents) ;
- n'ajoute AUCUNE information : pas de lieu, d'horaire, de prix, de définition, pas de parenthèse ;
- si tu ne connais pas un mot, recopie-le tel quel sans l'expliquer ;
- ne change pas le type de question (« combien » reste « combien », « où » reste « où ») ;
- pas de mise en forme (pas de gras, pas de guillemets), pas d'explication.

Exemples :
Question : horaires piscine ?
Reformulation : Quels sont les horaires d'ouverture de la piscine municipale d'Asnières-sur-Seine ?
Question : je veux me marier
Reformulation : Quelles sont les démarches pour se marier à la mairie d'Asnières-sur-Seine ?

Question : {question}
Reformulation :"""

_embedder = None
_reranker = None


def modeles():
    """Charge les modèles une seule fois (c'est l'étape la plus lente)."""
    global _embedder, _reranker
    if _embedder is None:
        from sentence_transformers import CrossEncoder, SentenceTransformer
        print("Chargement des modèles (embedding + reranker)...")
        _embedder = SentenceTransformer(MODELE_EMBEDDING, device=DEVICE)
        _reranker = CrossEncoder(MODELE_RERANKER, device=DEVICE)
        if REFORMULER:
            # On charge le LLM dès le début (sinon le 1er appel paie tout le temps de chargement)
            print(f"Chargement du LLM {MODELE_LLM} dans Ollama...")
            try:
                import ollama
                ollama.chat(model=MODELE_LLM, messages=[{"role": "user", "content": "Bonjour"}],
                            options={"num_predict": 1}, keep_alive="30m")
            except Exception as e:
                print(f"(Ollama injoignable : {e} -> pas de reformulation possible)")
    return _embedder, _reranker


def reformuler(question: str) -> str:
    """Demande au LLM une version plus explicite de la question. En cas de problème : question d'origine."""
    try:
        import ollama
        rep = ollama.chat(
            model=MODELE_LLM,
            messages=[{"role": "user", "content": PROMPT_REFORMULATION.format(question=question)}],
            options={"temperature": 0},
            keep_alive="30m",   # le modèle reste chargé 30 min (pas de rechargement à chaque question)
        )
        texte = rep["message"]["content"].strip().splitlines()[0]
        # on retire la mise en forme que le modèle ajoute parfois (**gras**, guillemets, "Reformulation :")
        texte = texte.replace("**", "").replace("*", "").strip().strip('"«» ')
        texte = texte.removeprefix("Reformulation :").strip()
        return texte or question
    except Exception as e:
        print(f"(reformulation impossible : {e} -> on garde la question d'origine)")
        return question


def vectoriser_question(question: str):
    embedder, _ = modeles()
    return embedder.encode(f"query: {question}", normalize_embeddings=True)


def recherche_vectorielle(conn, vecteur, k=K_CANDIDATS) -> list[dict]:
    lignes = conn.execute(
        """SELECT id, texte, section, source_titre, source_url,
                  embedding <=> %s AS distance          -- distance cosinus : 0 = même sens
           FROM chunks
           ORDER BY distance
           LIMIT %s""",
        (vecteur, k),
    ).fetchall()
    return [dict(zip(["id", "texte", "section", "source_titre", "source_url", "distance"], l)) for l in lignes]


def recherche_mots_cles(conn, question: str, k=K_CANDIDATS) -> list[dict]:
    # plainto_tsquery transforme la question en mots-clés français ("passeports" -> "passeport",
    # mots vides retirés). On remplace les ET (&) par des OU (|) : un chunk qui contient
    # une partie des mots doit aussi remonter.
    lignes = conn.execute(
        """WITH q AS (
               SELECT replace(plainto_tsquery('french', %s)::text, '&', '|')::tsquery AS requete
           )
           SELECT id, texte, section, source_titre, source_url, ts_rank(tsv, q.requete) AS score_mots
           FROM chunks, q
           WHERE q.requete::text <> '' AND tsv @@ q.requete
           ORDER BY score_mots DESC
           LIMIT %s""",
        (question, k),
    ).fetchall()
    return [dict(zip(["id", "texte", "section", "source_titre", "source_url", "score_mots"], l)) for l in lignes]


def fusion_rrf(listes: dict[str, list[dict]], k: int = 60) -> list[dict]:
    """Reciprocal Rank Fusion : un chunk bien classé dans une des listes (ou dans plusieurs) remonte."""
    fusion = {}
    for nom_liste, liste in listes.items():
        for rang, chunk in enumerate(liste, start=1):
            c = fusion.setdefault(chunk["id"], {**chunk, "rrf": 0.0})
            c.update({kk: vv for kk, vv in chunk.items() if kk not in c})
            c[nom_liste] = min(rang, c.get(nom_liste, rang))
            c["rrf"] += 1 / (k + rang)
    return sorted(fusion.values(), key=lambda c: c["rrf"], reverse=True)


def reranker(question: str, candidats: list[dict]) -> list[dict]:
    _, modele = modeles()
    scores = modele.predict([(question, c["texte"]) for c in candidats])
    for c, s in zip(candidats, scores):
        c["score"] = float(s)
    return sorted(candidats, key=lambda c: c["score"], reverse=True)


def une_recherche(question_recherche: list[str], question_reranker: str, k_final: int) -> tuple[list, list]:
    """Recherche hybride (avec une ou plusieurs formulations) + reranker + seuil."""
    listes = {}
    with psycopg.connect(DB_URL) as conn:
        register_vector(conn)
        for i, q in enumerate(question_recherche):
            listes[f"rang_vecteur_{i}"] = recherche_vectorielle(conn, vectoriser_question(q))
            listes[f"rang_mots_{i}"] = recherche_mots_cles(conn, q)

    candidats = fusion_rrf(listes)
    for c in candidats:   # rang affiché = le meilleur rang obtenu avec l'une ou l'autre formulation
        c["rang_vecteur"] = min([v for k, v in c.items() if k.startswith("rang_vecteur_")], default="-")
        c["rang_mots"] = min([v for k, v in c.items() if k.startswith("rang_mots_")], default="-")

    classes = reranker(question_reranker, candidats) if candidats else []
    # on garde au plus k_final chunks, et seulement ceux qui passent le seuil
    meilleurs = [c for c in classes[:k_final] if c["score"] >= SEUIL]
    return meilleurs, classes


def rechercher(question: str, k_final: int = K_FINAL) -> dict:
    """La fonction principale : question -> les meilleurs chunks (+ indique si on a trouvé)."""
    # 1er essai : la question telle quelle
    meilleurs, classes = une_recherche([question], question, k_final)
    reformulee = None

    # 2e essai (seulement si rien trouvé) : on fait reformuler la question par le LLM
    if not meilleurs and REFORMULER:
        reformulee = reformuler(question)
        if reformulee != question:
            meilleurs, classes = une_recherche([question, reformulee], reformulee, k_final)

    return {"question": question, "reformulee": reformulee, "trouve": bool(meilleurs),
            "chunks": meilleurs, "tous": classes}


# ---------------------------------------------------------------------------------------------
# Test : pour chaque question, on sait quel chunk DOIT remonter (avec une seule page, c'est facile)
QUESTIONS_TEST = [
    ("Où faire mon passeport ?", "Belfort ou Hauts d'Asnières"),
    ("Quels sont les horaires de l'hôtel de ville ?", "Mairie - Hôtel de ville"),
    ("Combien y a-t-il de mairies annexes ?", "Les mairies annexes"),
    ("Où demander la carte améthyste ?", "Belfort ou Hauts d'Asnières"),
    ("Quelle est l'adresse de la mairie annexe Belfort ?", "Mairie annexe Belfort"),
    ("Comment inscrire mon enfant à la cantine ?", f"AUCUN -> doit répondre '{MESSAGE_PAS_TROUVE}'"),
]


def afficher(resultat: dict, attendu: str | None = None, duree: float | None = None):
    print("=" * 90)
    print(f"QUESTION   : {resultat['question']}")
    if resultat["reformulee"]:
        print(f"REFORMULÉE : {resultat['reformulee']}   (1er essai sans résultat suffisant)")
    if attendu:
        print(f"ATTENDU    : {attendu}")
    print(f"TROUVÉ     : {'OUI' if resultat['trouve'] else 'NON -> ' + MESSAGE_PAS_TROUVE}"
          + (f"   ({duree:.1f}s)" if duree else ""))
    print("-" * 90)
    print(f"{'score':>6} {'dist.':>6} {'r.vect':>6} {'r.mots':>6}  section")
    for c in resultat["tous"]:
        marque = "  <- gardé" if c in resultat["chunks"] else ""
        dist = f"{c['distance']:.3f}" if "distance" in c else "  -  "
        print(f"{c['score']:>6.3f} {dist:>6} {c['rang_vecteur']:>6} {c['rang_mots']:>6}  {c['section']}{marque}")


if __name__ == "__main__":
    modeles()  # chargement une fois au début (pour que les temps affichés soient ceux de la recherche)
    questions = [(" ".join(sys.argv[1:]), None)] if len(sys.argv) > 1 else QUESTIONS_TEST
    for question, attendu in questions:
        t = time.time()
        res = rechercher(question)
        afficher(res, attendu, time.time() - t)
    print("=" * 90)
    print(f"score = reranker (0 à 1, seuil {SEUIL}) | dist. = distance cosinus (0 = même sens) | "
          "r.vect / r.mots = meilleur rang dans les recherches")