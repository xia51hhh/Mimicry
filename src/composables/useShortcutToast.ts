import { ref, readonly } from 'vue'

const toastMessage = ref('')
const toastShortcut = ref('')
const toastVisible = ref(false)

let hideTimer: ReturnType<typeof setTimeout> | null = null

export function useShortcutToast() {
  function showToast(message: string, shortcut: string) {
    if (hideTimer) clearTimeout(hideTimer)
    toastMessage.value = message
    toastShortcut.value = shortcut
    toastVisible.value = true
    hideTimer = setTimeout(() => {
      toastVisible.value = false
    }, 1500)
  }

  function hideToast() {
    toastVisible.value = false
  }

  return {
    message: readonly(toastMessage),
    shortcut: readonly(toastShortcut),
    visible: readonly(toastVisible),
    showToast,
    hideToast,
  }
}
