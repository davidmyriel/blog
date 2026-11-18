# Multi-vector search demo

A 41.5-second animated explainer of TopK's sparse multi-vector encoding, sized for LinkedIn (1080 × 1350).

## Preview

Open `index.html` in a browser. It loops with a pause button and scrubber.

- `?export=1` hides the controls.
- `?t=21` freezes on one moment.

## Render the MP4

```bash
npm install
npx playwright install chromium
npm run render
```

This writes `multi-vector-demo.mp4` at 30 fps. Use `npm run render -- --fps 60` for a smoother version.

## Story

| Time | Scene |
|---|---|
| 0–4.5s | Multi-vector search finds the best answers, but has been too slow at scale. |
| 4.5–10.5s | It compares every query word with every document word. |
| 10.5–35s | The globe: reference points, closeness, keep 8, one sparse list, shared slots. |
| 35–40s | 5–8× faster on MS MARCO (39.9 ms vs 221 ms and 310 ms, top 100 results). |
| 40–41.5s | End card. |

The latency numbers come from the SMVE blog post's latency chart. The globe uses real nearest-neighbor math on made-up 3D vectors, so it illustrates the method rather than showing model output.
