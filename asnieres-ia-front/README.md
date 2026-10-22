## Installation

Depuis la racine du dépôt, installez les dépendances du projet :

```powershell
cd .\guichet-asnieres
npm install
```

Le projet utilise l'Angular CLI installé localement ; il n'est pas nécessaire
d'installer `@angular/cli` globalement. Pour démarrer l'application :

```powershell
npm start
```

## Tailwind CSS

Le projet utilise Tailwind CSS 4 avec l'intégration PostCSS d'Angular.
La configuration se trouve dans `guichet-asnieres/.postcssrc.json` et
`guichet-asnieres/src/styles.css`. Avec Tailwind 4, `npx tailwindcss init`
n'est plus utilisé ; ajoutez `@import "tailwindcss";` aux styles globaux et
utilisez les classes Tailwind dans les templates Angular.

## Dépannage de `Cannot read properties of null (reading 'edgesOut')`

Cette erreur peut provenir d'un plantage interne de npm pendant la résolution
des dépendances, et non du code Angular. Si elle survient, mettez npm à jour,
vérifiez son cache, puis relancez l'installation depuis `guichet-asnieres` :

```powershell
npm install -g npm@11
npm cache verify
npm install
```
