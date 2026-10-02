# HELIX — Helm chart

Deploy di HELIX (backend FastAPI + frontend Nginx + ChromaDB) su Kubernetes.

## Prerequisiti
- Kubernetes con una **StorageClass di default** (provisioning dinamico dei PVC).
- Un **Ingress controller** (testato con `ingress-nginx`).
- Immagini su GHCR: `ghcr.io/rvoyat/helix` (backend) e `ghcr.io/rvoyat/helix-frontend`
  (frontend — buildato da `frontend/Dockerfile`, vedi workflow CI).
- Se i repo GHCR sono privati: crea un pull secret e impostalo in `imagePullSecrets`.

## Architettura
- **Single-host / same-origin**: il frontend chiama le API sullo stesso host
  (`API_BASE=''`). L'**Ingress** instrada per path: `/auth`, `/chat`, `/ambiti`,
  `/docs-list`, `/docs`, `/admin`, `/health` → backend; tutto il resto → frontend.
- **Stato mutabile del backend** (`users.json`, `ambiti.json`, `settings_llm.json`,
  `docs/`) su **PVC**, seminato da ConfigMap/Secret via **initContainer** (`cp -n`:
  non sovrascrive agli upgrade).
- **ChromaDB** persiste su PVC dedicato.

## Install
```bash
helm install helix ./helm/helix \
  -n helix --create-namespace \
  -f ./helm/helix/values-dev.yaml \
  --set ingress.host=helix.example.com \
  --set secrets.claudeApiKey=$CLAUDE_API_KEY
```

> Non committare chiavi reali. Usa `--set`, un file `-f` non tracciato, oppure
> SealedSecrets / External Secrets in produzione.

## Valori principali
| Chiave | Default | Note |
|---|---|---|
| `backend.image.repository` | `ghcr.io/rvoyat/helix` | |
| `frontend.image.repository` | `ghcr.io/rvoyat/helix-frontend` | |
| `config.llmProvider` | `claude` | `claude` \| `gemini` |
| `config.ingestionProvider` | `langchain` | `langchain` \| `llamaparse` |
| `secrets.claudeApiKey` / `geminiApiKey` / `llamaparseApiKey` | `""` | via `--set` |
| `persistence.*.storageClassName` | `""` | vuoto = default cluster |
| `ingress.host` | `helix.example.com` | |
| `ingress.tls.enabled` | `false` | con `tls.secretName` |

## Verifica
```bash
kubectl -n helix get pods,svc,ingress,pvc
# aggiungi <ingress-ip> helix.example.com a /etc/hosts, poi apri l'host nel browser
```

Login admin di default: `rvoyat` (cambia la password dopo il primo accesso).

## Upgrade
```bash
helm upgrade helix ./helm/helix -n helix -f ./helm/helix/values-dev.yaml ...
```
I file mutabili NON vengono riseminati (sono già sul PVC). Per ripartire da zero,
elimina i PVC: `kubectl -n helix delete pvc helix-backend-data helix-chromadb`.
