/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // 与设计稿一致的主色（按钮、高亮、图标）
        primary: {
          DEFAULT: "#0066FF",
          hover: "#0052CC",
          soft: "#E8F1FF",
        },
      },
      boxShadow: {
        card: "0 1px 3px rgba(15, 23, 42, 0.08)",
      },
    },
  },
  plugins: [],
};
