"""
Récupère des pages du site de la ville et en extrait le contenu principal
(sans menus, cookies, pied de page). Résultat : un fichier JSON par page dans data/raw/.
 
Lancer depuis le dossier rag/ :  python scrape.py
"""
import json
import re
from datetime import date
from pathlib import Path
 
import requests
import trafilatura
 
# Pages à récupérer (on en ajoutera d'autres plus tard, via le sitemap)
URLS = [
    "https://asnieres-sur-seine.fr/votre-mairie/informations-pratiques",
]
 
DOSSIER_SORTIE = Path(__file__).parent / "data" / "raw"
DOSSIER_SORTIE.mkdir(parents=True, exist_ok=True)
 
 
def nom_de_fichier(url: str) -> str:
    """'.../votre-mairie/informations-pratiques' -> 'votre-mairie_informations-pratiques.json'"""
    chemin = url.split("asnieres-sur-seine.fr/")[-1].strip("/")
    return re.sub(r"[^a-z0-9-]+", "_", chemin.lower()) + ".json"
 
 
def recuperer(url: str) -> dict:
    # 1. Télécharger le HTML de la page
    reponse = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0 (projet etudiant RAG Asnieres)"})
    reponse.raise_for_status()
 
    # 2. Extraire le contenu principal (trafilatura enlève menus, cookies, footer...)
    resultat = trafilatura.extract(
        reponse.text,
        url=url,
        output_format="json",
        with_metadata=True,
        include_tables=True,    # les horaires sont parfois dans des tableaux
        include_links=False,
        favor_recall=True,      # préférer garder un peu trop de texte que d'en perdre
    )
    if resultat is None:
        raise ValueError(f"Aucun contenu extrait pour {url}")
    meta = json.loads(resultat)
 
    # Le texte en Markdown garde les titres (# , ## , ###) : ingest.py s'en sert pour découper par section
    texte_md = trafilatura.extract(
        reponse.text,
        url=url,
        output_format="markdown",
        include_tables=True,
        include_links=False,
        include_formatting=True,
        favor_recall=True,
    )
 
    # 3. Garder uniquement ce qui nous sert, au format qu'utilisera ingest.py
    return {
        "url": url,
        "titre": meta.get("title"),
        "date_extraction": date.today().isoformat(),
        "type": "page_web",
        "texte": texte_md or meta.get("text", ""),
    }
 
 
if __name__ == "__main__":
    for url in URLS:
        doc = recuperer(url)
        fichier = DOSSIER_SORTIE / nom_de_fichier(url)
        fichier.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
 
        print(f"OK  {doc['titre']}  ->  {fichier.name}  ({len(doc['texte'])} caractères)")
        print("-" * 60)
        print(doc["texte"][:1500])
        print("-" * 60)
 