# DockMind 90-Second Demo Script

## Opening
Every loading dock has the same problem: the warehouse knows what is in front
of them, the truck has hard physical limits, and the plan still lives in
someone's head.

DockMind turns that messy moment into a company brain for logistics operations.

## Live Demo
First, I open the live camera intake. I click **Camera**, then **Capture**.
DockMind sees the actual cargo bay, runs YOLO on the image, and marks the boxes
directly on the warehouse frame.

Now I click **Analyze**. Qwen turns those real detections into a cargo manifest:
which boxes are frozen, which are fragile, which stop they belong to, and what
constraints matter.

Next, DockMind plans the truck. If I choose a regular 4-ton truck, it flags the
cold-chain problem. If I switch to the refrigerated truck, the interface changes
and the plan becomes safe.

The important part is that this is not one dashboard. It becomes a dynamic
interface for each role. The loader sees exact bay positions. The driver sees
the unload order. Ops sees the exceptions. The customer sees only safe status.

Finally, I click **Generate Agent**. DockMind exports a gstack-compatible skill
that an AI agent can execute: step-by-step loading instructions, inputs, safety
checks, and done criteria.

## Close
So DockMind is not a chatbot for logistics. It is a company brain for the
loading dock: camera in, truck plan out, agent skill ready.

The wedge is simple: one warehouse photo becomes the loading plan.
