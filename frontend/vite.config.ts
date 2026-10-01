import { reactRouter } from "@react-router/dev/vite";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";
import tsconfigPaths from "vite-tsconfig-paths";
import path from "path";

export default defineConfig({
  plugins: [tailwindcss(), reactRouter(), tsconfigPaths()],
  resolve: {
    alias: [
      { find: "~", replacement: path.resolve(__dirname, "app") },
      { find: "app", replacement: path.resolve(__dirname, "app") },
    ],
  },
});
