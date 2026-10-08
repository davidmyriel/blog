// Cuts the rendered MP4 down to ~25s and makes a GIF from it.
// Each scene plays faster; captions stay on screen long enough to read.
// Usage: npm run short   (runs `npm run render` first if the MP4 is missing)
import ffmpeg from 'ffmpeg-static';
import { spawnSync } from 'node:child_process';
import { existsSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const dir = path.dirname(fileURLToPath(import.meta.url));
const src = path.join(dir, 'multi-vector-demo.mp4');
const mp4 = path.join(dir, 'multi-vector-demo-short.mp4');
const gif = path.join(dir, 'multi-vector-demo.gif');

// [start, end, speed] in seconds of the full video
const SEGMENTS = [
  [0, 4.5, 1.5],     // promise
  [4.5, 10.5, 1.75], // why it is accurate
  [10.5, 35, 1.75],  // the globe
  [35, 40, 1.5],     // proof
  [40, 41.5, 1],     // end card
];
const GIF_WIDTH = 600, GIF_FPS = 15;

const run = args => {
  const r = spawnSync(ffmpeg, ['-v', 'error', '-y', ...args], { stdio: 'inherit' });
  if (r.status !== 0) throw new Error('ffmpeg failed');
};
if (!existsSync(src)) spawnSync('node', [path.join(dir, 'render.mjs')], { stdio: 'inherit' });

const parts = SEGMENTS.map(([a, b, s], i) => `[0:v]trim=${a}:${b},setpts=(PTS-STARTPTS)/${s}[v${i}]`);
const concat = `${SEGMENTS.map((_, i) => `[v${i}]`).join('')}concat=n=${SEGMENTS.length}:v=1:a=0,fps=30[out]`;
run(['-i', src, '-filter_complex', [...parts, concat].join(';'), '-map', '[out]',
  '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '16', '-preset', 'slow', '-movflags', '+faststart', mp4]);

// two-pass palette keeps the orange clean and the file small
run(['-i', mp4, '-filter_complex',
  `fps=${GIF_FPS},scale=${GIF_WIDTH}:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=64:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle`,
  '-loop', '0', gif]);

const mb = f => (statSync(f).size / 1e6).toFixed(1) + ' MB';
console.log(`wrote ${path.basename(mp4)} (${mb(mp4)}) and ${path.basename(gif)} (${mb(gif)})`);
