import { defineStore } from "pinia";
import { ref } from "vue";
import { invoke } from "@tauri-apps/api/core";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";
import { errorMessage } from "../types/ipc";

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

export interface InstallProgress {
  step: "venv" | "pip" | "browser";
  progress: number;
  detail: string;
}

export type SetupPhase =
  | "idle"
  | "checking"
  | "prompt"          // Show install dialog
  | "need_system_pkg" // Need system package (python3-venv)
  | "installing"      // Installing in progress
  | "completed"       // Done
  | "failed";         // Error

export const useBrowserStore = defineStore("browser", () => {
  const connected = ref(false);
  const launching = ref(false);
  const recording = ref(false);
  const recordedNodes = ref<RecordedNode[]>([]);

  // Setup state
  const setupPhase = ref<SetupPhase>("idle");
  const setupError = ref<string | null>(null);
  const installStep = ref<InstallProgress["step"] | null>(null);
  const installProgress = ref(0);
  const installDetail = ref("");
  const systemPkgName = ref("");

  let unlistenProgress: (() => void) | null = null;

  async function startProgressListener() {
    if (unlistenProgress) return;
    unlistenProgress = await listen<InstallProgress>("install-progress", (event) => {
      installStep.value = event.payload.step;
      installProgress.value = event.payload.progress;
      installDetail.value = event.payload.detail;
      if (event.payload.detail === "need_system_pkg") {
        setupPhase.value = "need_system_pkg";
      }
    });
  }

  function stopProgressListener() {
    unlistenProgress?.();
    unlistenProgress = null;
  }

  async function checkEnvironment() {
    setupPhase.value = "checking";
    try {
      const result = await invoke<{
        ready: boolean;
        hasVenv: boolean;
        hasDeps: boolean;
        hasBrowser: boolean;
      }>("check_environment");

      if (result.ready) {
        setupPhase.value = "idle";
        return true;
      }
      setupPhase.value = "prompt";
      return false;
    } catch {
      setupPhase.value = "prompt";
      return false;
    }
  }

  // Camoufox 环境状态
  const camoufoxInstalled = ref(false);
  const camoufoxVersion = ref<string | null>(null);
  const camoufoxChecking = ref(false);
  const camoufoxInstalling = ref(false);

  let recordingUnlisten: UnlistenFn | null = null;

  async function startRecordingPreview() {
    stopRecordingPreview(); // Prevent listener leaks
    recordingUnlisten = await listen<Record<string, unknown>>("sidecar:recording/event", (event) => {
      const node = event.payload as Record<string, unknown>;
      recordedNodes.value = [...recordedNodes.value, {
        type: "action",
        action: (node.type as string) || "click",
        selector: node.selector as string | undefined,
        value: node.value as string | undefined,
        url: node.url as string | undefined,
      }];
    });
  }

  function stopRecordingPreview() {
    if (recordingUnlisten) {
      recordingUnlisten();
      recordingUnlisten = null;
    }
  }

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
      return { success: false, error: errorMessage(e) };
    } finally {
      camoufoxInstalling.value = false;
    }
  }

  async function launch(profileId?: string) {
    if (launching.value) return;

    if (!camoufoxInstalled.value) {
      const check = await checkCamoufox();
      if (!check.installed) {
        return;
      }
    }

    launching.value = true;
    setupError.value = null;
    try {
      await invoke("browser_launch", { profileId: profileId || null });
      connected.value = true;
      setupPhase.value = "idle";
    } catch (e: unknown) {
      const msg = errorMessage(e);
      // Check if environment needs setup
      if (
        msg.includes("ModuleNotFoundError") ||
        msg.includes("No module named") ||
        msg.includes("ImportError") ||
        msg.includes("camoufox") ||
        msg.includes("not found") ||
        msg.includes("No such file") ||
        msg.includes("not installed") ||
        msg.includes("exited unexpectedly") ||
        msg.includes("Failed to start sidecar") ||
        msg.includes("Failed to spawn sidecar")
      ) {
        setupPhase.value = "prompt";
      } else {
        setupError.value = msg;
      }
    } finally {
      launching.value = false;
    }
  }

  async function installBrowser() {
    setupPhase.value = "installing";
    setupError.value = null;
    installStep.value = "venv";
    installProgress.value = 0;

    await startProgressListener();
    try {
      await invoke("browser_install");
      setupPhase.value = "completed";
    } catch (e: unknown) {
      const msg = errorMessage(e);
      if (msg.includes("NEED_SYSTEM_PKG:")) {
        const pkg = msg.split("NEED_SYSTEM_PKG:")[1]?.trim() || "python3-venv";
        systemPkgName.value = pkg;
        setupPhase.value = "need_system_pkg";
      } else {
        setupError.value = msg;
        setupPhase.value = "failed";
      }
    } finally {
      stopProgressListener();
    }
  }

  async function installSystemPkg(pkg: string) {
    setupError.value = null;
    try {
      await invoke("install_system_pkg", { package: pkg });
      // System pkg installed, retry full install
      await installBrowser();
    } catch (e: unknown) {
      setupError.value = errorMessage(e);
      setupPhase.value = "need_system_pkg";
    }
  }

  async function launchAfterSetup() {
    setupPhase.value = "idle";
    await launch();
  }

  function resetSetup() {
    setupPhase.value = "idle";
    setupError.value = null;
    installStep.value = null;
    installProgress.value = 0;
    installDetail.value = "";
    systemPkgName.value = "";
    stopProgressListener();
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
      await startRecordingPreview();
    } catch (e) {
      console.error("Failed to start recording:", e);
    }
  }

  async function stopRecording() {
    stopRecordingPreview();
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
    setupPhase, setupError, installStep, installProgress, installDetail, systemPkgName,
    camoufoxInstalled, camoufoxVersion, camoufoxChecking, camoufoxInstalling,
    launch, close, navigate, fetchStatus,
    startRecording, stopRecording, pollRecording,
    startRecordingPreview, stopRecordingPreview,
    installBrowser, installSystemPkg, launchAfterSetup,
    checkEnvironment, resetSetup,
    checkCamoufox, installCamoufox,
  };
});
