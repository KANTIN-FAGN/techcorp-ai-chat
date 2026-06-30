# TechCorp AI Chat

Interface web de chat permettant d'interagir en temps réel avec un modèle de langage servi par **Ollama**. Projet réalisé dans le cadre du **Challenge IA TechCorp (hackathon 7h)**.

## Contexte

TechCorp Industries a licencié son ancienne équipe technique suite à des soupçons de compromission du code et des données. La nouvelle équipe doit reprendre le travail laissé, valider l'intégrité du projet et finaliser le déploiement.

Deux missions composaient le challenge :

- **Mission critique — Production Ready** : déployer le modèle **Phi-3.5-Financial** (spécialisé finance/business) derrière un serveur d'inférence, avec une interface chat obligatoire pour l'utiliser en temps réel.
- **Mission expérimentale — R&D** : fine-tuner en LoRA un modèle médical expérimental à partir d'un dataset fourni (hors scope de ce dépôt web).

Le travail était réparti par filière (INFRA, IA, DATA, CYBER, DEV WEB). **Ce dépôt couvre la partie DEV WEB** : l'interface de chat qui consomme l'API du serveur d'inférence choisi par l'équipe INFRA — ici **Ollama**.

> ⚠️ **Note sécurité.** Un audit (voir [`docs/rapport_audit_securite.md`](docs/rapport_audit_securite.md)) a révélé une **backdoor délibérée** dans le modèle financier hérité de l'ancienne équipe : un trigger textuel caché, injecté dans les datasets d'entraînement, fait répondre le modèle avec de faux secrets d'infrastructure (clés AWS, VPN, SSH, etc.). Le modèle hérité **ne doit pas être déployé tel quel**, et les datasets fournis ne doivent pas être réutilisés pour un réentraînement sans nettoyage préalable.

## Architecture du dépôt

```
techcorp-ai-chat/
├── app/                  # Interface web de chat (React + Vite) — ce que documente ce README
├── tritton_server/       # Configuration Triton Inference Server (option de déploiement alternative)
├── models/                # Modèle Phi-3.5-Financial hérité
├── medical_dataset/       # Dataset pour le fine-tuning médical expérimental
├── scripts/               # Scripts d'entraînement et de tests
└── docs/                  # Documentation infra / sécurité (dont l'audit ci-dessus)
```

### Flux applicatif

```
Navigateur (React, port 3000)
        │  fetch streaming (NDJSON)
        ▼
Serveur Ollama  —  POST /api/chat
        │
        ▼
Modèle "techcorp-finance:latest" (ou modèle configuré)
```

Il n'y a **pas de backend applicatif** : le front appelle directement l'API REST d'Ollama (`/api/chat` pour la génération en streaming, `/api/tags` pour le contrôle de santé). Toute la donnée (conversations, thème, etc.) est persistée côté client via `localStorage`.

## Stack technique

- **React 18** + **Vite 6** — pas de framework UI, CSS pur avec variables pour le theming
- **Web Speech API** (navigateur) pour la dictée vocale et la synthèse vocale
- **Ollama** comme serveur d'inférence (API REST streaming)

## Fonctionnalités

### Conversation
- Streaming des réponses en temps réel, avec un **effet machine à écrire** (révélation lettre par lettre, façon ChatGPT) découplé du rythme brut des chunks réseau
- Indicateur **« en train d'écrire »** (points animés) avant l'arrivée du premier token
- **Régénérer** une réponse (ajoute une nouvelle réponse sous l'ancienne, sans l'écraser)
- **Copier** une réponse en un clic
- Suggestions de questions sur l'écran d'accueil, et message de bienvenue tiré aléatoirement à chaque visite
- **Scroll intelligent** : si l'utilisateur remonte lire l'historique pendant une génération, l'auto-scroll s'arrête ; un bouton flottant permet de revenir en bas

### Voix
- **Dictée vocale** (micro) : transcription en direct dans le champ de saisie via la Web Speech API (reconnaissance)
- **Lecture audio** des réponses à la demande (synthèse vocale)

### Historique des conversations
- Multi-conversations avec sidebar dédiée, persistées automatiquement (`localStorage`) — survit aux rafraîchissements
- **Nouvelle conversation** (bouton, ou raccourci clavier **⌘K / Ctrl+K**)
- **Renommer** / **Supprimer** une conversation (suppression confirmée par une popup, pas une alerte native)
- **Recherche** dans l'historique des conversations
- **Exporter** une conversation au format `.txt`
- **Effacer tout l'historique** (avec confirmation)

### Interface
- **Thème sombre / clair**, basculable, préférence mémorisée
- Design **responsive** (mobile, tablette, desktop)
- Sidebar **repliable** sur desktop, **drawer** sur mobile
- Indicateur de **statut du serveur Ollama** en temps réel (connecté / hors ligne / vérification), avec ping automatique périodique
- Compteur de caractères discret au-delà de 200 caractères saisis
- Animations soignées (apparition des messages, transitions, pulsations d'état)

## Lancer le projet en local

Prérequis : Node 18+, et [Ollama](https://ollama.com/download) installé et démarré avec le modèle souhaité.

```bash
cd app
cp .env.example .env   # ajuster les variables si besoin (voir ci-dessous)
npm install
npm run dev
```

L'application est servie sur **http://ynovws.com**.

### Variables d'environnement (`app/.env`)

| Variable | Description | Valeur par défaut |
|---|---|---|
| `VITE_OLLAMA_URL` | URL du serveur Ollama à contacter | `http://192.168.10.49:11434` |
| `VITE_OLLAMA_MODEL` | Nom du modèle Ollama à utiliser | `phi3.5` |

> En l'absence de `.env`, le code retombe sur le serveur de l'équipe (`http://192.168.10.49:11434`, modèle `techcorp-finance:latest`). Adapte ton `.env` si tu testes avec une instance Ollama locale.

### CORS

Si le navigateur bloque les requêtes vers Ollama, démarrer le serveur avec l'origine du front autorisée :

```bash
OLLAMA_ORIGINS=http://localhost:3000 ollama serve
```

## Structure du code (`app/src`)

```
src/
├── App.jsx                      # État global, gestion des conversations, orchestration du streaming
├── index.css                    # Design system (variables, thèmes clair/sombre, responsive)
├── components/
│   ├── Sidebar.jsx              # Historique, recherche, thème, export, suppression…
│   ├── ChatMessage.jsx          # Bulle de message + actions (copier/régénérer/écouter)
│   ├── ChatInput.jsx            # Champ de saisie, micro, compteur de caractères
│   ├── ConfirmDialog.jsx        # Popup de confirmation générique
│   └── BrandIcon.jsx            # Logo de l'application
└── lib/
    ├── ollama.js                 # Client API streaming vers Ollama
    ├── useLocalStorage.js        # Persistance générique en localStorage
    ├── useSpeechRecognition.js   # Dictée vocale (micro)
    ├── useSpeechSynthesis.js     # Lecture audio des réponses
    └── useTypewriter.js          # Effet machine à écrire
```
