import { defineConfig } from "vite";
import uni from "@dcloudio/vite-plugin-uni";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [uni()],
  build: {
    // DCloud defaults production builds to Terser. Its pinned Vite 5.2.8
    // cannot resolve the optional package reliably under the supported
    // workspace setup, while esbuild is already part of the compiler chain.
    minify: 'esbuild',
  },
  server: {
    host: '127.0.0.1',
    fs: { strict: true },
    cors: { origin: /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/ },
  },
});
