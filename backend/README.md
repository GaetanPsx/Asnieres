# Démarrage du backend

Le backend du projet est développé en **Python avec FastAPI**.

## Première installation

Ces étapes sont à effectuer uniquement lors de la première utilisation du projet sur votre ordinateur.

### 1. Se placer dans le dossier backend

Depuis la racine du projet :

```powershell
cd backend
```

### 2. Créer l'environnement virtuel Python

```powershell
python -m venv venv
```

Si la commande `python` n'est pas reconnue, essayer :

```powershell
py -m venv venv
```

### 3. Activer l'environnement virtuel

Sous Windows avec PowerShell :

```powershell
.\venv\Scripts\Activate.ps1
```

Lorsque l'environnement est correctement activé, `(venv)` apparaît au début de la ligne du terminal.

Exemple :

```text
(venv) PS C:\...\Asnieres\backend>
```

### 4. Installer les dépendances du projet

```powershell
pip install -r requirements.txt
```

Cette étape installe les bibliothèques nécessaires au backend, notamment FastAPI et Uvicorn.

---

## Démarrer le backend

Une fois la première installation effectuée, il n'est plus nécessaire de refaire les étapes précédentes à chaque lancement.

Se placer dans le dossier backend :

```powershell
cd backend
```

Puis lancer simplement :

```powershell
.\start.ps1
```

Le script démarre automatiquement le backend.

Lorsque le serveur est lancé, le terminal doit afficher une adresse similaire à :

```text
http://127.0.0.1:8000
```

Le backend est alors accessible dans le navigateur à l'adresse :

```text
http://127.0.0.1:8000
```

Pour vérifier que le backend fonctionne correctement :

```text
http://127.0.0.1:8000/health
```

La réponse attendue est :

```json
{
  "status": "ok"
}
```

La documentation interactive de l'API FastAPI est disponible à l'adresse :

```text
http://127.0.0.1:8000/docs
```

Cette interface permet de consulter et tester directement les différentes routes de l'API.

---

## Arrêter le backend

Dans le terminal où le backend est lancé, utiliser :

```text
Ctrl + C
```

---

## Quitter l'environnement virtuel

Si nécessaire, pour sortir manuellement de l'environnement virtuel Python :

```powershell
deactivate
```

---

## Résumé

### Première utilisation

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
.\start.ps1
```

### Utilisations suivantes

```powershell
cd backend
.\start.ps1
```

Backend :

```text
http://127.0.0.1:8000
```

Documentation de l'API :

```text
http://127.0.0.1:8000/docs
```