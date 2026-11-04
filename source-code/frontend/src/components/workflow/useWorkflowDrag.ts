/**
 * 工作流卡片/列表行共用的拖拽逻辑
 *
 * 按住左键移动超过阈值即进入拖拽，实时把鼠标下方的文件夹标为投放目标，
 * 松手交给 DragProvider 执行落库。卡片视图和列表视图都用它，避免两套手感。
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { useDragContext } from './WorkflowDragContext'

const DRAG_THRESHOLD = 5

interface UseWorkflowDragOptions {
  workflowId: string
  selectedWorkflowIds: string[]
  isBatchMode: boolean
  isSelected: boolean
}

export function useWorkflowDrag({
  workflowId,
  selectedWorkflowIds,
  isBatchMode,
  isSelected
}: UseWorkflowDragOptions) {
  const { isDragging: isGlobalDragging, startDrag, updatePosition, endDrag, setDropTargetId } = useDragContext()

  const [isLocalDragging, setIsLocalDragging] = useState(false)
  const mouseDownPosRef = useRef({ x: 0, y: 0 })
  const isDragTriggeredRef = useRef(false)
  const isMouseDownRef = useRef(false)

  useEffect(() => {
    if (isGlobalDragging && isLocalDragging) {
      document.body.style.cursor = 'grabbing'
      document.body.style.userSelect = 'none'
    } else {
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }

    return () => {
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }
  }, [isGlobalDragging, isLocalDragging])

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button !== 0) return
    if ((e.target as HTMLElement).closest('button')) return
    // 批量模式下只有已选中的项能被整组拖走
    if (isBatchMode && !isSelected) return

    e.preventDefault()

    mouseDownPosRef.current = { x: e.clientX, y: e.clientY }
    isDragTriggeredRef.current = false
    isMouseDownRef.current = true

    const handleMouseMove = (moveEvent: MouseEvent) => {
      if (!isMouseDownRef.current) return

      const dx = moveEvent.clientX - mouseDownPosRef.current.x
      const dy = moveEvent.clientY - mouseDownPosRef.current.y
      const distance = Math.sqrt(dx * dx + dy * dy)

      if (distance > DRAG_THRESHOLD && !isDragTriggeredRef.current) {
        isDragTriggeredRef.current = true
        setIsLocalDragging(true)
        startDrag(workflowId, selectedWorkflowIds, moveEvent.clientX, moveEvent.clientY)
      }

      if (isDragTriggeredRef.current) {
        updatePosition(moveEvent.clientX, moveEvent.clientY)

        const target = document.elementFromPoint(moveEvent.clientX, moveEvent.clientY)
        const folderItem = target?.closest('[data-folder-id]')
        if (folderItem) {
          const folderId = folderItem.getAttribute('data-folder-id')
          const isVirtual = folderItem.getAttribute('data-is-virtual') === 'true'

          if (folderId && (!isVirtual || folderId === 'favorites')) {
            setDropTargetId(folderId)
          } else {
            setDropTargetId(null)
          }
        } else {
          setDropTargetId(null)
        }
      }
    }

    const handleMouseUp = () => {
      isMouseDownRef.current = false
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)

      if (isDragTriggeredRef.current) {
        setIsLocalDragging(false)
        endDrag()
      }

      // click 在 mouseup 之后派发，留一拍让按钮的 onClick 能识别"这是一次拖拽收尾"
      setTimeout(() => {
        isDragTriggeredRef.current = false
      }, 0)
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
  }, [workflowId, selectedWorkflowIds, startDrag, updatePosition, endDrag, setDropTargetId, isBatchMode, isSelected])

  return {
    isVisualDragging: isLocalDragging && isGlobalDragging,
    handleMouseDown,
    wasDragTriggered: () => isDragTriggeredRef.current
  }
}
