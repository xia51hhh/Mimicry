import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { i18n } from '../i18n';
import { themes, getThemeById, applyThemeToDOM } from '../themes';
import type { ThemeDefinition } from '../themes';

const ACCENT_COLORS = [
  '#0078d4', // blue (VS Code)
  '#3b82f6', // blue bright
  '#22c55e', // green
  '#eab308', // yellow
  '#ef4444', // red
  '#a855f7', // purple
  '#f97316', // orange
  '#06b6d4', // cyan
  '#ec4899', // pink
] as const;

export { ACCENT_COLORS };

export const useSettingsStore = defineStore('settings', () => {
  const themeId = ref(localStorage.getItem('mimicry-theme') || 'dark-plus');
  const locale = ref(localStorage.getItem('mimicry-locale') || 'zh-CN');
  const accentColor = ref(localStorage.getItem('mimicry-accent') || '');

  const currentTheme = computed<ThemeDefinition>(() => getThemeById(themeId.value));
  const monacoTheme = computed(() => currentTheme.value.colors.monacoTheme);
  const allThemes = themes;

  function setTheme(id: string) {
    themeId.value = id;
    localStorage.setItem('mimicry-theme', id);
    applyTheme();
  }

  function setLocale(l: string) {
    locale.value = l;
    localStorage.setItem('mimicry-locale', l);
    (i18n.global.locale as unknown as { value: string }).value = l;
  }

  function setAccentColor(color: string) {
    accentColor.value = color;
    localStorage.setItem('mimicry-accent', color);
    applyTheme();
  }

  function applyTheme() {
    const theme = getThemeById(themeId.value);
    applyThemeToDOM(theme, accentColor.value || undefined);
  }

  // Apply on init
  applyTheme();

  // Execution defaults
  const humanize = ref(localStorage.getItem('mimicry-humanize') !== 'false');
  const delayMultiplier = ref(parseFloat(localStorage.getItem('mimicry-delay-multiplier') || '1.0'));
  const defaultTimeout = ref(parseInt(localStorage.getItem('mimicry-default-timeout') || '30000'));

  function setHumanize(v: boolean) {
    humanize.value = v;
    localStorage.setItem('mimicry-humanize', String(v));
  }

  function setDelayMultiplier(v: number) {
    delayMultiplier.value = Math.max(0, v);
    localStorage.setItem('mimicry-delay-multiplier', String(delayMultiplier.value));
  }

  function setDefaultTimeout(v: number) {
    defaultTimeout.value = Math.max(0, v);
    localStorage.setItem('mimicry-default-timeout', String(defaultTimeout.value));
  }

  // Proxy settings
  const proxyEnabled = ref(localStorage.getItem('mimicry-proxy-enabled') === 'true');
  const proxyServer = ref(localStorage.getItem('mimicry-proxy-server') || '');
  const proxyBypass = ref(localStorage.getItem('mimicry-proxy-bypass') || '');

  function setProxyEnabled(v: boolean) {
    proxyEnabled.value = v;
    localStorage.setItem('mimicry-proxy-enabled', String(v));
  }

  function setProxyServer(v: string) {
    proxyServer.value = v;
    localStorage.setItem('mimicry-proxy-server', v);
  }

  function setProxyBypass(v: string) {
    proxyBypass.value = v;
    localStorage.setItem('mimicry-proxy-bypass', v);
  }

  return {
    themeId,
    locale,
    accentColor,
    currentTheme,
    monacoTheme,
    allThemes,
    setTheme,
    setLocale,
    setAccentColor,
    applyTheme,
    // Execution
    humanize,
    delayMultiplier,
    defaultTimeout,
    setHumanize,
    setDelayMultiplier,
    setDefaultTimeout,
    // Proxy
    proxyEnabled,
    proxyServer,
    proxyBypass,
    setProxyEnabled,
    setProxyServer,
    setProxyBypass,
  };
});
