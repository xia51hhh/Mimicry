export interface ThemeColors {
  bg: string
  surface: string
  surfaceHover: string
  surfaceActive: string
  border: string
  borderHover: string
  text: string
  textMuted: string
  textInverse: string
  primary: string
  accent: string
  // Semantic
  success: string
  warning: string
  error: string
  info: string
  // Separators
  separator: string
  separatorLight: string
  // Node header colors
  nodeAction: string
  nodeCondition: string
  nodeLoop: string
  nodeGroup: string
  // Monaco
  monacoTheme: 'vs-dark' | 'vs' | string
}

export interface ThemeDefinition {
  id: string
  name: string
  type: 'dark' | 'light'
  colors: ThemeColors
}

export const themes: ThemeDefinition[] = [
  // ── Dark Themes ──
  {
    id: 'dark-plus',
    name: 'Dark+',
    type: 'dark',
    colors: {
      bg: '#0f0f0f',
      surface: '#1a1a1a',
      surfaceHover: '#252525',
      surfaceActive: '#2d2d2d',
      border: '#2a2a2a',
      borderHover: '#404040',
      text: '#e0e0e0',
      textMuted: '#888888',
      textInverse: '#0f0f0f',
      primary: '#3b82f6',
      accent: '#3b82f6',
      success: '#22c55e',
      warning: '#eab308',
      error: '#ef4444',
      info: '#60a5fa',
      separator: 'rgba(255,255,255,0.06)',
      separatorLight: 'rgba(255,255,255,0.03)',
      nodeAction: '#2563eb',
      nodeCondition: '#d97706',
      nodeLoop: '#9333ea',
      nodeGroup: '#64748b',
      monacoTheme: 'vs-dark',
    },
  },
  {
    id: 'dark',
    name: 'Dark',
    type: 'dark',
    colors: {
      bg: '#24292e',
      surface: '#2f353a',
      surfaceHover: '#383e44',
      surfaceActive: '#42484e',
      border: '#444d56',
      borderHover: '#586069',
      text: '#d1d5da',
      textMuted: '#959da5',
      textInverse: '#24292e',
      primary: '#0078d4',
      accent: '#0078d4',
      success: '#4ec9b0',
      warning: '#dcdcaa',
      error: '#f44747',
      info: '#9cdcfe',
      separator: 'rgba(255,255,255,0.08)',
      separatorLight: 'rgba(255,255,255,0.04)',
      nodeAction: '#2563eb',
      nodeCondition: '#d97706',
      nodeLoop: '#9333ea',
      nodeGroup: '#64748b',
      monacoTheme: 'vs-dark',
    },
  },
  {
    id: 'one-dark',
    name: 'One Dark',
    type: 'dark',
    colors: {
      bg: '#282c34',
      surface: '#21252b',
      surfaceHover: '#2c313a',
      surfaceActive: '#353b45',
      border: '#3e4452',
      borderHover: '#5c6370',
      text: '#abb2bf',
      textMuted: '#5c6370',
      textInverse: '#282c34',
      primary: '#61afef',
      accent: '#61afef',
      success: '#98c379',
      warning: '#e5c07b',
      error: '#e06c75',
      info: '#61afef',
      separator: 'rgba(171,178,191,0.08)',
      separatorLight: 'rgba(171,178,191,0.04)',
      nodeAction: '#61afef',
      nodeCondition: '#e5c07b',
      nodeLoop: '#c678dd',
      nodeGroup: '#5c6370',
      monacoTheme: 'vs-dark',
    },
  },
  {
    id: 'monokai',
    name: 'Monokai',
    type: 'dark',
    colors: {
      bg: '#272822',
      surface: '#2d2e27',
      surfaceHover: '#3e3d32',
      surfaceActive: '#49483e',
      border: '#3e3d32',
      borderHover: '#575650',
      text: '#f8f8f2',
      textMuted: '#90908a',
      textInverse: '#272822',
      primary: '#a6e22e',
      accent: '#a6e22e',
      success: '#a6e22e',
      warning: '#e6db74',
      error: '#f92672',
      info: '#66d9ef',
      separator: 'rgba(255,255,255,0.06)',
      separatorLight: 'rgba(255,255,255,0.03)',
      nodeAction: '#66d9ef',
      nodeCondition: '#e6db74',
      nodeLoop: '#ae81ff',
      nodeGroup: '#75715e',
      monacoTheme: 'vs-dark',
    },
  },
  {
    id: 'solarized-dark',
    name: 'Solarized Dark',
    type: 'dark',
    colors: {
      bg: '#002b36',
      surface: '#073642',
      surfaceHover: '#094753',
      surfaceActive: '#0b5364',
      border: '#094753',
      borderHover: '#2aa198',
      text: '#839496',
      textMuted: '#586e75',
      textInverse: '#002b36',
      primary: '#268bd2',
      accent: '#268bd2',
      success: '#859900',
      warning: '#b58900',
      error: '#dc322f',
      info: '#2aa198',
      separator: 'rgba(131,148,150,0.1)',
      separatorLight: 'rgba(131,148,150,0.05)',
      nodeAction: '#268bd2',
      nodeCondition: '#b58900',
      nodeLoop: '#6c71c4',
      nodeGroup: '#586e75',
      monacoTheme: 'vs-dark',
    },
  },
  // ── Light Themes ──
  {
    id: 'light-plus',
    name: 'Light+',
    type: 'light',
    colors: {
      bg: '#ffffff',
      surface: '#ffffff',
      surfaceHover: '#f5f5f5',
      surfaceActive: '#ebebeb',
      border: '#e0e0e0',
      borderHover: '#c0c0c0',
      text: '#1a1a1a',
      textMuted: '#666666',
      textInverse: '#ffffff',
      primary: '#3b82f6',
      accent: '#3b82f6',
      success: '#22c55e',
      warning: '#eab308',
      error: '#ef4444',
      info: '#60a5fa',
      separator: 'rgba(0,0,0,0.08)',
      separatorLight: 'rgba(0,0,0,0.04)',
      nodeAction: '#2563eb',
      nodeCondition: '#d97706',
      nodeLoop: '#9333ea',
      nodeGroup: '#6b7280',
      monacoTheme: 'vs',
    },
  },
  {
    id: 'light',
    name: 'Light',
    type: 'light',
    colors: {
      bg: '#e8e8e8',
      surface: '#f0f0f0',
      surfaceHover: '#dcdcdc',
      surfaceActive: '#d0d0d0',
      border: '#c4c4c4',
      borderHover: '#a0a0a0',
      text: '#2c2c2c',
      textMuted: '#707070',
      textInverse: '#ffffff',
      primary: '#0078d4',
      accent: '#0078d4',
      success: '#16825d',
      warning: '#bf8803',
      error: '#cd3131',
      info: '#0451a5',
      separator: 'rgba(0,0,0,0.08)',
      separatorLight: 'rgba(0,0,0,0.04)',
      nodeAction: '#0078d4',
      nodeCondition: '#bf8803',
      nodeLoop: '#8b5cf6',
      nodeGroup: '#6b7280',
      monacoTheme: 'vs',
    },
  },
  {
    id: 'github-light',
    name: 'GitHub Light',
    type: 'light',
    colors: {
      bg: '#f6f8fa',
      surface: '#ffffff',
      surfaceHover: '#f3f4f6',
      surfaceActive: '#e5e7eb',
      border: '#d0d7de',
      borderHover: '#afb8c1',
      text: '#1f2328',
      textMuted: '#656d76',
      textInverse: '#ffffff',
      primary: '#0969da',
      accent: '#0969da',
      success: '#1a7f37',
      warning: '#9a6700',
      error: '#cf222e',
      info: '#0969da',
      separator: 'rgba(31,35,40,0.06)',
      separatorLight: 'rgba(31,35,40,0.03)',
      nodeAction: '#0969da',
      nodeCondition: '#9a6700',
      nodeLoop: '#8250df',
      nodeGroup: '#6e7781',
      monacoTheme: 'vs',
    },
  },
  {
    id: 'solarized-light',
    name: 'Solarized Light',
    type: 'light',
    colors: {
      bg: '#fdf6e3',
      surface: '#eee8d5',
      surfaceHover: '#e6dfcb',
      surfaceActive: '#ddd6c1',
      border: '#d3cbb7',
      borderHover: '#b8b0a0',
      text: '#586e75',
      textMuted: '#93a1a1',
      textInverse: '#fdf6e3',
      primary: '#268bd2',
      accent: '#268bd2',
      success: '#859900',
      warning: '#b58900',
      error: '#dc322f',
      info: '#2aa198',
      separator: 'rgba(88,110,117,0.1)',
      separatorLight: 'rgba(88,110,117,0.05)',
      nodeAction: '#268bd2',
      nodeCondition: '#b58900',
      nodeLoop: '#6c71c4',
      nodeGroup: '#93a1a1',
      monacoTheme: 'vs',
    },
  },
]

