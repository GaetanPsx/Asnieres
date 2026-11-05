"""
Étape 5 du RAG : la génération de la réponse.

Le LLM (Ministral via Ollama) reçoit :
  - des CONSIGNES strictes (répondre uniquement avec les extraits, citer, refuser sinon) ;
  - les chunks gardés par retrieve.py, NUMÉROTÉS [1], [2], [3] ;
  - la question de l'usager.
Il rédige une réponse courte avec des citations [1], [2]...

Ensuite, on VÉRIFIE sa réponse (on ne fait pas confiance aveuglément au LLM) :
  - a-t-il refusé ? -> réponse "je ne suis pas en mesure de vous aider"
  - FIDÉLITÉ, phrase par phrase :
      * chaque nombre (horaire, prix, adresse...) doit apparaître dans les extraits ;
      * la phrase doit reprendre assez de mots des extraits (ou de la question) ;
      -> une phrase non vérifiable est RETIRÉE ; s'il ne reste rien -> repli sûr
         ("je n'ai pas cette information précise" + ce que disent vraiment les documents)
  - les numéros cités existent-ils vraiment ? (sinon on les retire)
  - les sources (titre, URL) viennent des MÉTADONNÉES des chunks, jamais du LLM
    -> il ne peut pas inventer un lien.
"""
import re
import unicodedata

from retrieve import MESSAGE_PAS_TROUVE, MODELE_LLM

REFUS = "Je ne suis pas en mesure de vous aider sur ce point. Vous pouvez vous adresser à l'accueil de la mairie."
REPLI = "Je n'ai pas trouvé cette information précise dans les documents de la mairie. Voici ce qu'ils indiquent :"

SEUIL_MOTS = 0.6   # part minimale des mots d'une phrase qu'on doit retrouver dans les extraits (ou la question)

CONSIGNES = f"""Tu es l'assistant d'accueil de la mairie d'Asnières-sur-Seine.
Tu réponds aux usagers UNIQUEMENT à partir des extraits officiels fournis.

Règles strictes :
1. N'utilise QUE les informations écrites dans les extraits. N'ajoute rien de tes connaissances :
   aucun prix, horaire, document, délai ou démarche qui n'est pas écrit dans les extraits.
2. Après chaque information, indique le numéro de l'extrait entre crochets, par exemple [1].
3. Si les extraits ne permettent pas de répondre à la question, réponds exactement : « {REFUS} »
4. Si une information est incomplète dans un extrait (par exemple un horaire coupé par « … »),
   dis qu'elle n'est pas précisée, ne la complète pas.
5. Réponds en français, en 2 à 4 phrases simples, en vouvoyant l'usager.
   Pas de liste, pas de titre, pas de gras.

Exemples (sur d'autres sujets) :

Extraits : [1] Piscine municipale : ouverte du mardi au dimanche de 10h à…
Question : À quelle heure ferme la piscine le dimanche ?
Bonne réponse : L'heure de fermeture de la piscine n'est pas précisée dans les informations dont je dispose. Elle est ouverte du mardi au dimanche à partir de 10h [1].

Extraits : [1] Médiathèque : les inscriptions se font sur place, à l'accueil.
Question : Quels documents faut-il pour s'inscrire à la médiathèque ?
Bonne réponse : La liste des documents à fournir n'est pas précisée dans les informations dont je dispose. L'inscription se fait sur place, à l'accueil de la médiathèque [1]."""

RAPPEL = ("Rappel : n'utilise QUE les extraits ci-dessus, cite [n] après chaque information, "
          "et si une information demandée n'y figure pas, dis qu'elle n'est pas précisée sans l'inventer.")


def construire_prompt(question: str, chunks: list[dict]) -> str:
    extraits = "\n\n".join(f"[{i}] {c['texte']}" for i, c in enumerate(chunks, start=1))
    # le rappel est placé APRÈS la question : les petits modèles suivent mieux ce qui est écrit en dernier
    return f"Extraits officiels :\n\n{extraits}\n\nQuestion de l'usager : {question}\n\n{RAPPEL}"


def est_un_refus(texte: str) -> bool:
    t = texte.lower()
    return "pas en mesure de vous aider" in t or MESSAGE_PAS_TROUVE in t


# ------------------------------------------------------------------------------------------
# Vérification de fidélité
MOTS_VIDES = {
    "vous", "votre", "vos", "nous", "notre", "pour", "dans", "avec", "sans", "sont", "etre", "peut",
    "peuvent", "pouvez", "cette", "comme", "selon", "toutes", "tous", "tout", "plus", "mais", "donc",
    "elle", "elles", "leur", "leurs", "aussi", "tres", "ainsi", "entre", "chez", "dont", "avoir", "avez",
    "devez", "sera", "soit", "deux", "etes", "faut", "fois", "afin", "lors", "ceux", "celle", "celles",
    # verbes / mots de liaison courants dans une réponse, qui n'apportent pas d'information à vérifier
    "faire", "rendre", "personne", "effectuer", "adresser", "situee", "situees", "situe", "situes",
    "disponible", "possible", "ville", "informations", "information", "extrait", "extraits", "indique",
    "indiquee", "indiques", "precise", "precisee", "precises", "precisees", "dispose", "disposons",
}
PHRASES_PRUDENTES = ("pas precise", "pas indique", "ne dispose pas", "pas mentionne", "pas d'information",
                     "pas en mesure")


