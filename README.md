# Clip2Tube

Application de **bureau Windows** (Python + PySide6) qui transforme des clips Twitch en vidéos verticales **9:16 (1080×1920)** et les publie sur **YouTube Shorts** et **TikTok** (ou export manuel).

> Ce n’est **pas** un site web.

## Fonctionnalités

- Recherche de clips Twitch (streamer / jeu, 24h / 7j / 30j), tri vues, filtre ≤ 60 s, anti-doublons
- 3 layouts FFmpeg : fond flouté, facecam split, letterbox + titres
- Sous-titres locaux **faster-whisper** (style Shorts)
- Publication YouTube (OAuth 2.0, token chiffré) + TikTok API ou dossier `tiktok_export/`
- File d’attente, planification, pilote automatique, icône barre système
- Config JSON + historique SQLite — aucune clé API en dur

## Prérequis

- Windows 10/11
- Python **3.11+**
- [FFmpeg](https://ffmpeg.org/download.html) (`ffmpeg.exe` + `ffprobe.exe` dans le PATH, ou dossier `ffmpeg/`, ou chemin dans Paramètres)
- Compte développeur Twitch (Client ID + Secret)
- Projet Google Cloud avec YouTube Data API v3 (OAuth client « Desktop »)
- (Optionnel) App TikTok Content Posting approuvée — sinon mode export

## Installation (développement)

```powershell
cd C:\Users\kingd\Documents\GitHub\clip2tube
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

Si l’activation du venv est bloquée :

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## Configuration rapide

1. Ouvrez **Paramètres** dans l’app
2. Collez **Twitch Client ID / Secret**
3. Collez **Google Client ID / Secret** (OAuth Desktop)
4. Indiquez le chemin de `ffmpeg.exe` (ou cliquez **Détecter**)
5. Ajoutez les logins de streamers suivis (un par ligne) pour l’auto-pilote
6. Allez dans **Comptes** → **Connecter YouTube** (navigateur OAuth)

Les secrets sont stockés dans `config/config.json` (ignoré par git) et les tokens OAuth sont **chiffrés** dans `data/`.

### Créer les clés Twitch

1. https://dev.twitch.tv/console → Register Application  
2. OAuth Redirect : `http://localhost`  
3. Copiez Client ID + créer un Client Secret

### Créer les clés Google / YouTube

1. Google Cloud Console → activer **YouTube Data API v3**  
2. Identifiants → Application de bureau OAuth  
3. Copiez Client ID + Client Secret dans Paramètres

## Utilisation

1. **Clips** — rechercher, cocher, « Envoyer au traitement »
2. **Traitement** — layout, musique, sous-titres, aperçu ; lancer
3. **File d’attente** — publier, planifier, réessayer
4. **Auto-pilote** — intervalle + limite / jour ; reste actif via la barre système (fermer la fenêtre = arrière-plan)

Variables de modèles : `{streamer}`, `{jeu}`, `{titre_clip}`, `{hashtags}`

## Packaging `.exe` (portable, hors dépôt)

```powershell
.\.venv\Scripts\Activate.ps1
powershell -ExecutionPolicy Bypass -File .\build\build_exe.ps1
```

Résultat :
- `dist\Clip2Tube\Clip2Tube.exe` — appli + dépendances + FFmpeg embarqué
- `dist\Clip2Tube-Portable.zip` — à copier sur n’importe quel PC Windows

Pas besoin de Python ni du repo Git sur la machine cible.  
Double-clic sur `Lancer_Clip2Tube.bat` ou `Clip2Tube.exe`.

> Premier usage des sous-titres : télécharge le modèle Whisper (internet, une fois).

## Structure

```
clip2tube/
├── main.py
├── requirements.txt
├── config/config.example.json
├── app/
│   ├── ui/            # PySide6
│   ├── services/      # Twitch, yt-dlp, FFmpeg, Whisper, YouTube, TikTok, scheduler
│   ├── models/
│   ├── db.py
│   └── utils/
└── build/build_exe.ps1
```

## Dépannage

| Problème | Piste |
|----------|--------|
| Twitch auth échoue | Vérifier Client ID/Secret |
| FFmpeg a échoué | Chemin `ffmpeg.exe`, codecs |
| YouTube OAuth | Type client = Desktop, API activée |
| Whisper lent | Modèle `tiny`/`base`, ou GPU CUDA |
| TikTok | Sans app approuvée → `output/tiktok_export/` |

## Licence

Usage personnel / éducatif. Respectez les conditions Twitch, YouTube et TikTok (droits sur les clips, crédits streamer).
