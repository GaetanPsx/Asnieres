"""
Étape 2 du RAG : découpage des documents en chunks.

Entrée  : data/raw/*.json           (un fichier par document, produit par scrape.py)
Sortie  : data/chunks/chunks.json   (la liste de tous les chunks, avec leurs métadonnées)

Stratégie :
  1. On découpe par SECTION, grâce aux titres Markdown (#, ##, ###...).
     Chaque lieu / sujet devient un chunk -> chaque chunk parle d'une seule chose.
     Les sous-titres génériques ("Horaires d'ouverture"...) restent dans le chunk de leur lieu.
  2. On "rédige" les listes à puces : elles deviennent des phrases
     ("Les démarches sur rendez-vous : attestation d'accueil, passeport.").
     Le reranker (et plus tard le LLM) comprend beaucoup mieux une phrase qu'un mot isolé dans une liste.
  3. On ajoute en tête de chaque chunk le "fil d'Ariane" (Page > Section),
     pour qu'il reste compréhensible tout seul.
  4. Si une section est trop longue, on la recoupe par paragraphes.

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
PUCE = re.compile(r"^(\s*)[-*]\s+(.*)$")


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


def rediger(corps: str) -> str:
    """
    Transforme les listes à puces en phrases, et colle les sous-titres génériques à leur contenu.

      Les démarches :                     Les démarches sur rendez-vous : Attestation d'accueil,
      - sur rendez-vous :          ->       Carte nationale d'identité, Passeport.
        - Attestation d'accueil           Les démarches sans rendez-vous : Carte améthyste.
        - Carte nationale d'identité
        - Passeport                       Horaires d'ouverture : Du lundi au vendredi de 8h30 à 17h30
      - sans rendez-vous :
        - Carte améthyste

      Horaires d'ouverture
      Du lundi au vendredi de 8h30 à 17h30
    """
    lignes = corps.splitlines()
    sortie = []
    i = 0
    while i < len(lignes):
        ligne = lignes[i]
        if not PUCE.match(ligne):
            sortie.append(ligne)
            i += 1
            continue

        # 1. On récupère tout le bloc de liste (les lignes vides entre deux puces en font partie)
        items = []   # [(texte de l'item, [sous-items])]
        while i < len(lignes):
            m = PUCE.match(lignes[i])
            if m:
                texte = m.group(2).strip()
                if len(m.group(1)) == 0 or not items:
                    items.append((texte, []))
                else:
                    items[-1][1].append(texte)
                i += 1
            elif not lignes[i].strip() and i + 1 < len(lignes) and PUCE.match(lignes[i + 1]):
                i += 1
            else:
                break

        # 2. Le texte juste avant la liste se termine par ":" ? ("Les démarches :") -> on le fusionne
        intro = None
        while sortie and not sortie[-1].strip():
            sortie.pop()
        if sortie and sortie[-1].strip().endswith(":"):
            intro = sortie.pop().strip().rstrip(" :")

        # 3. On écrit les phrases
        feuilles = [t.rstrip(" :") for t, enfants in items if not enfants]
        if feuilles:
            debut = f"{intro} : " if intro else ""
            sortie.append(f"{debut}{', '.join(feuilles)}.")
        for texte, enfants in items:
            if enfants:
                etiquette = texte.rstrip(" :")
                if intro:
                    etiquette = f"{intro} {etiquette}"
                sortie.append(f"{etiquette} : {', '.join(enfants)}.")
        sortie.append("")

    # Sous-titre générique seul sur sa ligne + texte juste après -> "Horaires d'ouverture : Du lundi..."
    resultat = []
    for ligne in sortie:
        if resultat and ligne.strip() and normaliser(resultat[-1]) in SOUS_TITRES_GENERIQUES \
                and not resultat[-1].strip().endswith("."):
            resultat[-1] = f"{resultat[-1].strip().rstrip(' :')} : {ligne.strip()}"
        elif ligne.strip() or (resultat and resultat[-1].strip()):
            if resultat and not ligne.strip() and normaliser(resultat[-1]) in SOUS_TITRES_GENERIQUES:
                continue   # pas de ligne vide entre un sous-titre et son contenu
            resultat.append(ligne)
    return "\n".join(resultat).strip()


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

        corps = rediger(section["corps"])
        morceaux = [corps] if len(corps) <= TAILLE_MAX else recouper(corps)
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