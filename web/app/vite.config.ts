import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// publicDir points at web/public so the export's web/public/site_data.json
// is served at /site_data.json in dev, preview and the built dist/.
export default defineConfig({
  plugins: [react()],
  publicDir: "../public",
  server: { port: 5173, host: "127.0.0.1", allowedHosts: [".trycloudflare.com"] },
  preview: { port: 4173, host: "127.0.0.1", allowedHosts: [".trycloudflare.com"] },
});
