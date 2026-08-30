# Deploying Deepwell on AWS (bare EC2, no Docker)

This runs Deepwell on a single EC2 instance exactly like it runs locally:
a Python venv + Ollama on the same box. No Docker, no code changes needed to
run — only a shared password for exposing it to the internet.

## 1. Launch an instance
- **OS:** Ubuntu 22.04 or 24.04.
- **Size:**
  - `g5.xlarge` (NVIDIA GPU) for local-like LLM speed — recommended for testers.
    Use an NVIDIA/Deep Learning AMI, or install drivers, so Ollama uses the GPU.
  - `m6i.xlarge` (CPU only) works but `llama3.1:8b` generation is slow.
- **Storage:** root EBS 100 GB+ (models + any ZIMs). EBS persists across reboots.

## 2. Security group
- Port **22** (SSH): your IP only.
- Port **8000** (the app): `0.0.0.0/0` so family can reach it. The shared
  password (step 6) is what protects it — not an IP allowlist.
  (If you add Caddy for HTTPS, open 80/443 instead and keep 8000 internal.)

## 3. Harden the instance metadata endpoint (important)
The `/ingest/*` routes fetch arbitrary user-supplied URLs server-side. Enforcing
IMDSv2 with a hop limit of 1 prevents that from being abused to steal IAM
credentials from the metadata endpoint:

```
aws ec2 modify-instance-metadata-options \
  --instance-id <your-instance-id> \
  --http-tokens required --http-put-response-hop-limit 1
```

(Or set it in the console: Actions → Instance settings → Modify instance metadata options.)

## 4. Install system deps + Ollama
```
sudo apt update && sudo apt install -y python3-venv git
curl -fsSL https://ollama.com/install.sh | sh   # installs + starts ollama.service
ollama pull llama3.1:8b
```

## 5. Get the app + install Python deps
```
git clone <your-repo-url> ~/deepwell
cd ~/deepwell
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```
The frontend is already built into `app/static/`, so Node is not required on the
server. (If you change the frontend, rebuild locally with `cd frontend && npm run
build` and redeploy.)

You also need the corpus in `data/` (SQLite DB + FAISS index + sources). Either
build it on the instance (`python run_pipeline.py`, needs Ollama running) or copy
your local `data/` up with `rsync`/`scp`.

## 6. Set the shared password
```
cp .env.example .env
# edit .env and set a strong DEEPWELL_PASSWORD
```
Any username works at the browser login prompt; only the password is checked.
Leaving `DEEPWELL_PASSWORD` empty runs the app fully open (local-dev behaviour).

## 7. Run it as a service
```
sudo cp deploy/deepwell.service /etc/systemd/system/deepwell.service
# edit the User/paths in the unit if you didn't use ubuntu + ~/deepwell
sudo systemctl daemon-reload
sudo systemctl enable --now deepwell
sudo systemctl status deepwell
journalctl -u deepwell -f          # first start downloads embed/reranker weights
```

## 8. Use it
Browse to `http://<instance-public-ip>:8000`, enter the shared password.
The Ask, Library, Add, and Debug pages all work as they do locally.

## Optional: HTTPS with a domain
HTTP Basic sends the password base64-encoded (not encrypted). For a longer-lived
test, put Caddy in front for automatic TLS (needs a domain pointed at the instance):

```
sudo apt install -y caddy
# /etc/caddy/Caddyfile:
#   deepwell.example.com {
#       reverse_proxy 127.0.0.1:8000
#   }
sudo systemctl restart caddy
```
Then open 443 (and 80 for the ACME challenge) in the security group instead of 8000.

## Notes
- **Single process only.** The FAISS index and the ingest job registry are held
  in memory in one process; run a single uvicorn worker (the unit does). Fine for
  a handful of testers.
- **Streaming:** if you later add a load balancer, raise its idle timeout (long
  answers/ingests exceed the default 60s) and don't put CloudFront in front of the
  streaming endpoints (it buffers).
