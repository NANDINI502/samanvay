# Deploying MedBot Orchestrator

Two targets, one `Dockerfile`:

- **A. Hugging Face Spaces (Docker SDK)** — the simplest public demo URL.
- **B. Nebius Serverless AI Endpoints** — runs the app container on Nebius AI Cloud.

The app itself never runs a model locally: every Nemotron call goes to
Nebius Token Factory through `orchestrator/client.py`. So the container needs
only a CPU, and the only secret is your Token Factory API key.

## Rules that apply to both

- **The API key is never in the image.** `.dockerignore` excludes `.env` and
  every `.env.*`; the `Dockerfile` contains no key. Provide `NEBIUS_API_KEY`
  only as a platform secret (HF Space secret / Nebius SecretStash).
- Don't put the key on a command line you'll keep (shell history, CI logs,
  screenshots). The steps below either use a web form or read it with a
  hidden prompt.
- Health check: `GET /api/health` returns `200` with
  `{"status": "ok", "ready": ..., "mock": ..., "api_key_configured": ..., "indexes_ready": ...}`.
  It reports only *whether* a key is set, never the key. `ready` is `true`
  when retrieval indexes are built and the app is in mock mode or has a key.
  The Docker image's `HEALTHCHECK` calls it.
- If Token Factory rejects a call (bad key, network), `/api/ask` returns
  `503` with a redacted reason; red-flag deferrals still work because they
  run in code before any model call.

### Runtime configuration

| Variable | Secret? | Value |
| --- | --- | --- |
| `NEBIUS_API_KEY` | **yes** | Your Token Factory key |
| `NEMOTRON_ORCHESTRATOR_MODEL` | no | Confirmed model ID (run `python scripts/check_nebius.py`) |
| `NEMOTRON_AGENT_MODEL` | no | Confirmed model ID |
| `MEDBOT_MOCK_LLM` | no | `0` for live (image default), `1` for labelled stub replies |
| `NEBIUS_BASE_URL` | no | Optional; defaults to `https://api.tokenfactory.nebius.com/v1/` |
| `EMBED_BACKEND` | no | `tfidf` (image default) |
| `PORT` | no | Optional; image default `7860` |

Retrieval indexes are built when the container starts (a few seconds with
TF-IDF), so they always match `EMBED_BACKEND`.

## Test the image locally first (optional)

Needs Docker. `--env-file` passes your local `.env` at **run** time only; it
is not copied into the image.

```bash
docker build -t medbot-orchestrator .

# Offline demo, no key needed
docker run --rm -p 7860:7860 -e MEDBOT_MOCK_LLM=1 medbot-orchestrator

# Live, with the key from your local .env (not baked into the image)
docker run --rm -p 7860:7860 --env-file .env -e MEDBOT_MOCK_LLM=0 medbot-orchestrator

curl http://127.0.0.1:7860/api/health
```

Open http://127.0.0.1:7860.

---

## A. Hugging Face Spaces (Docker)

Reference: https://huggingface.co/docs/hub/spaces-sdks-docker and
https://huggingface.co/docs/hub/spaces-config-reference

1. **Create the Space.** On https://huggingface.co/new-space choose a name,
   SDK **Docker** (blank template), hardware **CPU basic** is enough.
2. **Add secrets and variables** (Space → Settings → Variables and secrets):
   - **New secret:** `NEBIUS_API_KEY` = your Token Factory key.
   - **New variables:** `NEMOTRON_ORCHESTRATOR_MODEL`, `NEMOTRON_AGENT_MODEL`
     (confirmed IDs), `MEDBOT_MOCK_LLM` = `0`.

   Per the HF docs, Space secrets and variables are injected into the
   container's environment at runtime. Don't use build-time secrets — the
   image doesn't need the key to build.
3. **Push the code.** The Space's `README.md` must start with the Spaces YAML
   header (`sdk: docker`, `app_port: 7860`). That header lives in
   `deploy/huggingface/README.md` so the GitHub README stays clean; it
   becomes the Space's README when you push:

   ```bash
   # from the repo root, with a Hugging Face access token that has write access
   git clone https://huggingface.co/spaces/<HF_USER>/<SPACE_NAME> ../medbot-space
   git archive HEAD | tar -x -C ../medbot-space          # tracked files only — never .env
   cp deploy/huggingface/README.md ../medbot-space/README.md
   cd ../medbot-space
   git lfs install && git lfs track "*.joblib"   # the Hub can reject binary files pushed without LFS/Xet
   git add -A && git commit -m "Deploy MedBot Orchestrator" && git push
   ```

   The only binary file is `models/cardiac/model.joblib` (7 KB). If the
   Space was created with a `.gitattributes` that already tracks `*.joblib`,
   the `track` line is a no-op.

   Edit `<GITHUB_REPO_URL>` in the Space README before pushing.
   `git archive` exports only files committed to git, so `.env` (git-ignored)
   can't be copied.
4. **Watch the build** in the Space's *Logs* tab. When it shows *Running*,
   open `https://<HF_USER>-<SPACE_NAME>.hf.space/api/health` and check
   `"ready": true, "mock": false, "api_key_configured": true`.
5. Click the **Multi-agent** and **Red flag** examples; the header should say
   **LIVE on Nebius Token Factory** and the pipeline trace should show
   latency and token counts per Nemotron call.

