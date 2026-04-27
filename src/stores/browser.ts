import { defineStore } from "pinia";
import { ref, computed } from "vue";
import { invoke } from "@tauri-apps/api/core";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";
import { errorMessage, SidecarEvent } from "../types/ipc";

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

export interface BrowserSession {
  sessionId: string;
  profileId?: string;
  connected: boolean;
  recording: boolean;
  url: string | null;
  pages: number;
}

export const useBrowserStore = defineStore("browser", () => {
  // Multi-session state
  const sessions = ref<Map<string, BrowserSession>>(new Map());
  const activeSessionId = ref<string | null>(null);

  // Backward-compatible computed
  const connected = computed(() => {
    if (!activeSessionId.value) return false;
    return sessions.value.get(activeSessionId.value)?.connected ?? false;
  });
  const launching = ref(false);
  const recording = computed(() => {
    if (!activeSessionId.value) return false;
    return sessions.value.get(activeSessionId.value)?.recording ?? false;
  });
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
    recordingUnlisten = await listen<Record<string, unknown>>(SidecarEvent.RecordingEvent, (event) => {
      const node = event.payload as Record<string, unknown>;
      // Filter events by active session
      if (node.session_id && node.session_id !== activeSessionId.value) return;
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

  async function launch(profileId?: string, sessionId?: string) {
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
      const result = await invoke<{ session_id: string; warnings?: string[] }>("browser_launch", {
        profileId: profileId || null,
        sessionId: sessionId || null,
      });
      const sid = result.session_id ?? sessionId ?? profileId ?? "default";
      const session: BrowserSession = {
        sessionId: sid,
        profileId: profileId ?? undefined,
        connected: true,
        recording: false,
        url: null,
        pages: 0,
      };
      sessions.value = new Map(sessions.value).set(sid, session);
      if (!activeSessionId.value) activeSessionId.value = sid;
      // Show warnings as non-blocking error (auto-dismissed by next launch)
      if (result.warnings?.length) {
        setupError.value = result.warnings.join("\n");
      }
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

  async function close(sessionId?: string) {
    const sid = sessionId ?? activeSessionId.value;
    try {
      await invoke("browser_close", { sessionId: sid });
      if (sid) {
        const next = new Map(sessions.value);
        next.delete(sid);
        sessions.value = next;
        if (activeSessionId.value === sid) {
          activeSessionId.value = next.size > 0 ? next.keys().next().value ?? null : null;
        }
      }
    } catch (e) {
      console.error("Failed to close browser:", e);
    }
  }

  async function startRecording(sessionId?: string) {
    const sid = sessionId ?? activeSessionId.value;
    try {
      await invoke("recording_start", { sessionId: sid });
      if (sid) {
        const s = sessions.value.get(sid);
        if (s) {
          const next = new Map(sessions.value);
          next.set(sid, { ...s, recording: true });
          sessions.value = next;
        }
      }
      recordedNodes.value = [];
      await startRecordingPreview();
    } catch (e) {
      console.error("Failed to start recording:", e);
    }
  }

  async function stopRecording(sessionId?: string) {
    stopRecordingPreview();
    const sid = sessionId ?? activeSessionId.value;
    try {
      const result = await invoke<RecordingResult>("recording_stop", { sessionId: sid });
      if (sid) {
        const s = sessions.value.get(sid);
        if (s) {
          const next = new Map(sessions.value);
          next.set(sid, { ...s, recording: false });
          sessions.value = next;
        }
      }
      recordedNodes.value = result.nodes || [];
      return recordedNodes.value;
    } catch (e) {
      console.error("Failed to stop recording:", e);
      return [];
    }
  }

  async function pollRecording(sessionId?: string) {
    if (!recording.value) return [];
    const sid = sessionId ?? activeSessionId.value;
    try {
      const result = await invoke<RecordingResult>("recording_poll", { sessionId: sid });
      return result.nodes || [];
    } catch (e) {
      console.error("Failed to poll recording:", e);
      return [];
    }
  }

  async function navigate(url: string, sessionId?: string) {
    const sid = sessionId ?? activeSessionId.value;
    try {
      await invoke("browser_navigate", { url, sessionId: sid });
    } catch (e) {
      console.error("Failed to navigate:", e);
    }
  }

  async function fetchStatus(sessionId?: string) {
    const sid = sessionId ?? activeSessionId.value;
    try {
      const result = await invoke<{ connected: boolean; url: string | null; pages: number }>("browser_status", { sessionId: sid });
      if (sid) {
        const s = sessions.value.get(sid);
        if (s) {
          const next = new Map(sessions.value);
          next.set(sid, { ...s, connected: result.connected, url: result.url, pages: result.pages });
          sessions.value = next;
        }
      }
      return result;
    } catch (e) {
      console.error("Failed to get browser status:", e);
    }
  }

  async function listSessions() {
    try {
      return await invoke<{ sessions: Array<{ session_id: string; connected: boolean; url: string | null; pages: number }> }>("browser_list_sessions");
    } catch (e) {
      console.error("Failed to list sessions:", e);
      return { sessions: [] };
    }
  }

  function setActiveSession(sessionId: string) {
    if (sessions.value.has(sessionId)) {
      activeSessionId.value = sessionId;
    }
  }

  return {
    sessions, activeSessionId,
    connected, launching, recording, recordedNodes,
    setupPhase, setupError, installStep, installProgress, installDetail, systemPkgName,
    camoufoxInstalled, camoufoxVersion, camoufoxChecking, camoufoxInstalling,
    launch, close, navigate, fetchStatus, listSessions, setActiveSession,
    startRecording, stopRecording, pollRecording,
    startRecordingPreview, stopRecordingPreview,
    installBrowser, installSystemPkg, launchAfterSetup,
    checkEnvironment, resetSetup,
    checkCamoufox, installCamoufox,
  };
});
