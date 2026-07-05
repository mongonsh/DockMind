# DockMind

DockMind turns warehouse images into truck loading plans, 3D layouts, role-specific UIs, and executable agent skills.

## Demo

```bash
cd dockmind-demo
npm run dev:yolo
```

Open `http://127.0.0.1:4173`.

Use **Camera** -> **Capture** for live cargo intake, or upload a real cargo
image. **YOLO** sends the frame to `POST /api/detect`, runs `yolov8s-world.pt`
with cargo prompts, and draws the returned boxes on the actual displayed image
area. **Analyze** sends those real detections to `POST /api/analyze-cargo`;
Gemini turns them into a cargo manifest when `GEMINI_API_KEY` is configured.
The first YOLO run may download CLIP weights; later runs are cached.

## Real AI endpoints

- `GET /api/config` checks which integrations are configured.
- `POST /api/detect` runs YOLO / YOLO-World cargo detection.
- `POST /api/analyze-cargo` turns real detections into cargo manifest data.
- `POST /api/agent-skill` generates a gstack-compatible agent skill with Gemini.
- `POST /api/voice-command` parses voice commands into DockMind actions.
- `POST /api/crustdata` is an optional Crustdata proxy for account-specific enrichment.

The app never exposes secret values to the browser. Put secrets in `.env` locally
or in deploy environment variables:

```bash
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-3.5-flash,gemini-flash-latest,gemini-2.5-flash
GOOGLE_CLOUD_PROJECT_ID=...
GOOGLE_CLOUD_REGION=us-central1
GOOGLE_CLOUD_ACCESS_TOKEN=...
CRUSTDATA_API_KEY=...
SHISA_API_KEY=...
SHISA_API_URL=...
GBRAIN_ENABLED=true
```

Current voice mode uses browser speech recognition and speech synthesis. If
Shisa credentials are present, `/api/config` reports Shisa as available; the
voice surface is ready for a Shisa-specific adapter.

If you need to reinstall the local YOLO environment:

```bash
npm run setup:yolo
```

## Optional Local Renders

Generate a Blender render and GLB from the sample plan:

```bash
npm run render:blender
```

Run the YOLO detector wrapper:

```bash
npm run detect:yolo
```

The default detector uses YOLO-World prompts: cardboard box, cargo box, package,
carton, crate, and pallet.

## Pitch

DockMind is a company brain for the loading dock. It reads warehouse cargo, plans a truck load, shows a different interface to each role, and exports skills that AI agents can execute.

## Deploy

Render is configured with `render.yaml`.

1. Push this repo to GitHub.
2. Create a Render Blueprint from `render.yaml`.
3. Add environment variables for Gemini, Crustdata, Shisa, and `GBRAIN_ENABLED`.
4. Deploy the Docker service.

The Docker image installs YOLO dependencies and serves the app with
`scripts/dockmind_server.py`.

## GStack / GBrain

- Project skills live in `.agents/skills/dockmind-loader-agent` and
  `.agents/skills/dockmind-voice-agent`.
- `.gbrain-source` pins this repo to `https://github.com/mongonsh/DockMind.git`.
- `CLAUDE.md` includes gstack skill routing and gbrain search guidance.
- On a machine with gbrain installed, run `/sync-gbrain` to index the repo.