def sans_accents(t: str) -> str:
    t = unicodedata.normalize("NFD", t.lower().replace("’", "'"))
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def racines(t: str) -> set[str]:
    """Mots de 4 lettres et plus, réduits à leurs 5 premières lettres (passeports ~ passeport, ouvert ~ ouverture)."""
    return {m[:5] for m in re.findall(r"[a-z]+", sans_accents(t)) if len(m) >= 4 and m not in MOTS_VIDES}


def nombres(t: str) -> set[str]:
    return set(re.findall(r"\d+", t))


def phrase_fidele(phrase: str, vocab: set[str], nombres_ok: set[str]) -> tuple[bool, str]:
    p = re.sub(r"\[\d+\]", "", phrase)
    # 1. chaque nombre de la phrase doit exister dans les extraits
    inventes = nombres(p) - nombres_ok
    if inventes:
        return False, f"nombre(s) absent(s) des extraits : {', '.join(sorted(inventes))}"
    # 2. une phrase "prudente" (« n'est pas précisé ») est toujours acceptée
    if any(x in sans_accents(p) for x in PHRASES_PRUDENTES):
        return True, ""
    # 3. assez de mots doivent venir des extraits (ou de la question)
    mots = racines(p)
    if not mots:
        return True, ""
    part = len(mots & vocab) / len(mots)
    if part < SEUIL_MOTS:
        absents = sorted(mots - vocab)
        return False, f"seulement {part:.0%} des mots dans les extraits (absents : {', '.join(absents)})"
    return True, ""


def verifier(texte: str, question: str, chunks: list[dict]) -> tuple[list[str], list[dict]]:
    """Découpe la réponse en phrases et ne garde que celles qu'on peut vérifier dans les extraits."""
    source = " ".join(c["texte"] for c in chunks)
    vocab = racines(source) | racines(question)
    nombres_ok = nombres(source)
    gardees, retirees = [], []
    for phrase in re.split(r"(?<=[.!?])\s+", texte.strip()):
        if not re.sub(r"\[\d+\]|\bet\b|[\s.,;]", "", phrase):   # ligne vide ou juste "[1] et [2]"
            continue
        ok, raison = phrase_fidele(phrase, vocab, nombres_ok)
        (gardees if ok else retirees).append(phrase if ok else {"phrase": phrase, "raison": raison})
    return gardees, retirees


def repli(chunks: list[dict]) -> str:
    """Réponse sûre : on cite directement le meilleur extrait (sans son fil d'Ariane)."""
    c = chunks[0]
    corps = re.sub(r"\s*\n+\s*", " ", c["texte"].split("\n", 1)[-1].strip())
    if len(corps) > 400:
        corps = corps[:400].rsplit(" ", 1)[0] + "…"
    lieu = c["section"].split(" > ")[-1]
    return f"{REPLI} {lieu} : {corps} [1]"


# ------------------------------------------------------------------------------------------
def generer(question: str, chunks: list[dict]) -> dict:
    """Fait rédiger la réponse par le LLM à partir des chunks, puis la vérifie."""
    import ollama

    rep = ollama.chat(
        model=MODELE_LLM,
        messages=[
            {"role": "system", "content": CONSIGNES},
            {"role": "user", "content": construire_prompt(question, chunks)},
        ],
        options={"temperature": 0.1},   # peu de "créativité" : on veut de la fidélité
        keep_alive="30m",
    )
    brut = rep["message"]["content"]
    texte = brut.strip().replace("**", "")

    # 1. Le LLM a refusé ?
    if est_un_refus(texte):
        return {"reponse": REFUS, "sources": [], "trouve": False, "citations_ok": True,
                "fidele": True, "phrases_retirees": [], "brut": brut}

    # 2. Fidélité : on retire les phrases qu'on ne retrouve pas dans les extraits
    gardees, retirees = verifier(texte, question, chunks)
    infos = [p for p in gardees if not any(x in sans_accents(p) for x in PHRASES_PRUDENTES)]
    if not infos:
        # plus aucune information vérifiée -> repli sûr sur le texte officiel
        texte = repli(chunks)
    else:
        texte = " ".join(gardees)

    # 3. Citations : on ne garde que les numéros qui correspondent à un vrai extrait
    cites = sorted({int(n) for n in re.findall(r"\[(\d+)\]", texte)})
    valides = [n for n in cites if 1 <= n <= len(chunks)]
    for n in set(cites) - set(valides):
        texte = texte.replace(f"[{n}]", "")      # citation inventée -> retirée
    texte = re.sub(r"[ \t]+([.,;!?])", r"\1", re.sub(r"[ \t]{2,}", " ", texte))   # espaces laissés

    # 4. Les sources viennent des métadonnées des chunks (jamais du texte du LLM)
    sources = [
        {"numero": n, "section": chunks[n - 1]["section"], "titre": chunks[n - 1]["source_titre"],
         "url": chunks[n - 1]["source_url"]}
        for n in valides
    ]
    return {
        "reponse": texte.strip(),
        "sources": sources,
        "trouve": True,
        "citations_ok": bool(valides),     # False = rien de cité -> réponse à surveiller
        "fidele": not retirees,            # False = des phrases ont été retirées (le LLM a inventé)
        "phrases_retirees": retirees,      # pour le suivi / le débogage (pas affiché à l'usager)
        "brut": brut,
    }