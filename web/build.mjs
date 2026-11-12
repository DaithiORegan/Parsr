import { build } from "esbuild";
import { copyFile, mkdir } from "node:fs/promises";
await mkdir("public/vendor", { recursive: true });
await build({
  entryPoints: ["src/app.js"],
  bundle: true,
  format: "esm",
  outfile: "public/app.js",
  minify: true,
});
await copyFile(
  "node_modules/pdfjs-dist/build/pdf.worker.min.mjs",
  "public/vendor/pdf.worker.min.mjs",
);
