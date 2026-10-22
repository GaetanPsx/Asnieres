"""
Étape 3 du RAG : embedding des chunks + stockage dans PostgreSQL (pgvector).

Entrée  : data/chunks/chunks.json   (produit par ingest.py)
Sortie  : la table "chunks" dans PostgreSQL, une ligne par chunk :
          texte + vecteur + métadonnées (source, URL, section, date...)

Prérequis : Docker lancé et le conteneur rag-db démarré  ->  docker start rag-db

Lancer depuis le dossier rag/ :  python index.py
"""
import json
import os
import time
from pathlib import Path

import psycopg
from pgvector.psycopg import register_vector

FICHIER_CHUNKS = Path(__file__).parent / "data" / "chunks" / "chunks.json"

# Connexion à la base (le conteneur rag-db écoute sur le port 5433 de ton PC)
DB_URL = os.getenv("RAG_DB_URL", "host=localhost port=5433 user=postgres password=rag dbname=postgres")

# Modèle d'embedding : le MÊME devra être utilisé pour vectoriser les questions (retrieve.py)
MODELE_EMBEDDING = "intfloat/multilingual-e5-base"   # vecteurs de dimension 768
DEVICE = "cpu"   # ta carte graphique est occupée par le LLM (Ollama)


def charger_modele():
    from sentence_transformers import SentenceTransformer
    print(f"Chargement du modèle {MODELE_EMBEDDING} (téléchargé au 1er lancement, ~1 Go)...")
    return SentenceTransformer(MODELE_EMBEDDING, device=DEVICE)


def vectoriser(modele, textes: list[str]):
    # e5 attend le préfixe "passage: " devant les documents (et "query: " devant les questions)
    return modele.encode(
        [f"passage: {t}" for t in textes],
        normalize_embeddings=True,   # vecteurs de longueur 1 -> la distance cosinus est fiable
        show_progress_bar=True,
    )


def creer_table(conn, dimension: int):
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    register_vector(conn)
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS chunks (
            id              text PRIMARY KEY,
            texte           text NOT NULL,
            section         text,
            source_titre    text,
            source_url      text,
            type            text,
            date_extraction date,
            embedding       vector({dimension}) NOT NULL,
            -- index plein texte en français, calculé automatiquement (servira à la recherche hybride)
            tsv             tsvector GENERATED ALWAYS AS (to_tsvector('french', texte)) STORED
        )
    """)
    # Index pour que la recherche de vecteurs proches reste rapide avec beaucoup de chunks
    conn.execute("CREATE INDEX IF NOT EXISTS chunks_embedding_idx ON chunks USING hnsw (embedding vector_cosine_ops)")
    conn.execute("CREATE INDEX IF NOT EXISTS chunks_tsv_idx ON chunks USING gin (tsv)")


def inserer(conn, chunks: list[dict], vecteurs):
    # On vide puis on remplit : relancer le script donne toujours une base à jour, sans doublons
    conn.execute("TRUNCATE chunks")
    with conn.cursor() as cur:
        cur.executemany(
            """INSERT INTO chunks (id, texte, section, source_titre, source_url, type, date_extraction, embedding)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            [
                (c["id"], c["texte"], c.get("section"), c.get("source_titre"), c.get("source_url"),
                 c.get("type"), c.get("date_extraction"), v)
                for c, v in zip(chunks, vecteurs)
            ],
        )


if __name__ == "__main__":
    chunks = json.loads(FICHIER_CHUNKS.read_text(encoding="utf-8"))
    print(f"{len(chunks)} chunks à indexer")

    # 1. Embedding
    t = time.time()
    modele = charger_modele()
    vecteurs = vectoriser(modele, [c["texte"] for c in chunks])
    print(f"Embedding OK : {len(vecteurs)} vecteurs de dimension {vecteurs.shape[1]} ({time.time() - t:.1f}s)")

    # 2. Stockage dans PostgreSQL
    with psycopg.connect(DB_URL, autocommit=True) as conn:
        creer_table(conn, vecteurs.shape[1])
        inserer(conn, chunks, vecteurs)

        # 3. Vérification : ce qu'il y a maintenant dans la table
        print("\nContenu de la table chunks :")
        for id_, section, n in conn.execute(
            "SELECT id, section, length(texte) FROM chunks ORDER BY id"
        ).fetchall():
            print(f"  {id_}  ({n} car.)  {section}")
        total = conn.execute("SELECT count(*) FROM chunks").fetchone()[0]
        print(f"\n{total} chunks stockés dans PostgreSQL.")