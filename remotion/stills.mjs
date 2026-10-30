// node stills.mjs props.json outdir t1 t2 ...   -> PNG stills (one bundle, many frames)
import { bundle } from "@remotion/bundler";
import { selectComposition, renderStill } from "@remotion/renderer";
import fs from "node:fs";
import path from "node:path";
const [propsPath, outDir, ...ts] = process.argv.slice(2);
const inputProps = JSON.parse(fs.readFileSync(propsPath, "utf8"));
const serveUrl = await bundle({ entryPoint: path.resolve("src/index.ts") });
const opts = { serveUrl, inputProps, browserExecutable: process.env.REMOTION_BROWSER || null, chromiumOptions: { gl: "swangle" } };
const composition = await selectComposition({ ...opts, id: "Reel" });
fs.mkdirSync(outDir, { recursive: true });
for (const t of ts) {
  await renderStill({ ...opts, composition, frame: Math.round(+t * 30), output: path.join(outDir, `t${(+t).toFixed(1).padStart(5, "0")}.png`) });
  console.log("still", t);
}
