"""
Étape 2 du RAG : découpage des documents en chunks.

Entrée  : data/raw/*.json      (un fichier par document, produit par scrape.py)
Sortie  : data/chunks/chunks.json   (la liste de tous les chunks, avec leurs métadonnées)

Stratégie :
  1. On découpe par SECTION, grâce aux titres Markdown (#, ##, ###...).
     Chaque lieu / sujet devient un chunk -> chaque chunk parle d'une seule chose.
     Les sous-titres génériques ("Horaires d'ouverture"...) restent dans le chunk de leur lieu.
  2. On ajoute en tête de chaque chunk le "fil d'Ariane" (Page > Section),
     pour qu'il reste compréhensible tout seul.
  3. Si une section est trop longue, on la recoupe par paragraphes.
  4. Si un document n'a aucun titre, on le coupe par paragraphes (taille fixe + chevauchement).

Lancer depuis le dossier rag/ :  python ingest.py
"""
import json
import re
from pathlib import Path

DOSSIER_RAW = Path(__file__).parent / "data" / "raw"
FICHIER_SORTIE = Path(__file__).parent / "data" / "chunks" / "chunks.json"

TAILLE_MAX = 1200        # caractères max par chunk (au-delà, on recoupe)
TAILLE_MIN = 40          # en dessous, le contenu est trop pauvre pour être un chunk utile
CHEVAUCHEMENT = 1        # nb de paragraphes répétés entre 2 morceaux d'une section recoupée

# Sous-titres "génériques" : ils décrivent une partie d'un lieu/sujet, pas un nouveau sujet.
# Ils ne créent PAS de nouveau chunk : ils restent dans le chunk du titre précédent.
SOUS_TITRES_GENERIQUES = {
    "horaires d'ouverture", "horaires", "les démarches", "démarches", "adresse",
    "contact", "contacts", "accès", "tarifs", "informations complémentaires",
}

TITRE_MD = re.compile(r"^(#{1,6})\s+(.*)$")


def normaliser(t: str) -> str:
    return t.strip().lower().replace("’", "'").rstrip(" :")


def nettoyer(texte: str) -> str:
    """Retire le gras Markdown (**) et les lignes de texte répétées deux fois de suite."""
    texte = texte.replace("**", "")
    lignes, precedente = [], None
    for ligne in texte.splitlines():
        cle = ligne.strip()
        if cle and not cle.startswith("#") and cle == precedente:
            continue
        lignes.append(ligne.rstrip())
        if cle:
            precedente = cle
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lignes))


def decouper_en_sections(texte: str) -> list[dict]:
    """
    Découpe un texte Markdown en sections.

    On ne se fie PAS aux niveaux des titres (#, ##, ###...) : sur les sites web ils sont
    souvent incohérents (ex : '#### Mairie annexe Belfort' suivi de '## Mairie annexe Belfort').
    Règles :
      - tout titre non générique ouvre une nouvelle section ;
      - plusieurs titres à la suite sans texte entre eux sont fusionnés (doublons retirés) ;
      - un sous-titre générique ('Horaires d'ouverture'...) reste dans la section en cours.
    """
    sections = []
    titres_en_attente = []   # titres consécutifs pas encore suivis de texte
    titre_section = None
    lignes = []

    def fermer_section():
        corps = "\n".join(lignes).strip()
        if corps:
            sections.append({"titre": titre_section, "corps": corps})
        lignes.clear()

    for ligne in texte.splitlines():
        m = TITRE_MD.match(ligne.strip())
        if m and normaliser(m.group(2)) not in SOUS_TITRES_GENERIQUES:
            titre = m.group(2).strip()
            if not titres_en_attente or normaliser(titres_en_attente[-1]) != normaliser(titre):
                titres_en_attente.append(titre)
            continue
        if titres_en_attente and ligne.strip():
            # du texte arrive après un ou plusieurs titres : nouvelle section
            fermer_section()
            titre_section = " > ".join(titres_en_attente)
            titres_en_attente = []
        lignes.append(m.group(2) if m else ligne)   # sous-titre générique -> gardé comme texte
    fermer_section()
    return sections


def recouper(corps: str) -> list[str]:
    """Recoupe un texte trop long par paragraphes, en gardant un léger chevauchement."""
    paragraphes = [p.strip() for p in re.split(r"\n\s*\n", corps) if p.strip()]
    # pas de lignes vides dans le texte ? on se rabat sur un découpage ligne par ligne
    if len(paragraphes) == 1:
        paragraphes = [l.strip() for l in corps.splitlines() if l.strip()]
    morceaux, courant = [], []
    for p in paragraphes:
        if courant and len("\n\n".join(courant + [p])) > TAILLE_MAX:
            morceaux.append("\n\n".join(courant))
            courant = courant[-CHEVAUCHEMENT:] if CHEVAUCHEMENT else []
        courant.append(p)
    if courant:
        morceaux.append("\n\n".join(courant))
    return morceaux


def chunker_document(doc: dict) -> list[dict]:
    texte = nettoyer(doc["texte"])
    sections = decouper_en_sections(texte)
    if not sections:   # pas de titres du tout : on traite le document comme une seule section
        sections = [{"titre": None, "corps": texte}]

    chunks = []
    for section in sections:
        titre_page = doc.get("titre") or ""
        titre_section = section["titre"]
        if not titre_section or normaliser(titre_section) == normaliser(titre_page):
            fil_ariane = titre_page
        else:
            fil_ariane = f"{titre_page} > {titre_section}" if titre_page else titre_section

        morceaux = [section["corps"]] if len(section["corps"]) <= TAILLE_MAX else recouper(section["corps"])
        for morceau in morceaux:
            if len(morceau) < TAILLE_MIN:
                continue
            chunks.append({
                "id": f"{Path(doc['_fichier']).stem}__{len(chunks):03d}",
                "texte": f"[{fil_ariane}]\n{morceau}",     # <- c'est CE texte qui sera vectorisé
                "section": fil_ariane,
                "source_titre": doc.get("titre"),
                "source_url": doc.get("url"),
                "type": doc.get("type"),
                "date_extraction": doc.get("date_extraction"),
            })
    return chunks


if __name__ == "__main__":
    tous_les_chunks = []
    for fichier in sorted(DOSSIER_RAW.glob("*.json")):
        doc = json.loads(fichier.read_text(encoding="utf-8"))
        doc["_fichier"] = fichier.name
        chunks = chunker_document(doc)
        tous_les_chunks.extend(chunks)
        print(f"{fichier.name} : {len(chunks)} chunks")

    FICHIER_SORTIE.parent.mkdir(parents=True, exist_ok=True)
    FICHIER_SORTIE.write_text(json.dumps(tous_les_chunks, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nTotal : {len(tous_les_chunks)} chunks -> {FICHIER_SORTIE}\n")

    # Aperçu pour vérifier à l'œil
    for c in tous_les_chunks:
        print("=" * 70)
        print(f"{c['id']}  ({len(c['texte'])} caractères)")
        print("-" * 70)
        print(c["texte"])