# HELIX su Kubernetes — design del chart Helm

> Documento di design del chart `helm/helix`. Spiega **perché** il chart è fatto
> così (vincoli emersi dal codice e scelte adottate), a complemento del
> [`README.md`](./README.md) che ne descrive l'uso.
>
> **Stato: implementato e verificato.** Il chart installa i tre servizi, con
> config/segreti esternalizzati in ConfigMap/Secret e persistenza su PVC,
> accessibile via Ingress. Verifica end-to-end eseguita su minikube: pods
> `Running`, PVC `Bound`, initContainer `seed` completato, routing Ingress
> corretto, login admin `rvoyat`, e persistenza confermata dopo il restart del
> backend. Vedi [Verifica su cluster locale](#verifica-su-cluster-locale-minikube).

## Contesto e obiettivo

HELIX nasce con `docker-compose` (tre servizi: `chromadb`, `backend`, `frontend`).
Per portarlo su Kubernetes con un chart riusabile, cinque vincoli emersi dal codice
hanno guidato il design:

1. **Solo il backend era su un registry** (`ghcr.io/rvoyat/helix:latest`). In
   compose il frontend è `nginx:alpine` con i file `frontend/` (~120 KB)
   **bind-montati** dall'host; in K8s il bind mount non esiste → serve
   un'**immagine frontend dedicata**.
2. **Il browser chiamava il backend su `http://localhost:8092` hardcoded**
   (`frontend/login.html`, `index.html`, `docs.html`, `admin.html`,
   `helix-brand.js`). In cluster quell'host non è raggiungibile → si adotta un
   modello **single-host same-origin**: `API_BASE=''` e lo split statico/API è
   fatto dall'Ingress per path.
3. **Il backend scrive a runtime**: `users.json` (`backend/auth.py`),
   `ambiti.json` (`backend/main.py:_save_ambiti_config`), `settings_llm.json`
   (`backend/llm_settings.save`) e carica PDF in `DOCS_FOLDER`
   (`backend/main.py`, upload/reindex). Questi file **non** possono stare in
   ConfigMap/Secret read-only → vanno su un **PVC scrivibile**, seminato una
   tantum da ConfigMap/Secret via **initContainer**.
4. I path dei file mutabili sono **relativi al WORKDIR `/app`** (`./users.json`,
   `./ambiti.json`, `./settings_llm.json`); `DOCS_FOLDER` è invece configurabile
   via env. L'immagine backend resta invariata (nessun rebuild): si usano
   **subPath mount** dal PVC.
5. **Segreto committato in chiaro**: `LLAMAPARSE_API_KEY` in `.env` e
   `settings_llm.json`. Da **ruotare** e gestire solo via Secret (vedi
   [Sicurezza](#sicurezza)).

## Scelte adottate

- **Frontend**: nuova immagine nginx + statici (non più bind mount).
- **Accesso**: single-host same-origin, realizzato con **routing per path a
  livello di Ingress** (nessun reverse proxy applicativo aggiuntivo).
- **Storage**: StorageClass di **default** del cluster; `storageClassName`
  configurabile (vuoto = default).

## Modifiche al sorgente (propedeutiche all'immagine frontend)

- URL hardcoded `http://localhost:8092` sostituito con **same-origin**
  (`API_BASE = ''`) in `frontend/login.html`, `index.html`, `docs.html`,
  `admin.html`, `helix-brand.js`. Così `${API_BASE}/auth/login` diventa
  `/auth/login`, sullo stesso host dell'Ingress.
- Nuovo `frontend/Dockerfile`: `FROM nginx:alpine`,
  `COPY frontend/ /usr/share/nginx/html`,
  `COPY nginx.conf /etc/nginx/conf.d/default.conf` (nginx resta solo-statico; lo
  split API lo fa l'Ingress).
- `frontend/Dockerfile` **escluso dal context** via `.dockerignore`: `COPY frontend/`
  altrimenti lo pubblicherebbe su `http://<host>/Dockerfile`. BuildKit legge
  comunque il Dockerfile indicato da `-f frontend/Dockerfile` anche se
  dockerignorato, quindi il build continua a funzionare.
- CI: build/push dell'immagine `helix-frontend` oltre a quella backend.

## Struttura del chart

```
helm/helix/
  Chart.yaml
  values.yaml
  templates/
    _helpers.tpl                 # nomi, label comuni, selettori
    configmap-backend-env.yaml   # env NON segreti
    secret-backend-env.yaml      # env segreti (chiavi API)
    configmap-seed.yaml          # seed ambiti.json (non sensibile)
    secret-seed.yaml             # seed users.json + settings_llm.json (sensibili)
    backend-pvc.yaml
    backend-deployment.yaml      # initContainer di seeding + subPath mount
    backend-service.yaml
    chromadb-pvc.yaml
    chromadb-deployment.yaml
    chromadb-service.yaml
    frontend-deployment.yaml
    frontend-service.yaml
    ingress.yaml
    NOTES.txt
```

## Dettaglio componenti

### ChromaDB
- Deployment (replica 1, `strategy: Recreate` perché PVC RWO) con
  `chromadb/chroma:latest`.
- Env: `IS_PERSISTENT=TRUE`, `PERSIST_DIRECTORY=/chroma/chroma`.
- PVC montato su `/chroma/chroma`.
- Probe liveness/readiness: `GET {{ chromadb.heartbeatPath }}` su `:8000`,
  **default `/api/v2/heartbeat`**.
- Service ClusterIP `:8000` → il nome del service alimenta `CHROMA_HOST`.

> **Nota probe v2.** L'immagine `chromadb/chroma:latest` serve ora solo la **v2**
> dell'API: `/api/v1/heartbeat` risponde `410 Gone`, facendo fallire le probe e
> mandando il pod in `CrashLoopBackOff`. Il path è stato reso configurabile via
> `chromadb.heartbeatPath` (default v2) nel commit `ae91f9e`. Usare
> `/api/v1/heartbeat` solo con immagini chroma pre-0.6.

### Backend
- Deployment (replica 1, `strategy: Recreate`), immagine da values
  (`backend.image.{repository,tag}`), porta `8092`.
- **Env da ConfigMap** (`envFrom`): `GEMINI_MODEL`, `DOCS_FOLDER=/app/docs`,
  `INGESTION_PROVIDER`, `CHROMA_HOST=<chromadb-svc>`, `CHROMA_PORT=8000`.
- **Env da Secret** (`envFrom`): `GEMINI_API_KEY`, `CLAUDE_API_KEY`,
  `LLAMAPARSE_API_KEY`.
- **PVC** `helix-backend-data` (RWO) con 4 **subPath mount** scrivibili e persistenti:
  - `/app/users.json` (subPath `users.json`)
  - `/app/ambiti.json` (subPath `ambiti.json`)
  - `/app/settings_llm.json` (subPath `settings_llm.json`)
  - `/app/docs` (subPath `docs`, directory)
- **initContainer `seed`**: monta il PVC e i volumi ConfigMap/Secret di seed su
  `/seed`, poi copia i file nel PVC **solo se assenti** (`cp -n`). Così le
  modifiche fatte dalla UI admin non vengono sovrascritte agli upgrade.
- Probe liveness/readiness: `GET /health` su `:8092`.
- Service ClusterIP `:8092`.

> **Duplicazione chiavi.** Le API key stanno sia negli env (`backend/config.py`)
> sia in `settings_llm.json` (`backend/llm_settings.py`, usato a runtime dal
> `RAGAgent`). Il seed di `settings_llm.json` deriva dagli **stessi valori** del
> Secret per coerenza al primo boot; dopodiché la copia su PVC (modificabile da UI
> admin) è autoritativa.

### Frontend
- Deployment con l'immagine `helix-frontend` (nginx + statici), porta `80`.
- Service ClusterIP `:80`. Probe `GET /`.

### Ingress (single-host, same-origin)
- Un host (`ingress.host`), TLS opzionale.
- Routing per path (`pathType: Prefix`):

  | Path | Service |
  |------|---------|
  | `/auth`, `/chat`, `/ambiti`, `/docs-list`, `/docs`, `/admin`, `/health` | **backend:8092** |
  | `/` (catch-all) | **frontend:80** |

- Il confine per-elemento del Prefix evita collisioni: `/docs` instrada `/docs/...`
  e `/docs-list` (regola dedicata) al backend, mentre lo statico `/docs.html`
  resta sul frontend.

## `values.yaml` (sintesi)

- `backend.image.{repository,tag}`, `frontend.image.{repository,tag}`,
  `chromadb.image`.
- `chromadb.heartbeatPath` (default `/api/v2/heartbeat`).
- `resources` e `replicaCount` per servizio.
- `persistence.{backend,chromadb}.{size, storageClassName}` (vuoto = default).
- `ingress.{enabled, className, host, tls}`.
- `config`: `geminiModel`, `claudeModel`, `llmProvider`, `ingestionProvider`,
  `docsFolder`.
- `secrets`: `geminiApiKey`, `claudeApiKey`, `llamaparseApiKey` — da passare via
  `--set` o un file `-f` non committato; **non** mettere valori reali nel chart.
- `seed.users` / `seed.ambiti`: contenuto iniziale di `users.json` / `ambiti.json`.
- `imagePullSecrets`: per registry privati (GHCR, ECR, …).

## Sicurezza

- **Ruotare** la `LLAMAPARSE_API_KEY` committata in passato e rimuoverla da
  `.env` / `settings_llm.json` tracciati. *(TODO aperto.)*
- Secret gestiti fuori dal repo (`--set`, SealedSecrets o External Secrets in
  produzione).
- `users.json` contiene hash SHA-256 di password **senza salt**
  (`backend/auth.py`): accettabile per il seed ma da considerare debito tecnico.

## Verifica end-to-end

1. `helm lint helm/helix`
2. `helm template helm/helix -f values-dev.yaml` → ispezione dei manifest.
3. Install su cluster locale (kind/minikube) con ingress-nginx:
   `helm install helix helm/helix -n helix --create-namespace -f values-dev.yaml --set secrets.llamaparseApiKey=...`
4. `kubectl get pods,svc,ingress,pvc -n helix` → tutti `Running`/`Bound`.
5. Aprire l'host Ingress: login (`rvoyat`), verifica chat, **upload PDF** da
   Gestione Documenti, **reindex**, creazione **ambito** e **utente** da admin.
6. Riavviare il pod backend e verificare che utenti/ambiti/documenti **persistano**
   (PVC).
7. Probe: `kubectl describe pod` senza restart loop; `/health` e
   `/api/v2/heartbeat` OK.

### Verifica su cluster locale (minikube)

Procedura usata per il collaudo con immagini da un registry privato (scope:
**deploy + UI + persistenza**, senza chat né chiavi LLM). I valori specifici del
registry vanno in un file di override **non committato** (es. `values-ecr.yaml`,
git-ignored).

1. **Ingress controller**: `minikube addons enable ingress` (classe `nginx`).
2. **Namespace + pull secret** per il registry privato:
   ```
   kubectl create namespace helix
   kubectl -n helix create secret docker-registry <pull-secret> \
     --docker-server=<registry> --docker-username=<user> --docker-password=<token>
   ```
3. **Override values** (non committato): `backend.image` / `frontend.image` che
   puntano al registry privato, `imagePullSecrets: [{ name: <pull-secret> }]`,
   `ingress.host`, eventuali dimensioni PVC ridotte. `chromadb.image` resta su
   Docker Hub (nessuna auth).
4. **Install**: `helm install helix ./helm/helix -n helix -f <override>.yaml`
5. **Rollout**: `kubectl -n helix rollout status deploy/helix-chromadb deploy/helix-backend deploy/helix-frontend`

**Controlli eseguiti (esito OK):**
- `kubectl -n helix get pods,svc,ingress,pvc` → tutto `Running`/`Bound`;
  initContainer `seed` completato; PVC legati.
- Routing Ingress (`curl --resolve <host>:80:<ingress-ip>`):
  `GET /` → 200 (frontend); `GET /health` → 200 (backend); `POST /auth/login` con
  credenziali errate → 401 JSON (prova che il path API va al backend); login admin
  `rvoyat` → token.
- **Persistenza**: con token admin creato un ambito via `POST /ambiti`, poi
  `kubectl -n helix rollout restart deploy/helix-backend`; dopo il restart
  l'ambito è ancora presente (`GET /ambiti`) → conferma PVC + subPath + seeding
  `cp -n`.
- Fallback se l'IP dell'Ingress non è raggiungibile dall'host: `minikube tunnel`
  oppure `kubectl -n ingress-nginx port-forward svc/ingress-nginx-controller 8080:80`
  e accesso via `http://<host>:8080`.

**Cleanup**: `helm uninstall helix -n helix && kubectl delete ns helix` (rimuove
anche i PVC).

## Note

- Backend e ChromaDB usano PVC **RWO** con `strategy: Recreate` (replica singola):
  lo stato attuale dell'app non è progettato per scalare orizzontalmente (sessioni
  auth in memoria in `backend/auth.py`, indicizzazione locale). La scalabilità
  multi-replica è **fuori scope**.
