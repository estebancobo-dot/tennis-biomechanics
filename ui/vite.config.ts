// P0.5a (15-11, #305): the application's interface, built to one self-contained HTML file (no server: it opens from
// disk in the PC's window and in the tests); its data are put in when it opens (tennisbio.app.p0)
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { viteSingleFile } from "vite-plugin-singlefile";

export default defineConfig({
  plugins: [react(), viteSingleFile()],
  base: "./",
  build: { outDir: "../src/tennisbio/app/p0", emptyOutDir: true, target: "es2020" },
});
