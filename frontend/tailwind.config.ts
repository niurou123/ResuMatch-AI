import type { Config } from 'tailwindcss'

/**
 * 设计令牌：白底黑字 · 单色极简
 *
 * - 页面与卡片统一纯白，靠 1px 细边框划分层级，不用阴影堆叠
 * - 文字用近黑墨色 #1f2329，弱化为 #4e5969 / #86909c
 * - 主色即墨色（按钮黑底白字），蓝色只保留给必要的交互强调
 * - 语义色（成功/警告/危险）保留但降低饱和，避免抢视觉
 */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#ffffff',
        surface: {
          DEFAULT: '#ffffff',
          '2': '#fafafa',
          '3': '#f5f6f7',
        },
        border: {
          DEFAULT: '#e5e6eb',
          strong: '#d0d3d9',
          lighter: '#f0f1f2',
        },
        text: {
          DEFAULT: '#1f2329',
          '2': '#4e5969',
          '3': '#86909c',
          '4': '#a9aeb8',
        },
        // 墨色：文字与次级按钮（保持黑白主体）
        ink: {
          DEFAULT: '#1f2329',
          soft: '#3a4048',
          strong: '#000000',
        },
        // 主色蓝：只用于主按钮、当前菜单项、链接与选中态
        primary: {
          DEFAULT: '#0b6bcb',
          '2': '#3f8fdb',
          light: '#e8f1fb',
          dark: '#084c8f',
        },
        accent: {
          DEFAULT: '#0b6bcb',
          light: '#e8f1fb',
        },
        success: '#2ea121',
        warn: '#d97706',
        danger: '#d93026',
        nav: {
          bg: '#ffffff',
          hover: '#f5f6f7',
          text: '#4e5969',
        },
      },
      borderRadius: {
        card: '4px',
        btn: '4px',
        chip: '2px',
      },
      boxShadow: {
        card: 'none',
        pop: '0 2px 8px rgba(0, 0, 0, 0.06)',
      },
      fontFamily: {
        sans: [
          '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto',
          'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Helvetica Neue',
          'Arial', 'sans-serif',
        ],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Consolas', 'monospace'],
      },
      fontSize: {
        '2xs': ['11px', '16px'],
      },
    },
  },
  plugins: [],
} satisfies Config
