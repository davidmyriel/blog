// Renders index.html to a 1080x1350 MP4 for LinkedIn, one frame at a time.
// Usage: npm run render [-- --fps 30 --out multi-vector-demo.mp4]
import { chromium } from 'playwright';
import ffmpeg from 'ffmpeg-static';
import { spawn } from 'node:child_process';
import { mkdir, rm, writeFile } from 'node:fs/promises';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const dir = path.dirname(fileURLToPath(import.meta.url));
const arg = (name, fallback) => {
  const i = process.argv.indexOf(`--${name}`);
  return i > -1 ? process.argv[i + 1] : fallback;
};
const fps = Number(arg('fps', 30));
const out = path.resolve(dir, arg('out', 'multi-vector-demo.mp4'));
const frames = path.join(dir, '.frames');

await rm(frames, { recursive: true, force: true });
await mkdir(frames, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1080, height: 1350 } });
await page.goto(pathToFileURL(path.join(dir, 'index.html')).href + '?export=1&t=0');
await page.evaluate(() => document.fonts.ready);
await page.waitForFunction(() => typeof window.seek === 'function');
const duration = await page.evaluate(() => window.DURATION);
const total = Math.round(duration * fps);

for (let f = 0; f < total; f++) {
  const png = await page.evaluate(t => {
    window.seek(t);
    return document.getElementById('c').toDataURL('image/png').split(',')[1];
  }, f / fps);
  await writeFile(path.join(frames, `${String(f).padStart(5, '0')}.png`), Buffer.from(png, 'base64'));
  if (f % fps === 0) process.stdout.write(`\rframe ${f}/${total}`);
}
await browser.close();
process.stdout.write(`\rframe ${total}/${total}\n`);

await new Promise((resolve, reject) => {
  const p = spawn(ffmpeg, [
    '-y', '-framerate', String(fps), '-i', path.join(frames, '%05d.png'),
    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '16', '-preset', 'slow',
    '-movflags', '+faststart', out,
  ], { stdio: 'inherit' });
  p.on('exit', code => code === 0 ? resolve() : reject(new Error(`ffmpeg exited with ${code}`)));
});
await rm(frames, { recursive: true, force: true });
console.log(`wrote ${out}`);
