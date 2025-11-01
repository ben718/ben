"""A tiny WSGI application that serves a functional HTML page.

The goal of this module is to keep the application completely
dependency-free so that it can run in minimal environments while still
providing a pleasant, working landing page for the project.
"""
from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
from subprocess import CalledProcessError, run
from typing import Callable, Iterable, List, Tuple
from wsgiref.simple_server import make_server

StartResponse = Callable[[str, List[Tuple[str, str]]], None]
WSGIApplication = Callable[[dict, StartResponse], Iterable[bytes]]

PROJECT_ROOT = Path(__file__).resolve().parents[1]

GIT_PLACEHOLDER = "{{GIT_METADATA}}"

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang=\"fr\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>OmadaBOM – maquette fonctionnelle</title>
    <style>
      :root {
        color-scheme: light dark;
        --bg: #f5f7fb;
        --fg: #0f172a;
        --accent: #2563eb;
        --accent-soft: rgba(37, 99, 235, 0.08);
        --accent-strong: rgba(37, 99, 235, 0.15);
        --card: rgba(255, 255, 255, 0.92);
        --border: rgba(15, 23, 42, 0.08);
      }

      @media (prefers-color-scheme: dark) {
        :root {
          --bg: #0f172a;
          --fg: #e2e8f0;
          --card: rgba(15, 23, 42, 0.9);
          --border: rgba(226, 232, 240, 0.12);
        }
      }

      * {
        box-sizing: border-box;
      }

      body {
        margin: 0;
        min-height: 100vh;
        font-family: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif;
        background: radial-gradient(circle at 10% 20%, rgba(37, 99, 235, 0.12), transparent 55%),
          radial-gradient(circle at 90% 10%, rgba(14, 165, 233, 0.12), transparent 60%),
          var(--bg);
        color: var(--fg);
        display: flex;
        align-items: center;
        justify-content: center;
        padding: clamp(1.5rem, 5vw, 4rem);
      }

      main {
        width: min(1080px, 100%);
        background: var(--card);
        border-radius: 32px;
        padding: clamp(2rem, 5vw, 3.5rem);
        box-shadow: 0 40px 80px -40px rgba(15, 23, 42, 0.4);
        backdrop-filter: blur(22px);
      }

      header.hero {
        display: flex;
        flex-direction: column;
        gap: 1rem;
        margin-bottom: 2.5rem;
      }

      header.hero h1 {
        margin: 0;
        font-size: clamp(2.2rem, 5vw, 3.4rem);
        font-weight: 700;
      }

      header.hero p {
        margin: 0;
        max-width: 60ch;
        line-height: 1.6;
        font-size: 1.05rem;
      }

      .git-info {
        font-family: 'Fira Code', 'Source Code Pro', monospace;
        font-size: 0.9rem;
        opacity: 0.85;
      }

      .progress {
        display: flex;
        align-items: center;
        gap: 1rem;
        margin-bottom: 2rem;
      }

      .progress-bar {
        flex: 1;
        background: var(--border);
        border-radius: 999px;
        overflow: hidden;
        height: 0.5rem;
      }

      .progress-fill {
        width: 25%;
        height: 100%;
        background: linear-gradient(120deg, #2563eb, #1d4ed8);
        transition: width 0.4s ease;
      }

      .progress span {
        font-weight: 600;
      }

      .step {
        display: none;
        border: 1px solid var(--border);
        border-radius: 24px;
        padding: clamp(1.5rem, 3vw, 2.25rem);
        background: rgba(255, 255, 255, 0.65);
        backdrop-filter: blur(6px);
        margin-bottom: 1.75rem;
      }

      .step.active {
        display: block;
      }

      .step h2 {
        margin-top: 0;
        margin-bottom: 1rem;
        font-size: 1.7rem;
      }

      .step > p.description {
        margin-top: 0;
        margin-bottom: 1.5rem;
        color: rgba(15, 23, 42, 0.75);
      }

      .grid {
        display: grid;
        gap: 1rem;
      }

      .grid.two {
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      }

      label.option-card {
        display: block;
        border-radius: 18px;
        padding: 1.2rem;
        border: 1px solid var(--border);
        background: rgba(255, 255, 255, 0.55);
        cursor: pointer;
        transition: transform 0.2s ease, box-shadow 0.2s ease, border 0.2s ease;
        position: relative;
        overflow: hidden;
      }

      label.option-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 16px 40px -28px rgba(37, 99, 235, 0.45);
      }

      label.option-card input {
        position: absolute;
        opacity: 0;
        pointer-events: none;
      }

      label.option-card span {
        display: block;
        font-weight: 600;
        margin-bottom: 0.35rem;
      }

      label.option-card small {
        color: rgba(15, 23, 42, 0.65);
      }

      label.option-card input:checked + span,
      label.option-card input:checked ~ span {
        color: #1d4ed8;
      }

      label.option-card input:checked ~ .card-bg {
        opacity: 1;
      }

      label.option-card .card-bg {
        position: absolute;
        inset: 0;
        background: var(--accent-soft);
        opacity: 0;
        transition: opacity 0.2s ease;
        z-index: -1;
      }

      .field {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
        margin-bottom: 1.25rem;
      }

      .field label {
        font-weight: 600;
      }

      .field input[type='number'],
      .field input[type='text'],
      .field select {
        border: 1px solid var(--border);
        border-radius: 14px;
        padding: 0.85rem 1rem;
        font-size: 1rem;
        background: rgba(255, 255, 255, 0.9);
      }

      .inline-options {
        display: flex;
        flex-wrap: wrap;
        gap: 0.75rem;
      }

      .inline-options label {
        border-radius: 999px;
        padding: 0.5rem 1rem;
        border: 1px solid var(--border);
        cursor: pointer;
        position: relative;
        overflow: hidden;
      }

      .inline-options label input {
        position: absolute;
        opacity: 0;
      }

      .inline-options label span {
        font-weight: 600;
      }

      .inline-options label input:checked + span {
        color: #1d4ed8;
      }

      .toggle-advanced {
        background: none;
        border: none;
        color: #2563eb;
        font-weight: 600;
        cursor: pointer;
        margin-top: 1rem;
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
      }

      .advanced {
        margin-top: 1.5rem;
        padding-top: 1.25rem;
        border-top: 1px dashed var(--border);
      }

      .hidden {
        display: none !important;
      }

      .zones-list {
        display: flex;
        flex-direction: column;
        gap: 0.75rem;
        margin-top: 1rem;
      }

      .zones-list li {
        list-style: none;
        padding: 0.85rem 1rem;
        border-radius: 16px;
        background: var(--accent-soft);
        display: flex;
        justify-content: space-between;
        align-items: center;
      }

      .zones-list button {
        border: none;
        background: none;
        color: #ef4444;
        font-weight: 600;
        cursor: pointer;
      }

      .qos-list {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
        margin-bottom: 1.5rem;
      }

      .qos-item {
        display: flex;
        align-items: center;
        justify-content: space-between;
        border-radius: 14px;
        padding: 0.85rem 1rem;
        border: 1px solid var(--border);
        background: rgba(255, 255, 255, 0.7);
      }

      .qos-item .controls {
        display: flex;
        gap: 0.25rem;
      }

      .qos-item button {
        border: none;
        background: var(--accent-soft);
        color: #1d4ed8;
        border-radius: 999px;
        padding: 0.25rem 0.75rem;
        cursor: pointer;
        font-weight: 600;
      }

      .summary-card {
        background: rgba(255, 255, 255, 0.75);
        border-radius: 24px;
        padding: 1.5rem;
        border: 1px solid var(--border);
        display: flex;
        flex-direction: column;
        gap: 1rem;
      }

      .summary-card h3 {
        margin: 0;
        font-size: 1.35rem;
      }

      .summary-card ul {
        margin: 0;
        padding-left: 1.2rem;
      }

      .summary-card li {
        margin-bottom: 0.5rem;
      }

      .pill {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        padding: 0.35rem 0.75rem;
        border-radius: 999px;
        background: var(--accent-soft);
        font-weight: 600;
        font-size: 0.9rem;
      }

      nav.actions {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
      }

      nav.actions button {
        flex: 1;
        border: none;
        border-radius: 16px;
        padding: 0.95rem 1.25rem;
        font-size: 1rem;
        font-weight: 600;
        cursor: pointer;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
      }

      #prevStep {
        background: rgba(37, 99, 235, 0.12);
        color: #1d4ed8;
      }

      #nextStep {
        background: linear-gradient(120deg, #2563eb, #1d4ed8);
        color: white;
        box-shadow: 0 18px 40px -25px rgba(37, 99, 235, 0.9);
      }

      nav.actions button:hover {
        transform: translateY(-2px);
      }

      .download-box {
        padding: 1.25rem;
        border-radius: 18px;
        background: var(--accent-soft);
        border: 1px dashed rgba(37, 99, 235, 0.35);
      }

      .download-box strong {
        display: block;
        margin-bottom: 0.5rem;
      }

      .cta {
        margin-top: 0.5rem;
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        background: linear-gradient(120deg, #2563eb, #7c3aed);
        color: white;
        border-radius: 999px;
        padding: 0.9rem 1.75rem;
        text-decoration: none;
        font-weight: 600;
        box-shadow: 0 25px 60px -30px rgba(124, 58, 237, 0.75);
      }

      footer.page {
        margin-top: 2.5rem;
        text-align: center;
        font-size: 0.9rem;
        color: rgba(15, 23, 42, 0.6);
      }

      @media (max-width: 768px) {
        body {
          padding: 1rem;
        }

        main {
          border-radius: 20px;
          padding: 1.75rem;
        }

        .step {
          border-radius: 18px;
        }

        nav.actions {
          flex-direction: column;
        }

        nav.actions button {
          width: 100%;
        }
      }
    </style>
  </head>
  <body>
    <main>
      <header class=\"hero\">
        <div>
          <p class=\"pill\">Maquette fonctionnelle</p>
          <h1>OmadaBOM – configurez un réseau précis, simplement</h1>
          <p>Découvrez le parcours hybride Simple/Avancé d'OmadaBOM pour traduire vos besoins en une configuration réseau professionnelle, entièrement personnalisable.</p>
        </div>
        <div class=\"git-info\">{{GIT_METADATA}}</div>
      </header>

      <div class=\"progress\">
        <div class=\"progress-bar\">
          <div class=\"progress-fill\" id=\"progressFill\"></div>
        </div>
        <span id=\"progressLabel\">Étape 1 sur 4</span>
      </div>

      <section class=\"step active\" data-step=\"1\">
        <h2>Étape 1 · Décrivez votre environnement</h2>
        <p class=\"description\">Commencez par une estimation rapide, puis affinez avec des détails structurels si nécessaire.</p>
        <div class=\"field\">
          <label for=\"surfaceInput\">Surface totale à couvrir (m²)</label>
          <input id=\"surfaceInput\" type=\"number\" min=\"1\" value=\"300\" />
        </div>

        <div class=\"field\">
          <label>Type d'environnement principal</label>
          <div class=\"grid two\">
            <label class=\"option-card\">
              <input type=\"radio\" name=\"environment\" value=\"bureau\" checked />
              <div class=\"card-bg\"></div>
              <span>🏢 Bureau</span>
              <small>Open-space, salles de réunion, bureaux cloisonnés.</small>
            </label>
            <label class=\"option-card\">
              <input type=\"radio\" name=\"environment\" value=\"maison\" />
              <div class=\"card-bg\"></div>
              <span>🏠 Maison</span>
              <small>Résidences, villas, appartements spacieux.</small>
            </label>
            <label class=\"option-card\">
              <input type=\"radio\" name=\"environment\" value=\"entrepot\" />
              <div class=\"card-bg\"></div>
              <span>🏭 Entrepôt</span>
              <small>Logistique, ateliers, hangars industriels.</small>
            </label>
            <label class=\"option-card\">
              <input type=\"radio\" name=\"environment\" value=\"hotel\" />
              <div class=\"card-bg\"></div>
              <span>🏨 Hôtel</span>
              <small>Chambres, couloirs, espaces communs multiples.</small>
            </label>
            <label class=\"option-card\">
              <input type=\"radio\" name=\"environment\" value=\"exterieur\" />
              <div class=\"card-bg\"></div>
              <span>🌳 Extérieur</span>
              <small>Campus, parkings, jardins, zones urbaines.</small>
            </label>
          </div>
        </div>

        <div class=\"field\">
          <label>Densité d'appareils attendue</label>
          <div class=\"inline-options\">
            <label>
              <input type=\"radio\" name=\"density\" value=\"faible\" />
              <span>Faible</span>
            </label>
            <label>
              <input type=\"radio\" name=\"density\" value=\"moyenne\" checked />
              <span>Moyenne</span>
            </label>
            <label>
              <input type=\"radio\" name=\"density\" value=\"elevee\" />
              <span>Élevée</span>
            </label>
          </div>
        </div>

        <button class=\"toggle-advanced\" type=\"button\" data-advanced-target=\"advanced-step1\">Afficher les options avancées</button>
        <div class=\"advanced hidden\" id=\"advanced-step1\">
          <div class=\"field\">
            <label>Structure du bâtiment</label>
            <div class=\"inline-options\">
              <label>
                <input type=\"radio\" name=\"structure\" value=\"cloisons\" checked />
                <span>Cloisons légères</span>
              </label>
              <label>
                <input type=\"radio\" name=\"structure\" value=\"murs\" />
                <span>Murs porteurs</span>
              </label>
              <label>
                <input type=\"radio\" name=\"structure\" value=\"metal\" />
                <span>Structure métallique</span>
              </label>
            </div>
          </div>

          <div class=\"field\">
            <label>Hauteur sous plafond</label>
            <div class=\"inline-options\">
              <label>
                <input type=\"radio\" name=\"height\" value=\"standard\" checked />
                <span>Standard &lt; 3m</span>
              </label>
              <label>
                <input type=\"radio\" name=\"height\" value=\"elevee\" />
                <span>Élevée 3-5m</span>
              </label>
              <label>
                <input type=\"radio\" name=\"height\" value=\"tres\" />
                <span>Très élevée &gt; 5m</span>
              </label>
            </div>
          </div>

          <div class=\"field\">
            <label>Décomposez par zones (optionnel)</label>
            <div class=\"grid two\">
              <div class=\"field\">
                <label for=\"zoneNameInput\">Nom de la zone</label>
                <input id=\"zoneNameInput\" type=\"text\" placeholder=\"Ex : Open-space\" />
              </div>
              <div class=\"field\">
                <label for=\"zoneSurfaceInput\">Surface (m²)</label>
                <input id=\"zoneSurfaceInput\" type=\"number\" min=\"1\" />
              </div>
              <div class=\"field\">
                <label for=\"zoneDensitySelect\">Densité</label>
                <select id=\"zoneDensitySelect\">
                  <option value=\"faible\">Faible</option>
                  <option value=\"moyenne\" selected>Moyenne</option>
                  <option value=\"elevee\">Élevée</option>
                </select>
              </div>
            </div>
            <button type=\"button\" id=\"addZoneButton\" class=\"toggle-advanced\">+ Ajouter cette zone</button>
            <ul class=\"zones-list\" id=\"zoneList\"></ul>
          </div>
        </div>
      </section>

      <section class=\"step\" data-step=\"2\">
        <h2>Étape 2 · Choisissez vos services</h2>
        <p class=\"description\">Sélectionnez les usages clés pour adapter automatiquement la sécurité et la performance.</p>
        <div class=\"grid\">
          <label class=\"option-card\">
            <input type=\"checkbox\" data-service=\"invites\" checked />
            <div class=\"card-bg\"></div>
            <span>Réseau invités</span>
            <small>Wi-Fi isolé pour visiteurs et collaborateurs temporaires.</small>
          </label>
          <label class=\"option-card\">
            <input type=\"checkbox\" data-service=\"voip\" />
            <div class=\"card-bg\"></div>
            <span>Téléphonie sur IP (VoIP)</span>
            <small>Appels voix haute priorité et stabilité assurée.</small>
          </label>
          <label class=\"option-card\">
            <input type=\"checkbox\" data-service=\"iot\" />
            <div class=\"card-bg\"></div>
            <span>Objets connectés (IoT)</span>
            <small>Segmentation automatique des capteurs et équipements.</small>
          </label>
          <label class=\"option-card\">
            <input type=\"checkbox\" data-service=\"haute_vitesse\" />
            <div class=\"card-bg\"></div>
            <span>Connexion &gt; 1 Gbit/s</span>
            <small>Optimise pour la fibre multi-gigabit et le Wi-Fi 6/7.</small>
          </label>
        </div>

        <button class=\"toggle-advanced\" type=\"button\" data-advanced-target=\"advanced-step2\">Afficher les options avancées</button>
        <div class=\"advanced hidden\" id=\"advanced-step2\">
          <div class=\"field\">
            <label>Hiérarchisation du trafic (QoS)</label>
            <div class=\"qos-list\" id=\"qosList\"></div>
          </div>
          <div class=\"field\">
            <label>Exigences de sécurité spécifiques</label>
            <div class=\"grid two\">
              <label class=\"option-card\">
                <input type=\"checkbox\" data-security=\"isolation\" checked />
                <div class=\"card-bg\"></div>
                <span>Isolation stricte des clients</span>
                <small>Aucun appareil invité ne peut voir un autre appareil.</small>
              </label>
              <label class=\"option-card\">
                <input type=\"checkbox\" data-security=\"filtrage\" />
                <div class=\"card-bg\"></div>
                <span>Filtrage MAC</span>
                <small>Autoriser uniquement les équipements pré-enregistrés.</small>
              </label>
              <label class=\"option-card\">
                <input type=\"checkbox\" data-security=\"portail\" />
                <div class=\"card-bg\"></div>
                <span>Portail captif avancé</span>
                <small>Portail personnalisé avec vouchers et conditions légales.</small>
              </label>
            </div>
          </div>
          <div class=\"grid two\">
            <div class=\"field\">
              <label for=\"workstationCount\">Nombre de postes de travail</label>
              <input type=\"number\" id=\"workstationCount\" min=\"0\" value=\"25\" />
            </div>
            <div class=\"field\">
              <label for=\"bandwidthPerUser\">Besoins moyens par poste (Mbps)</label>
              <input type=\"number\" id=\"bandwidthPerUser\" min=\"0\" value=\"50\" />
            </div>
            <div class=\"field\">
              <label for=\"cameraCountBandwidth\">Nombre de flux vidéo critiques</label>
              <input type=\"number\" id=\"cameraCountBandwidth\" min=\"0\" value=\"0\" />
            </div>
            <div class=\"field\">
              <label for=\"bandwidthPerCamera\">Débit par flux (Mbps)</label>
              <input type=\"number\" id=\"bandwidthPerCamera\" min=\"0\" value=\"4\" />
            </div>
          </div>
        </div>
      </section>

      <section class=\"step\" data-step=\"3\">
        <h2>Étape 3 · Vidéosurveillance VIGI</h2>
        <p class=\"description\">Intégrez un dispositif complet de vidéosurveillance et dimensionnez le stockage.</p>
        <div class=\"inline-options\">
          <label>
            <input type=\"radio\" name=\"cctv\" value=\"non\" checked />
            <span>Pas de caméras</span>
          </label>
          <label>
            <input type=\"radio\" name=\"cctv\" value=\"oui\" />
            <span>Ajouter la vidéosurveillance</span>
          </label>
        </div>

        <div id=\"cctvDetails\" class=\"hidden\">
          <div class=\"grid two\">
            <div class=\"field\">
              <label for=\"cctvInteriorCount\">Caméras intérieures</label>
              <input type=\"number\" id=\"cctvInteriorCount\" min=\"0\" value=\"4\" />
            </div>
            <div class=\"field\">
              <label for=\"cctvExteriorCount\">Caméras extérieures</label>
              <input type=\"number\" id=\"cctvExteriorCount\" min=\"0\" value=\"2\" />
            </div>
          </div>
          <div class=\"field\">
            <label>Durée de rétention</label>
            <div class=\"inline-options\">
              <label>
                <input type=\"radio\" name=\"retention\" value=\"7\" />
                <span>7 jours</span>
              </label>
              <label>
                <input type=\"radio\" name=\"retention\" value=\"15\" checked />
                <span>15 jours</span>
              </label>
              <label>
                <input type=\"radio\" name=\"retention\" value=\"30\" />
                <span>30 jours</span>
              </label>
              <label>
                <input type=\"radio\" name=\"retention\" value=\"60\" />
                <span>60 jours</span>
              </label>
            </div>
          </div>

          <button class=\"toggle-advanced\" type=\"button\" data-advanced-target=\"advanced-step3\">Afficher les options avancées</button>
          <div class=\"advanced hidden\" id=\"advanced-step3\">
            <div class=\"grid two\">
              <div class=\"field\">
                <label>Répartition des caméras intérieures</label>
                <div class=\"grid\">
                  <label>
                    Dôme C440
                    <input type=\"number\" id=\"cctvDomeCount\" min=\"0\" value=\"3\" />
                  </label>
                  <label>
                    Turret C240
                    <input type=\"number\" id=\"cctvTurretCount\" min=\"0\" value=\"1\" />
                  </label>
                  <label>
                    Bullet C340
                    <input type=\"number\" id=\"cctvInteriorBulletCount\" min=\"0\" value=\"0\" />
                  </label>
                </div>
              </div>
              <div class=\"field\">
                <label>Répartition des caméras extérieures</label>
                <div class=\"grid\">
                  <label>
                    Bullet C340
                    <input type=\"number\" id=\"cctvExteriorBulletCount\" min=\"0\" value=\"2\" />
                  </label>
                  <label class=\"inline-options\" style=\"margin-top:0.5rem;\">
                    <input type=\"checkbox\" id=\"cctvAiCheckbox\" />
                    <span>Analyse IA (véhicules / humains)</span>
                  </label>
                </div>
              </div>
            </div>

            <div class=\"field\">
              <label>Résolution souhaitée</label>
              <div class=\"inline-options\">
                <label>
                  <input type=\"radio\" name=\"resolution\" value=\"1080p\" />
                  <span>1080p</span>
                </label>
                <label>
                  <input type=\"radio\" name=\"resolution\" value=\"4MP\" checked />
                  <span>4MP</span>
                </label>
                <label>
                  <input type=\"radio\" name=\"resolution\" value=\"8MP\" />
                  <span>8MP / 4K</span>
                </label>
              </div>
            </div>

            <div class=\"field\">
              <label>Mode d'enregistrement</label>
              <div class=\"inline-options\">
                <label>
                  <input type=\"radio\" name=\"recordingMode\" value=\"continu\" checked />
                  <span>Continu 24/7</span>
                </label>
                <label>
                  <input type=\"radio\" name=\"recordingMode\" value=\"mouvement\" />
                  <span>Sur détection de mouvement</span>
                </label>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section class=\"step\" data-step=\"4\">
        <h2>Étape 4 · Résultats et livrables</h2>
        <p class=\"description\">Synthèse dynamique de votre configuration. Ajustez les étapes précédentes pour affiner la recommandation.</p>
        <div class=\"summary-card\">
          <h3>Matériel recommandé</h3>
          <ul id=\"hardwareList\"></ul>
        </div>
        <div class=\"summary-card\">
          <h3>Indicateurs clés</h3>
          <ul id=\"metricsList\"></ul>
        </div>
        <div class=\"summary-card\">
          <h3>Focus services &amp; sécurité</h3>
          <ul id=\"serviceList\"></ul>
        </div>
        <div class=\"download-box\">
          <strong>Dossier professionnel disponible :</strong> BOM détaillée, plan VLAN/IP, port-map, calculs PoE &amp; stockage.
          <a class=\"cta\" href=\"#\" aria-disabled=\"true\">Paiement simulé – 9,99 €</a>
        </div>
      </section>

      <nav class=\"actions\">
        <button type=\"button\" id=\"prevStep\">← Étape précédente</button>
        <button type=\"button\" id=\"nextStep\">Étape suivante →</button>
      </nav>

      <footer class=\"page\">
        Cette maquette démontre l'expérience hybride Simple / Avancé d'OmadaBOM. Tous les calculs sont simulés côté client pour illustrer le futur moteur professionnel.
      </footer>
    </main>

    <script>
      const state = {
        surface: 300,
        environment: 'bureau',
        density: 'moyenne',
        structure: 'cloisons',
        height: 'standard',
        zones: [],
        services: { invites: true, voip: false, iot: false, haute_vitesse: false },
        qosOrder: ['voip', 'visioconference', 'navigation', 'streaming', 'iot'],
        security: { isolation: true, filtrage: false, portail: false },
        bandwidth: { postes: 25, mbpsParPoste: 50, cameras: 0, mbpsParCamera: 4 },
        cctv: {
          enabled: false,
          interior: 4,
          exterior: 2,
          retention: 15,
          resolution: '4MP',
          mode: 'continu',
          interiorTypes: { dome: 3, turret: 1, bullet: 0 },
          exteriorTypes: { bullet: 2, ai: false },
        },
      };

      const steps = Array.from(document.querySelectorAll('[data-step]'));
      const progressFill = document.getElementById('progressFill');
      const progressLabel = document.getElementById('progressLabel');
      const nextBtn = document.getElementById('nextStep');
      const prevBtn = document.getElementById('prevStep');
      let currentStep = 1;

      function updateProgress() {
        const percent = (currentStep / steps.length) * 100;
        progressFill.style.width = `${percent}%`;
        progressLabel.textContent = `Étape ${currentStep} sur ${steps.length}`;
        prevBtn.disabled = currentStep === 1;
        nextBtn.textContent = currentStep === steps.length ? 'Revenir aux étapes' : 'Étape suivante →';
      }

      function showStep(step) {
        steps.forEach((section) => {
          section.classList.toggle('active', Number(section.dataset.step) === step);
        });
        currentStep = step;
        updateProgress();
        if (step === 4) {
          renderSummary();
        }
      }

      function toggleAdvanced(targetId, button) {
        const block = document.getElementById(targetId);
        block.classList.toggle('hidden');
        const expanded = !block.classList.contains('hidden');
        button.textContent = expanded ? 'Masquer les options avancées' : 'Afficher les options avancées';
      }

      document.querySelectorAll('.toggle-advanced').forEach((btn) => {
        const target = btn.dataset.advancedTarget;
        if (!target) return;
        btn.addEventListener('click', () => toggleAdvanced(target, btn));
      });

      nextBtn.addEventListener('click', () => {
        if (currentStep < steps.length) {
          showStep(currentStep + 1);
        } else {
          showStep(1);
        }
      });

      prevBtn.addEventListener('click', () => {
        if (currentStep > 1) {
          showStep(currentStep - 1);
        }
      });

      document.getElementById('surfaceInput').addEventListener('input', (event) => {
        const value = Number(event.target.value);
        state.surface = Number.isFinite(value) && value > 0 ? value : 0;
      });

      document.querySelectorAll('input[name=\"environment\"]').forEach((input) => {
        input.addEventListener('change', () => {
          if (input.checked) {
            state.environment = input.value;
          }
        });
      });

      document.querySelectorAll('input[name=\"density\"]').forEach((input) => {
        input.addEventListener('change', () => {
          if (input.checked) {
            state.density = input.value;
          }
        });
      });

      document.querySelectorAll('input[name=\"structure\"]').forEach((input) => {
        input.addEventListener('change', () => {
          if (input.checked) {
            state.structure = input.value;
          }
        });
      });

      document.querySelectorAll('input[name=\"height\"]').forEach((input) => {
        input.addEventListener('change', () => {
          if (input.checked) {
            state.height = input.value;
          }
        });
      });

      document.getElementById('addZoneButton').addEventListener('click', () => {
        const name = document.getElementById('zoneNameInput').value.trim();
        const surface = Number(document.getElementById('zoneSurfaceInput').value);
        const density = document.getElementById('zoneDensitySelect').value;
        if (!name || !Number.isFinite(surface) || surface <= 0) {
          alert('Veuillez renseigner un nom et une surface valide.');
          return;
        }
        state.zones.push({ id: crypto.randomUUID(), name, surface, density });
        document.getElementById('zoneNameInput').value = '';
        document.getElementById('zoneSurfaceInput').value = '';
        renderZones();
      });

      function renderZones() {
        const list = document.getElementById('zoneList');
        list.innerHTML = '';
        state.zones.forEach((zone) => {
          const li = document.createElement('li');
          li.innerHTML = `<strong>${zone.name}</strong> — ${zone.surface} m² · densité ${zone.density}<button type=\"button\">Supprimer</button>`;
          li.querySelector('button').addEventListener('click', () => {
            state.zones = state.zones.filter((item) => item.id !== zone.id);
            renderZones();
          });
          list.appendChild(li);
        });
      }

      document.querySelectorAll('[data-service]').forEach((checkbox) => {
        checkbox.addEventListener('change', () => {
          state.services[checkbox.dataset.service] = checkbox.checked;
        });
      });

      const qosItems = [
        { key: 'voip', label: 'Téléphonie (VoIP)' },
        { key: 'visioconference', label: 'Visioconférence' },
        { key: 'navigation', label: 'Navigation Web' },
        { key: 'streaming', label: 'Streaming vidéo' },
        { key: 'iot', label: 'IoT & capteurs' },
      ];

      function renderQosList() {
        const container = document.getElementById('qosList');
        container.innerHTML = '';
        state.qosOrder.forEach((key, index) => {
          const item = qosItems.find((entry) => entry.key === key);
          if (!item) return;
          const div = document.createElement('div');
          div.className = 'qos-item';
          div.innerHTML = `<span>${index + 1}. ${item.label}</span>`;
          const controls = document.createElement('div');
          controls.className = 'controls';
          const up = document.createElement('button');
          up.type = 'button';
          up.textContent = '↑';
          const down = document.createElement('button');
          down.type = 'button';
          down.textContent = '↓';
          up.disabled = index === 0;
          down.disabled = index === state.qosOrder.length - 1;
          up.addEventListener('click', () => moveQos(index, -1));
          down.addEventListener('click', () => moveQos(index, 1));
          controls.appendChild(up);
          controls.appendChild(down);
          div.appendChild(controls);
          container.appendChild(div);
        });
      }

      function moveQos(index, delta) {
        const newIndex = index + delta;
        if (newIndex < 0 || newIndex >= state.qosOrder.length) return;
        const [item] = state.qosOrder.splice(index, 1);
        state.qosOrder.splice(newIndex, 0, item);
        renderQosList();
      }

      document.querySelectorAll('[data-security]').forEach((checkbox) => {
        checkbox.addEventListener('change', () => {
          state.security[checkbox.dataset.security] = checkbox.checked;
        });
      });

      document.getElementById('workstationCount').addEventListener('input', (event) => {
        const value = Number(event.target.value);
        state.bandwidth.postes = Number.isFinite(value) && value >= 0 ? value : 0;
      });

      document.getElementById('bandwidthPerUser').addEventListener('input', (event) => {
        const value = Number(event.target.value);
        state.bandwidth.mbpsParPoste = Number.isFinite(value) && value >= 0 ? value : 0;
      });

      document.getElementById('cameraCountBandwidth').addEventListener('input', (event) => {
        const value = Number(event.target.value);
        state.bandwidth.cameras = Number.isFinite(value) && value >= 0 ? value : 0;
      });

      document.getElementById('bandwidthPerCamera').addEventListener('input', (event) => {
        const value = Number(event.target.value);
        state.bandwidth.mbpsParCamera = Number.isFinite(value) && value >= 0 ? value : 0;
      });

      document.querySelectorAll('input[name=\"cctv\"]').forEach((input) => {
        input.addEventListener('change', () => {
          const enabled = input.value === 'oui' && input.checked;
          state.cctv.enabled = enabled;
          document.getElementById('cctvDetails').classList.toggle('hidden', !enabled);
        });
      });

      document.getElementById('cctvInteriorCount').addEventListener('input', (event) => {
        const value = Number(event.target.value);
        state.cctv.interior = Number.isFinite(value) && value >= 0 ? value : 0;
      });

      document.getElementById('cctvExteriorCount').addEventListener('input', (event) => {
        const value = Number(event.target.value);
        state.cctv.exterior = Number.isFinite(value) && value >= 0 ? value : 0;
      });

      document.querySelectorAll('input[name=\"retention\"]').forEach((input) => {
        input.addEventListener('change', () => {
          if (input.checked) {
            state.cctv.retention = Number(input.value);
          }
        });
      });

      document.getElementById('cctvDomeCount').addEventListener('input', (event) => {
        const value = Number(event.target.value);
        state.cctv.interiorTypes.dome = Number.isFinite(value) && value >= 0 ? value : 0;
      });

      document.getElementById('cctvTurretCount').addEventListener('input', (event) => {
        const value = Number(event.target.value);
        state.cctv.interiorTypes.turret = Number.isFinite(value) && value >= 0 ? value : 0;
      });

      document.getElementById('cctvInteriorBulletCount').addEventListener('input', (event) => {
        const value = Number(event.target.value);
        state.cctv.interiorTypes.bullet = Number.isFinite(value) && value >= 0 ? value : 0;
      });

      document.getElementById('cctvExteriorBulletCount').addEventListener('input', (event) => {
        const value = Number(event.target.value);
        state.cctv.exteriorTypes.bullet = Number.isFinite(value) && value >= 0 ? value : 0;
      });

      document.getElementById('cctvAiCheckbox').addEventListener('change', (event) => {
        state.cctv.exteriorTypes.ai = event.target.checked;
      });

      document.querySelectorAll('input[name=\"resolution\"]').forEach((input) => {
        input.addEventListener('change', () => {
          if (input.checked) {
            state.cctv.resolution = input.value;
          }
        });
      });

      document.querySelectorAll('input[name=\"recordingMode\"]').forEach((input) => {
        input.addEventListener('change', () => {
          if (input.checked) {
            state.cctv.mode = input.value;
          }
        });
      });

      function areaPerAp(density) {
        const base = { faible: 200, moyenne: 130, elevee: 90 };
        return base[density] || 130;
      }

      function structureFactor(structure) {
        return { cloisons: 1, murs: 0.85, metal: 0.75 }[structure] || 1;
      }

      function heightFactor(height) {
        return { standard: 1, elevee: 0.92, tres: 0.82 }[height] || 1;
      }

      function computeAccessPoints() {
        const zones = state.zones.length ? state.zones : [{ surface: state.surface, density: state.density }];
        let total = 0;
        zones.forEach((zone) => {
          const area = areaPerAp(zone.density) * structureFactor(state.structure) * heightFactor(state.height);
          const effective = Math.max(area, 45);
          total += Math.ceil(zone.surface / effective);
        });
        return Math.max(total, 1);
      }

      function pickApModel(apCount) {
        if (state.environment === 'hotel') return 'EAP615-Wall (Wi-Fi 6 mural)';
        if (state.environment === 'exterieur') return 'EAP610-Outdoor (Wi-Fi 6 extérieur)';
        if (state.density === 'elevee' || state.services.haute_vitesse) return 'EAP690E HD (Wi-Fi 6E tri-bande)';
        if (apCount >= 6) return 'EAP673 (Wi-Fi 6 double bande)';
        return 'EAP650 (Wi-Fi 6)';
      }

      function pickSwitch(totalPoEPorts, poeBudget) {
        if (totalPoEPorts <= 8 && poeBudget <= 150) return 'TL-SG2210MP (8 ports PoE+, 150W)';
        if (totalPoEPorts <= 16 && poeBudget <= 300) return 'TL-SG2428P (24 ports PoE+, 250W)';
        if (totalPoEPorts <= 24 && poeBudget <= 380) return 'TL-SG3428MP (24 ports PoE+, 384W)';
        return 'TL-SG3452XP (48 ports PoE++, 720W)';
      }

      function pickRouter(totalBandwidth) {
        if (state.services.haute_vitesse || totalBandwidth > 1000) return 'ER7206 (Multi-Gigabit)';
        if (totalBandwidth > 600) return 'ER707-M2 (Dual WAN 2.5G)';
        return 'ER605 (Gigabit)';
      }

      function pickController(apCount, cameraCount) {
        const devices = apCount + cameraCount;
        if (devices > 20) return 'OC300 (contrôleur rack)';
        return 'OC200 (contrôleur cloud)';
      }

      function computeSummary() {
        const apCount = computeAccessPoints();
        const apModel = pickApModel(apCount);
        const cameraCount = state.cctv.enabled ? state.cctv.interior + state.cctv.exterior : 0;
        const poePerAp = state.density === 'elevee' ? 22 : 18;
        const poePerCamera = state.cctv.resolution === '8MP' ? 18 : state.cctv.resolution === '4MP' ? 12 : 9;
        const poeBudget = apCount * poePerAp + cameraCount * poePerCamera;
        const portsNeeded = apCount + cameraCount;
        const switchModel = pickSwitch(portsNeeded, poeBudget * 1.2);
        const totalBandwidthUsers = state.bandwidth.postes * state.bandwidth.mbpsParPoste;
        const totalBandwidthCameras = state.bandwidth.cameras * state.bandwidth.mbpsParCamera;
        const totalBandwidth = totalBandwidthUsers + totalBandwidthCameras;
        const routerModel = pickRouter(totalBandwidth);
        const controller = pickController(apCount, cameraCount);
        const nvr = cameraCount ? (cameraCount > 8 ? 'VIGI NVR1108' : 'VIGI NVR1008H') : null;
        const retentionDays = state.cctv.retention;
        const resolution = state.cctv.resolution;
        const recordingFactor = state.cctv.mode === 'continu' ? 1 : 0.45;
        const bitrate = resolution === '8MP' ? 12 : resolution === '4MP' ? 8 : 5;
        const storageTb = cameraCount ? ((cameraCount * bitrate * 0.125) * 24 * retentionDays * recordingFactor) / 1024 : 0;
        const storageDisplay = storageTb ? `${storageTb.toFixed(2)} To estimés` : '—';
        const poeProvided = switchModel.includes('3452') ? 720 : switchModel.includes('3428') ? 384 : switchModel.includes('2428') ? 250 : 150;
        const consumption = apCount * 15 + cameraCount * 12 + (poeProvided * 0.1) + 25;
        const annualCost = (consumption * 24 * 365 / 1000) * 0.25;
        return {
          hardware: [
            `${apCount} × ${apModel}`,
            `${switchModel} (ports PoE requis : ${portsNeeded})`,
            `${routerModel}`,
            controller,
            cameraCount ? `${cameraCount} × Caméras VIGI (${resolution})` : null,
            nvr,
            cameraCount ? `Stockage recommandé : ${storageDisplay}` : null,
          ].filter(Boolean),
          metrics: [
            `Budget PoE requis : ${poeBudget.toFixed(0)} W`,
            `Budget PoE disponible : ${poeProvided} W`,
            `Consommation estimée : ${consumption.toFixed(0)} W`,
            `Coût annuel (0,25 €/kWh) : ${annualCost.toFixed(0)} €`,
            `Bande passante agrégée : ${totalBandwidth.toFixed(0)} Mbps`,
          ],
          services: [
            state.services.invites ? 'VLAN Invités isolé + portail captif' : null,
            state.services.voip ? 'QoS prioritaire VoIP' : null,
            state.services.iot ? 'Segment IoT dédié et ACL restrictives' : null,
            state.services.haute_vitesse ? 'Backbone multi-gigabit recommandé' : null,
            state.security.filtrage ? 'Filtrage MAC / 802.1X' : null,
            state.security.portail ? 'Portail captif avancé avec vouchers' : null,
            `Priorités QoS : ${state.qosOrder.map((key) => qosItems.find((item) => item.key === key)?.label).filter(Boolean).join(' → ')}`,
          ].filter(Boolean),
        };
      }

      function renderSummary() {
        const summary = computeSummary();
        const hardwareList = document.getElementById('hardwareList');
        const metricsList = document.getElementById('metricsList');
        const serviceList = document.getElementById('serviceList');
        hardwareList.innerHTML = summary.hardware.map((item) => `<li>${item}</li>`).join('');
        metricsList.innerHTML = summary.metrics.map((item) => `<li>${item}</li>`).join('');
        serviceList.innerHTML = summary.services.map((item) => `<li>${item}</li>`).join('');
      }

      renderQosList();
      updateProgress();
    </script>
  </body>
</html>
"""

NOT_FOUND_TEMPLATE = """<!DOCTYPE html>
<html lang=\"fr\">
  <head>
    <meta charset=\"utf-8\" />
    <title>Page introuvable</title>
  </head>
  <body>
    <h1>404 - Page introuvable</h1>
    <p>La ressource demandée n'existe pas.</p>
  </body>
</html>
"""


def _response(status: str, body: str, start_response: StartResponse) -> Iterable[bytes]:
    payload = body.encode("utf-8")
    headers = [
        ("Content-Type", "text/html; charset=utf-8"),
        ("Content-Length", str(len(payload))),
    ]
    start_response(status, headers)
    yield payload


def _run_git_command(args: list[str]) -> str:
    """Execute a Git command rooted at the project directory."""

    result = run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        check=True,
    )
    return result.stdout.strip()


def _get_git_metadata() -> tuple[str, str] | None:
    """Return the active branch name and commit hash if available."""

    try:
        branch = _run_git_command(["rev-parse", "--abbrev-ref", "HEAD"])
        commit = _run_git_command(["rev-parse", "HEAD"])
    except (CalledProcessError, FileNotFoundError, PermissionError):
        return None

    if not branch or not commit:
        return None

    return branch, commit


def _render_git_metadata_html() -> str:
    """Generate the HTML snippet describing the current Git state."""

    metadata = _get_git_metadata()
    if metadata is None:
        return "Version Git indisponible (dépôt non initialisé)."

    branch, commit = metadata
    short_commit = commit[:7]
    return f"Version Git : <code>{branch}</code> @ <code>{short_commit}</code>"


def _render_homepage(git_html: str) -> str:
    """Insert the Git metadata into the homepage template."""

    return HTML_TEMPLATE.replace(GIT_PLACEHOLDER, git_html)


def create_app(
    git_info_provider: Callable[[], str] | None = None,
) -> WSGIApplication:
    """Return the WSGI application used by the project."""

    provider = git_info_provider or _render_git_metadata_html

    def application(environ: dict, start_response: StartResponse) -> Iterable[bytes]:
        path = environ.get("PATH_INFO", "/") or "/"
        if path in {"", "/", "/index.html"}:
            git_html = provider()
            body = _render_homepage(git_html)
            return _response("200 OK", body, start_response)

        return _response("404 Not Found", NOT_FOUND_TEMPLATE, start_response)

    return application


def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Launch the development server."""

    with make_server(host, port, create_app()) as httpd:
        print(f"Serving on http://{host}:{port} – press Ctrl+C to quit")
        httpd.serve_forever()


def _parse_args(argv: list[str] | None = None) -> tuple[str, int]:
    parser = ArgumentParser(description="Launch the demonstration web server")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind")
    parser.add_argument("--port", default=8000, type=int, help="Port to listen on")
    args = parser.parse_args(argv)
    return args.host, args.port


def main(argv: list[str] | None = None) -> None:
    host, port = _parse_args(argv)
    serve(host, port)


if __name__ == "__main__":  # pragma: no cover - manual execution helper
    main()
