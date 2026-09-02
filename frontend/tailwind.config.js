/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        display: ['"Fraunces"', "Georgia", "serif"],
        sans: ['"Geist"', "Inter", "system-ui", "sans-serif"],
        mono: ['"Geist Mono"', "ui-monospace", "SFMono-Regular", "monospace"],
      },
      colors: {
        // Warm paper + ink, single deep-teal accent (a "deep well" of water/depth).
        paper: {
          DEFAULT: "#f4f1ea",
          deep: "#ece7dc",
        },
        surface: {
          DEFAULT: "#fffdf8",
          sunk: "#f7f3ea",
        },
        ink: {
          DEFAULT: "#20201c",
          soft: "#54514a",
          faint: "#867f72",
        },
        line: {
          DEFAULT: "#e4ded1",
          strong: "#d5cdba",
        },
        accent: {
          DEFAULT: "#0f5a58",
          deep: "#0a423f",
          soft: "#e0ede9",
          ink: "#0c4644",
        },
        // Desaturated, warm-harmonized categorical palette for data viz only.
        data: {
          teal: "#3d8079",
          clay: "#b06a4f",
          gold: "#b08a3e",
          plum: "#7a5a86",
          slate: "#5f7183",
          moss: "#6c8248",
        },
      },
      boxShadow: {
        // Tinted, warm shadows instead of pure black.
        card: "0 1px 2px rgba(40,34,24,0.04), 0 8px 24px -12px rgba(40,34,24,0.14)",
        lift: "0 2px 4px rgba(40,34,24,0.05), 0 18px 40px -16px rgba(40,34,24,0.22)",
        inset: "inset 0 1px 2px rgba(40,34,24,0.06)",
      },
      borderRadius: {
        "4xl": "1.75rem",
      },
      transitionTimingFunction: {
        spring: "cubic-bezier(0.22, 1, 0.36, 1)",
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "pulse-soft": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.5" },
        },
      },
      animation: {
        "fade-up": "fade-up 0.45s cubic-bezier(0.22, 1, 0.36, 1) both",
        "pulse-soft": "pulse-soft 1.4s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
