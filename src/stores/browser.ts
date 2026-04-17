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

  async function launch() {
    if (launching.value) return;
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

  return {
    connected, launching, recording, recordedNodes,
    launch, close, startRecording, stopRecording, pollRecording,
  };
});
