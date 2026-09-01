import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
// Build output is consumed directly by FastAPI's StaticFiles mount at /static,
// so the base path and outDir must line up with app/main.py.
export default defineConfig({
    plugins: [react()],
    base: "/static/",
    build: {
        outDir: "../app/static",
        emptyOutDir: true,
    },
    server: {
        proxy: {
            "/ask": "http://localhost:8000",
            "/search": "http://localhost:8000",
            "/debug/search": "http://localhost:8000",
            "/library/list": "http://localhost:8000",
            "/stats": "http://localhost:8000",
            "/categories": "http://localhost:8000",
            "/pdf": "http://localhost:8000",
            "/zim": "http://localhost:8000",
        },
    },
});
