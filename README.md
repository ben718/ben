# Ben – démonstration de site fonctionnel

Ce dépôt contient deux éléments principaux :

* un utilitaire Python pour analyser des dates ISO 8601 avec quelques
  tolérances supplémentaires (`src/datetime_utils.py`) ;
* une mini application web WSGI sans dépendance externe (`src/webapp.py`)
  qui sert un configurateur OmadaBOM interactif en quatre étapes
  (capture Simple/Avancée, calcul dynamique de la BOM, indicateurs PoE et
  OPEX).

## Lancer le site

```bash
python -m webapp --host 0.0.0.0 --port 8000
```

Vous pouvez ensuite visiter <http://localhost:8000> pour voir le site.

La page d'accueil affiche automatiquement la branche et le dernier commit
Git détectés. Si aucune information n'apparaît, initialisez ou mettez à jour
votre dépôt avec `git init`, `git add` puis `git commit`.

## Tests

```bash
pytest
```