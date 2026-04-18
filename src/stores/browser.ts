import { defineStore } from "pinia";
import { ref } from "vue";
import { invoke } from "@tauri-apps/api/core";

export interface RecordedNode {
  type: string;
  action: string;
  selector?: string;
  value?: string;
  url?: string;
  position?: { x: number; y: number };
}

interface RecordingResult {
  nodes: RecordedNode[];
}

export const useBrowserStore = defineStore("browser", () => {
  const connected = ref(false);
  const launching = ref(false);
  const recording = ref(false);
  const recordedNodes = ref<RecordedNode[]>([]);

  // Camoufox 环境状态
  const camoufoxInstalled = ref(false);
  const camoufoxVersion = ref<string | null>(null);
  const camoufoxChecking = ref(false);
  const camoufoxInstalling = ref(false);

  async function checkCamoufox() {
    camoufoxChecking.value = true;
    try {
      const result = await invoke<{ installed: boolean; version: string | null }>("camoufox_check");
      camoufoxInstalled.value = result.installed;
      camoufoxVersion.value = result.version;
      return result;
    } catch (e) {
      console.error("Failed to check camoufox:", e);
      return { installed: false, version: null };
    } finally {
      camoufoxChecking.value = false;
    }
  }

  async function installCamoufox() {
    if (camoufoxInstalling.value) return { success: false, error: "Already installing" };
    camoufoxInstalling.value = true;
    try {
      const result = await invoke<{ success: boolean; version?: string; error?: string }>("camoufox_install");
      if (result.success) {
        camoufoxInstalled.value = true;
        camoufoxVersion.value = result.version ?? null;
      }
      return result;
    } catch (e) {
      console.error("Failed to install camoufox:", e);
      return { success: false, error: String(e) };
    } finally {
      camoufoxInstalling.value = false;
    }
  }

  async function launch() {
    if (launching.value) return;

    if (!camoufoxInstalled.value) {
      const check = await checkCamoufox();
      if (!check.installed) {
        return;
      }
    }

    launching.value = true;
    try {
      await invoke("browser_launch");
      connected.value = true;
    } catch (e) {
      console.error("Failed to launch browser:", e);
    } finally {
      launching.value = false;
    }
  }

  async function close() {
    try {
      await invoke("browser_close");
      connected.value = false;
      recording.value = false;
    } catch (e) {
      console.error("Failed to close browser:", e);
    }
  }

  async function startRecording() {
    try {
      await invoke("recording_start");
      recording.value = true;
      recordedNodes.value = [];
    } catch (e) {
      console.error("Failed to start recording:", e);
    }
  }

  async function stopRecording() {
    try {
      const result = await invoke<RecordingResult>("recording_stop");
      recording.value = false;
      recordedNodes.value = result.nodes || [];
      return recordedNodes.value;
    } catch (e) {
      console.error("Failed to stop recording:", e);
      recording.value = false;
      return [];
    }
  }

  async function pollRecording() {
    if (!recording.value) return [];
    try {
      const result = await invoke<RecordingResult>("recording_poll");
      return result.nodes || [];
    } catch (e) {
      console.error("Failed to poll recording:", e);
      return [];
    }
  }

  async function navigate(url: string) {
    try {
      await invoke("browser_navigate", { url });
    } catch (e) {
      console.error("Failed to navigate:", e);
    }
  }

  async function fetchStatus() {
    try {
      const result = await invoke<{ connected: boolean; url: string | null; pages: number }>("browser_status");
      connected.value = result.connected;
      return result;
    } catch (e) {
      console.error("Failed to get browser status:", e);
    }
  }

  return {
    connected, launching, recording, recordedNodes,
    camoufoxInstalled, camoufoxVersion, camoufoxChecking, camoufoxInstalling,
    launch, close, navigate, fetchStatus,
    startRecording, stopRecording, pollRecording,
    checkCamoufox, installCamoufox,
  };
});
