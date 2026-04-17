import { ref } from 'vue'

export type PanelDirection = 'horizontal' | 'vertical'

interface UsePanelOptions {
  direction: PanelDirection
  defaultSize: number
  minSize: number
  maxSize: number
  storageKey?: string
  /** If true, dragging in the positive direction increases size (e.g. sidebar on left) */
  invertDelta?: boolean
}

export function usePanel(options: UsePanelOptions) {
  const { direction, defaultSize, minSize, maxSize, storageKey, invertDelta } = options

  const savedSize = storageKey ? Number(localStorage.getItem(storageKey)) || defaultSize : defaultSize
  const size = ref(savedSize)
  const collapsed = ref(false)

  let resizing = false
  let startPos = 0
  let startSize = 0

  function onResizeStart(e: MouseEvent) {
    resizing = true
    startPos = direction === 'horizontal' ? e.clientX : e.clientY
    startSize = size.value
    document.addEventListener('mousemove', onResizeMove)
    document.addEventListener('mouseup', onResizeEnd)
    document.body.style.cursor = direction === 'horizontal' ? 'col-resize' : 'row-resize'
    document.body.style.userSelect = 'none'
  }

  function onResizeMove(e: MouseEvent) {
    if (!resizing) return
    const currentPos = direction === 'horizontal' ? e.clientX : e.clientY
    const delta = invertDelta ? (currentPos - startPos) : (startPos - currentPos)
    size.value = Math.max(minSize, Math.min(maxSize, startSize + delta))
  }

  function onResizeEnd() {
    resizing = false
    document.removeEventListener('mousemove', onResizeMove)
    document.removeEventListener('mouseup', onResizeEnd)
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
    if (storageKey) localStorage.setItem(storageKey, String(size.value))
  }

  function toggle() {
    collapsed.value = !collapsed.value
  }

  function show() {
    collapsed.value = false
  }

  function hide() {
    collapsed.value = true
  }

  return { size, collapsed, onResizeStart, toggle, show, hide }
}

// Shared panel state for cross-component toggle buttons
const sidebarCollapsed = ref(false)
const bottomCollapsed = ref(false)
const rightPanelCollapsed = ref(false)
const bottomPanelHeight = ref(200)

export function usePanelLayout() {
  return {
    sidebarCollapsed,
    bottomCollapsed,
    rightPanelCollapsed,
    bottomPanelHeight,
    toggleSidebar: () => { sidebarCollapsed.value = !sidebarCollapsed.value },
    toggleBottom: () => { bottomCollapsed.value = !bottomCollapsed.value },
    toggleRightPanel: () => { rightPanelCollapsed.value = !rightPanelCollapsed.value },
  }
}
