"""
Le RAG complet : question -> recherche (retrieve.py) -> génération (generate.py) -> réponse sourcée.

C'est la fonction repondre(question) que le BACK appellera. Elle renvoie un dictionnaire (= JSON) :
    {
      "question":   "Où faire mon passeport ?",
      "reponse":    "Vous pouvez faire votre passeport sur rendez-vous à la mairie annexe ... [1]",
      "sources":    [{"numero": 1, "section": "...", "titre": "...", "url": "https://..."}],
      "trouve":     true,        # false -> message "je ne suis pas en mesure de vous aider"
      "reformulee": null,        # la question reformulée, si le 1er essai de recherche a échoué
      "citations_ok": true,      # false -> le LLM n'a cité aucun extrait : réponse à surveiller
      "fidele":     true,        # false -> des phrases inventées par le LLM ont été retirées
      "duree_s":    6.2
    }
(format à valider avec la personne du back)

Lancer depuis le dossier rag/ (Docker + rag-db démarrés, Ollama lancé) :
    python rag.py                               -> questions de test
    python rag.py "Où faire mon passeport ?"    -> une question précise
    python rag.py --json "Où faire mon passeport ?"   -> affiche le JSON renvoyé au back
"""
import json
import sys
import time

from generate import REFUS, generer
from retrieve import modeles, rechercher


def repondre(question: str) -> dict:
    t = time.time()
    recherche = rechercher(question)

    if not recherche["trouve"]:
        # Rien de pertinent dans les documents : on ne sollicite même pas le LLM -> aucun risque d'invention
        resultat = {"reponse": REFUS, "sources": [], "trouve": False, "citations_ok": True,
                    "fidele": True, "phrases_retirees": []}
    else:
        resultat = generer(question, recherche["chunks"])

    return {
        "question": question,
        "reponse": resultat["reponse"],
        "sources": resultat["sources"],
        "trouve": resultat["trouve"],
        "reformulee": recherche["reformulee"],
        "citations_ok": resultat["citations_ok"],
        "fidele": resultat["fidele"],
        "phrases_retirees": resultat["phrases_retirees"],   # pour le suivi, pas affiché à l'usager
        "duree_s": round(time.time() - t, 1),
    }


QUESTIONS_TEST = [
    "Où faire mon passeport ?",
    "Quels sont les horaires de l'hôtel de ville ?",
    "Combien y a-t-il de mairies annexes ?",
    "Où demander la carte améthyste ?",
    "Quelle est l'adresse de la mairie annexe Belfort ?",
    "À quelle heure ferme la mairie annexe Belfort l'après-midi ?",   # info tronquée -> ne doit PAS inventer
    "Quels papiers pour refaire ma carte d'identité ?",               # le test "sans RAG" du début
    "Comment inscrire mon enfant à la cantine ?",                      # hors corpus -> refus
]


def afficher(r: dict):
    print("=" * 90)
    print(f"QUESTION : {r['question']}")
    if r["reformulee"]:
        print(f"(reformulée pour la recherche : {r['reformulee']})")
    print("-" * 90)
    print(r["reponse"])
    if r["sources"]:
        print("\nSources :")
        for s in r["sources"]:
            print(f"  [{s['numero']}] {s['section']} — {s['url']}")
    for x in r["phrases_retirees"]:
        print(f"\n🛑 Phrase inventée retirée ({x['raison']}) :\n   « {x['phrase']} »")
    if r["trouve"] and not r["citations_ok"]:
        print("\n⚠️  Aucune citation : réponse à vérifier")
    print(f"\n({r['duree_s']} s)")


if __name__ == "__main__":
    args = sys.argv[1:]
    en_json = "--json" in args
    args = [a for a in args if a != "--json"]
    questions = [" ".join(args)] if args else QUESTIONS_TEST

    modeles()   # chargement des modèles une seule fois
    for q in questions:
        r = repondre(q)
        print(json.dumps(r, ensure_ascii=False, indent=2)) if en_json else afficher(r)
    print("=" * 90)