# Ben – démonstration de site fonctionnel

Ce dépôt contient deux éléments principaux :

* un utilitaire Python pour analyser des dates ISO 8601 avec quelques
  tolérances supplémentaires (`src/datetime_utils.py`) ;
* une mini application web WSGI sans dépendance externe (`src/webapp.py`)
  qui sert un configurateur OmadaBOM interactif en quatre étapes, relié à
  un moteur Python réalisant les calculs de sizing et la génération du
  dossier téléchargeable (BOM, synthèse technique, port-map, plan VLAN).

## Lancer le site

```bash
python -m webapp --host 0.0.0.0 --port 8000
```

Vous pouvez ensuite visiter <http://localhost:8000> pour voir le site et
utiliser le configurateur. Le moteur Python situé derrière `/api/generate`
alimente la synthèse affichée à l'écran, et l'endpoint `/api/download`
retourne une archive ZIP contenant les livrables.

La page d'accueil affiche automatiquement la branche et le dernier commit
Git détectés. Si aucune information n'apparaît, initialisez ou mettez à jour
votre dépôt avec `git init`, `git add` puis `git commit`.

## Tests

```bash
pytest
```

## Fonctionnalités principales

* Calcul serveur fiable : les recommandations matérielles, budgets PoE,
  indicateurs OPEX et plans VLAN sont produits par `src/omadabom_engine.py`.
* Téléchargement opérationnel : le bouton « Télécharger le ZIP » déclenche
  la génération d'une archive contenant `bom.csv`, `synthese.txt`,
  `portmap.txt` et `plan_vlan.txt`.
* API prête à intégrer : les clients peuvent exploiter `/api/generate`
  (JSON -> JSON) et `/api/download` (JSON -> ZIP) pour alimenter d'autres
  frontends.
* Validations serveur : les incohérences (surface nulle, vidéosurveillance
  sans caméras, résolution inconnue…) retournent des erreurs explicites
  afin de guider la saisie et garantir un dimensionnement réaliste.