The Space URL to submit is `https://huggingface.co/spaces/<HF_USER>/<SPACE_NAME>`.

---

## B. Nebius Serverless AI Endpoints

References (Nebius docs):
- Endpoints quickstart: https://docs.nebius.com/serverless/quickstart/endpoints
- Managing endpoints (all `create` flags): https://docs.nebius.com/serverless/endpoints/manage
- Container Registry quickstart: https://docs.nebius.com/container-registry/quickstart
- SecretStash (CLI service name `mysterybox`): https://docs.nebius.com/mysterybox/secrets/create

Prerequisites (from the quickstart): Nebius AI Cloud CLI installed and
configured (`cat ~/.nebius/config.yaml` shows your project ID), `jq`,
Docker, membership of a group with at least the `editor` role, and quota
for at least one VM and one VPC allocation. You also need a subnet ID.

### 1. Build and push the image to Nebius Container Registry

```bash
export REGION_ID=<region_ID>            # e.g. the region of your project
export REGISTRY_PATH=$(nebius registry create \
  --name medbot-registry \
  --format json | jq -r ".metadata.id" | cut -d- -f 2)
nebius registry configure-helper        # Docker credential helper (run Docker as your user, not root)

export IMAGE=cr.$REGION_ID.nebius.cloud/$REGISTRY_PATH/medbot-orchestrator:v1
docker build --platform linux/amd64 -t "$IMAGE" .
docker push "$IMAGE"
```

Images from Container Registry in the same project need no registry
credentials on the endpoint.

### 2. Store the API key in SecretStash

Easiest and safest: in the web console's endpoint form, under **Secret
environment variables**, click **Create secret** with key `NEBIUS_API_KEY`.

Or with the CLI — the key is read from a hidden prompt so it doesn't land in
shell history:

```bash
read -rs NEBIUS_API_KEY && export NEBIUS_API_KEY
nebius mysterybox secret create \
  --name medbot-nebius-api-key \
  --secret-version-payload "[{\"key\": \"NEBIUS_API_KEY\", \"string_value\": \"$NEBIUS_API_KEY\"}]"
unset NEBIUS_API_KEY
```

The payload key must be exactly `NEBIUS_API_KEY`: `--env-secret` requires
the environment variable name to match a payload key in the secret.

### 3. Create the endpoint

```bash
nebius ai endpoint create \
  --name medbot-orchestrator \
  --image "$IMAGE" \
  --container-port 7860 \
  --env "MEDBOT_MOCK_LLM=0,NEMOTRON_ORCHESTRATOR_MODEL=<confirmed_id>,NEMOTRON_AGENT_MODEL=<confirmed_id>" \
  --env-secret "NEBIUS_API_KEY=medbot-nebius-api-key" \
  --platform cpu-d3 \
  --preset 4vcpu-16gb \
  --subnet-id <subnet_ID>
```

- `cpu-d3` / `4vcpu-16gb` is the CPU platform/preset used in the Nebius
  endpoints quickstart; the app needs no GPU. List what your project offers
  with `nebius compute platform list --parent-id <project_ID> --format json`.
- `--env` takes comma-separated `key=value` pairs; a key can't appear in
  both `--env` and `--env-secret`.
- **Authentication.** Without `--auth`, the endpoint needs no token, which
  is what lets judges open the demo in a browser (browsers can't add an
  `Authorization` header). Nebius recommends `--auth token` for production;
  with it, every request needs `Authorization: Bearer <token>`, so it suits
  API testing, not a public web demo. Either way, anyone who can reach the
  app can spend your Token Factory credits — stop the endpoint after judging.

### 4. Get the URL and check health

```bash
export ENDPOINT_ID=$(nebius ai endpoint get-by-name \
  --name medbot-orchestrator --format jsonpath='{.metadata.id}')
nebius ai endpoint get "$ENDPOINT_ID" --format json \
  | jq '{state: .status.state, urls: .status.public_endpoints}'

export ENDPOINT_URL=$(nebius ai endpoint get "$ENDPOINT_ID" --format json \
  | jq -r '.status.public_endpoints[] | select(startswith("https://"))' | head -1)
curl -sS "$ENDPOINT_URL/api/health"
```

Wait until the endpoint is running, then open `$ENDPOINT_URL` in a browser.

### 5. Operate

```bash
nebius ai endpoint logs "$ENDPOINT_ID"
nebius ai endpoint stop --id "$ENDPOINT_ID"     # compute isn't charged while stopped
nebius ai endpoint start --id "$ENDPOINT_ID"
nebius ai endpoint delete --id "$ENDPOINT_ID"
```

There is no in-place update: to ship a new image, push a new tag, create a
new endpoint, then delete the old one.

---

## What was verified before handing this over

- The image's file set (the repo minus everything in `.dockerignore`) was
  run with the image's start command, `MEDBOT_MOCK_LLM=0` and no key: the
  app started, built all retrieval indexes, `/api/health` reported
  `ready: false, api_key_configured: false`, red-flag deferrals worked, and
  model-backed questions returned `503`. No `.env` file was in the file set.
- **Not verified:** `docker build` itself (no Docker in the build
  environment), the Hugging Face build, and the Nebius endpoint — run the
  local Docker test above, then deploy.
