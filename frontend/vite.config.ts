import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The browser calls /api/... on Vite itself, which forwards it to the API container.
// This way no CORS setup is needed.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://api:8000",
    },
  },
});
