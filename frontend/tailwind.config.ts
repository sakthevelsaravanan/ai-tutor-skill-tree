import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#090d16",
        surface: "#111827",
        surfaceLight: "#1f2937",
        border: "#283445",
        accent: "#38bdf8",
        accentHover: "#0284c7",
      },
    },
  },
  plugins: [],
};

export default config;
