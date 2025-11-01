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

Vous pouvez également fournir un catalogue personnalisé pour alimenter le
moteur :

```bash
python -m webapp --catalogue /chemin/vers/catalogue.json
```

Pour produire un export statique de la page d'accueil (idéal pour GitHub Pages ou
une revue rapide sans serveur Python) :

```bash
python -m webapp --export-static docs/index.html
```

Vous pouvez ensuite visiter <http://localhost:8000> pour voir le site et
utiliser le configurateur. Le moteur Python situé derrière `/api/generate`
alimente la synthèse affichée à l'écran, et l'endpoint `/api/download`
retourne une archive ZIP contenant les livrables.

### Publier et tester via GitHub Pages

Pour partager rapidement la maquette directement depuis Git :

1. Générez la page statique avec `python -m webapp --export-static docs/index.html`.
2. Validez et poussez vos changements sur GitHub.
3. Dans le dépôt, ouvrez **Settings → Pages**.
4. Dans la section **Source**, choisissez la branche **`main`** ou **`docs`**,
   puis validez.

GitHub Pages déploiera automatiquement le site sur une URL publique en quelques
instants, ce qui vous permet de tester la démo sans configuration
supplémentaire. Sur cette version statique, les appels `/api/generate` et
`/api/download` renverront une erreur contrôlée (puisque le backend Python n'est
pas disponible), mais l'interface reste entièrement navigable pour la démo.

La page d'accueil affiche automatiquement la branche et le dernier commit
Git détectés, ainsi qu'une courte liste des derniers commits disponibles pour
offrir un aperçu visuel de l'activité récente. Si aucune information n'apparaît,
initialisez ou mettez à jour votre dépôt avec `git init`, `git add` puis
`git commit`. Dans un contexte où le dossier `.git` n'est pas disponible
(archive, déploiement CI/CD, etc.), vous pouvez définir les variables
d'environnement `OMADABOM_GIT_BRANCH` et `OMADABOM_GIT_COMMIT` avant de lancer
le serveur afin d'afficher tout de même les métadonnées attendues. En absence
d'historique Git, la section dédiée indique simplement la dernière révision
connue.

## Tests

```bash
pytest
```

## Catalogue dynamique

Les références utilisées par le moteur proviennent du fichier
`data/catalogue.json`. Chaque entrée précise le SKU, la consommation PoE, le
prix estimé et les caractéristiques clés exploitées par le moteur de règles.

Pour remplacer le catalogue par une version personnalisée (issue d'un export
PGSQL, d'un ERP, etc.) :

1. générez un nouveau fichier JSON reprenant la structure fournie ;
2. positionnez la variable d'environnement
   `OMADABOM_CATALOGUE_PATH=/chemin/vers/votre/catalogue.json` ;
3. relancez l'application ou vos tests : le moteur rechargera automatiquement le
   fichier lors du prochain calcul.

Le helper `set_catalogue_path()` exposé par `src/omadabom_engine` simplifie les
tests automatisés si vous souhaitez injecter un catalogue temporaire.

## Fonctionnalités principales

* Calcul serveur fiable : les recommandations matérielles, budgets PoE,
  indicateurs OPEX et plans VLAN sont produits par `src/omadabom_engine.py`.
* Téléchargement opérationnel : le bouton « Télécharger le ZIP » déclenche
  la génération d'une archive contenant `bom.csv`, `synthese.txt`,
  `portmap.txt`, `plan_vlan.txt` ainsi que des versions PDF prêtes à
  partager (`bom.pdf`, `synthese.pdf`, `plan_vlan.pdf`).
* Catalogue dynamique : la liste des équipements est stockée dans
  `data/catalogue.json`. Il suffit de mettre à jour ce fichier (ou de
  définir la variable d'environnement `OMADABOM_CATALOGUE_PATH`) pour que
  le moteur utilise les nouvelles références, budgets PoE et tarifs.
* Questionnaire professionnel : chaque étape propose des volets avancés
  (niveau Wi-Fi 6/6E/7, étages, contraintes radio, infrastructure existante,
  profils QoS, SSID cibles, services métiers personnalisés) afin d'affiner
  la recommandation en fonction des usages TP-Link Omada identifiés.
* API prête à intégrer : les clients peuvent exploiter `/api/generate`
  (JSON -> JSON) et `/api/download` (JSON -> ZIP) pour alimenter d'autres
  frontends.
* Validations serveur : les incohérences (surface nulle, vidéosurveillance
  sans caméras, résolution inconnue…) retournent des erreurs explicites
  afin de guider la saisie et garantir un dimensionnement réaliste.
* Historique Git embarqué : la page d'accueil liste les derniers commits pour
  faciliter le contrôle visuel entre plusieurs déploiements ou démonstrations.
