# DockMind

DockMind turns warehouse images into truck loading plans, 3D layouts, role-specific UIs, and executable agent skills.

## Demo

```bash
cd dockmind-demo
npm run dev:yolo
```

Open `http://127.0.0.1:4173`.

Use the **YOLO** button after uploading a real cargo image. It sends the image to
`POST /api/detect`, runs `yolov8s-world.pt` with cargo prompts, and draws the
returned boxes on the actual displayed image area. The first run may download
YOLO/CLIP weights; later runs are cached.

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
