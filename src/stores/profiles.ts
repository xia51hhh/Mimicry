import { defineStore } from "pinia";
import { ref } from "vue";
import { invoke } from "@tauri-apps/api/core";

export interface BrowserConfig {
  window_width?: number;
  window_height?: number;
  headless?: boolean;
  startup_url?: string;
  geoip?: boolean;
  block_webrtc?: boolean;
  block_webgl?: boolean;
  humanize?: boolean | number;
  block_images?: boolean;
  enable_cache?: boolean;
  disable_coop?: boolean;
  locale?: string;
  fonts?: string[];
  executable_path?: string;
  args?: string[];
  virtual_display?: string;
  addons?: string[];
}

export const DEFAULT_BROWSER_CONFIG: BrowserConfig = {
  geoip: true,
  block_webrtc: true,
  block_webgl: false,
  humanize: true,
  enable_cache: true,
  disable_coop: true,
  block_images: false,
  headless: false,
};

export interface Profile {
  id: string;
  name: string;
  fingerprint: Record<string, unknown>;
  user_data_dir: string;
  proxy?: { server: string; username?: string; password?: string } | null;
  os_target: string;
  browser_config: BrowserConfig;
  created_at: string;
  updated_at: string;
}

export const useProfileStore = defineStore("profiles", () => {
  const profiles = ref<Profile[]>([]);
  const loading = ref(false);
  const selectedId = ref<string | null>(null);

  async function fetchAll() {
    loading.value = true;
    try {
      profiles.value = await invoke<Profile[]>("profile_list");
    } finally {
      loading.value = false;
    }
  }

  async function create(profile: Omit<Profile, "created_at" | "updated_at">) {
    const now = new Date().toISOString();
    const full: Profile = { ...profile, created_at: now, updated_at: now };
    const result = await invoke<Profile>("profile_create", { profile: full });
    profiles.value = [result, ...profiles.value];
    return result;
  }

  async function update(profile: Profile) {
    profile.updated_at = new Date().toISOString();
    const result = await invoke<Profile>("profile_update", { profile });
    profiles.value = profiles.value.map((p) => (p.id === result.id ? result : p));
    return result;
  }

  async function remove(id: string) {
    await invoke("profile_delete", { id });
    profiles.value = profiles.value.filter((p) => p.id !== id);
    if (selectedId.value === id) selectedId.value = null;
  }

  return { profiles, loading, selectedId, fetchAll, create, update, remove };
});