export function getThemeById(id: string): ThemeDefinition {
  return themes.find((t) => t.id === id) || themes[0]
}

export function applyThemeToDOM(theme: ThemeDefinition, accentColor?: string) {
  const root = document.documentElement
  const c = theme.colors

  root.setAttribute('data-theme', theme.type)
  root.style.setProperty('--color-bg', c.bg)
  root.style.setProperty('--color-surface', c.surface)
  root.style.setProperty('--color-surface-hover', c.surfaceHover)
  root.style.setProperty('--color-surface-active', c.surfaceActive)
  root.style.setProperty('--color-border', c.border)
  root.style.setProperty('--color-border-hover', c.borderHover)
  root.style.setProperty('--color-text', c.text)
  root.style.setProperty('--color-text-muted', c.textMuted)
  root.style.setProperty('--color-text-inverse', c.textInverse)
  root.style.setProperty('--color-primary', accentColor || c.primary)
  root.style.setProperty('--color-accent', accentColor || c.accent)
  root.style.setProperty('--color-success', c.success)
  root.style.setProperty('--color-warning', c.warning)
  root.style.setProperty('--color-error', c.error)
  root.style.setProperty('--color-info', c.info)
  root.style.setProperty('--color-separator', c.separator)
  root.style.setProperty('--color-separator-light', c.separatorLight)
  root.style.setProperty('--color-node-action', c.nodeAction)
  root.style.setProperty('--color-node-condition', c.nodeCondition)
  root.style.setProperty('--color-node-loop', c.nodeLoop)
  root.style.setProperty('--color-node-group', c.nodeGroup)
}
