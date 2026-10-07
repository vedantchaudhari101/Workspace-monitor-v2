# Deploying a live demo

The whole product (web app, API, CV pipeline, database) runs in one container built from the root `Dockerfile`. PyTorch and the YOLO models need about 2 GB of RAM, which rules out most free tiers. **Hugging Face Spaces** is the recommended free option: 2 vCPU, 16 GB RAM, Docker support and a public `https://<user>-<space>.hf.space` URL.

## Option A — Hugging Face Spaces (free, recommended)

1. Create an account at huggingface.co.
2. **New Space** → choose a name (for example `workspace-monitor`) → SDK **Docker** → template **Blank** → hardware **CPU basic (free)** → visibility **Public**.
3. Push this repository to the Space:

   ```bash
   git clone https://huggingface.co/spaces/<your-user>/workspace-monitor hf-space
   cd hf-space
   # copy the project in (everything except node_modules, dist, .git)
   rsync -a --exclude node_modules --exclude dist --exclude .git ../workspace-monitor/ ./
   # the Space reads its settings from the README front matter
   cp deploy/huggingface/README.md README.md
   git add . && git commit -m "Deploy Workspace Monitor" && git push
   ```

   Pushing requires a Hugging Face access token with write permission (Settings → Access Tokens), used as the git password.

4. In the Space, open **Settings → Variables and secrets** and add:

   | Name | Type | Value |
   |---|---|---|
   | `SECRET_KEY` | Secret | a long random string (`openssl rand -hex 32`) |
   | `ADMIN_PASSWORD` | Secret | the password visitors will use |
   | `SEED_DEMO` | Variable | `true` to include the example building (labelled as demo data) |
   | `SHOW_DEMO_LOGIN` | Variable | `true` if visitors should get a "fill in the demo account" button |

5. The first build takes 10–15 minutes. When the Space shows **Running**, your link is live.

Things to know about the free tier:

* **Storage is temporary.** The database and uploads reset whenever the Space restarts. Uploaded videos are deleted after processing anyway; only results are kept until the next restart.
* **It sleeps after 48 hours without visitors.** The first visit afterwards takes about a minute to wake it.
* **Everyone shares one admin account** when `SHOW_DEMO_LOGIN=true`. Anyone with the link can upload videos and approve recommendations. Leave it off and share the password privately if that matters.
* **Processing speed** is about real time for a 720p video on the 2 vCPU tier. Keep showcase clips under a minute; uploads are capped at 200 MB in the container.

### Use your own sample video

The image downloads a small CC BY 4.0 clip so visitors can click **Try the sample video**. It's useful for showing the pipeline, but the people in it sit in front of chairs that calibration can't see, so it rarely registers occupancy. For a convincing demo, record your own clip (fixed elevated camera, chairs visible and empty at the start, people sitting down and leaving over 30–60 s, with their permission), host it anywhere with a direct download URL (a GitHub release asset works), and set it as a build argument in the `Dockerfile`:

```dockerfile
ARG SAMPLE_VIDEO_URL=https://github.com/<you>/<repo>/releases/download/v1/demo.mp4
ARG SAMPLE_VIDEO_CREDIT="Recorded at IIIT Guwahati with permission"
```

## Option B — any Docker host

```bash
docker build -t workspace-monitor .
docker run -d -p 80:7860 \
  -e SECRET_KEY=... -e ADMIN_PASSWORD=... -e SEED_DEMO=true \
  -v wm-data:/data \
  workspace-monitor
```

Mount `/data` to keep the database between restarts. This works on a small VM (2 vCPU / 4 GB RAM or more), Railway, Render paid instances or Fly.io machines with at least 2 GB of memory.

## Option C — with PostgreSQL

```bash
cp .env.example .env    # change the secrets
docker compose up -d --build
```

The app applies database migrations on startup. To upgrade an existing database created before migrations existed, start the new version once: it detects the old schema, stamps it and upgrades it in place.

## After deploying

* Put the link in your README, résumé and LinkedIn project entry.
* Open it once in a private window to check the sign-in flow a visitor will see.
* If the Space shows an error, the **Logs** tab has the container output.
