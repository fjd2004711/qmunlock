import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [
    react(),
    {
      name: "tauri-local-assets",
      transformIndexHtml(html) {
        return html.replace(/ crossorigin(="")?/g, "");
      },
    },
  ],
  // Tauri loads the production page from its custom protocol, so assets must
  // resolve relative to the bundled index.html rather than the web root.
  base: "./",
  build: {
    // Tauri's custom asset protocol does not need CORS credentials. Omitting
    // crossorigin keeps WebKit from treating local module files as opaque.
    rollupOptions: {
      output: {
        entryFileNames: "assets/[name]-[hash].js",
        chunkFileNames: "assets/[name]-[hash].js",
        assetFileNames: "assets/[name]-[hash][extname]",
      },
    },
  },
  clearScreen: false,
  server: { port: 1420, strictPort: true },
  envPrefix: ["VITE_", "TAURI_"]
});
