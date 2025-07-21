// frontend/postcss.config.mjs

export default {
  plugins: {
    '@tailwindcss/postcss': {}, // ИСПРАВЛЕНИЕ: Используем новый плагин-посредник
    autoprefixer: {},
  },
};