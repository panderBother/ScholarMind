/** @type {import('tailwindcss').Config} */
export default {
  // Streamdown / @streamdown 在 node_modules 内拼接 Tailwind 类名，必须纳入扫描，否则 Shiki 高亮与代码块样式不会出现在最终 CSS 中
  content: [
    "./index.html",
    "./src/**/*.{ts,tsx}",
    "./node_modules/streamdown/dist/**/*.{js,mjs}",
    "./node_modules/@streamdown/code/dist/**/*.{js,mjs}",
    "./node_modules/@streamdown/cjk/dist/**/*.{js,mjs}",
  ],
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
