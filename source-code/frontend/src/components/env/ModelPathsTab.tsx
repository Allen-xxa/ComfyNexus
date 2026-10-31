import { useCallback, useEffect, useState } from 'react'
import { AlertCircle, CheckCircle2, FileCode2, RefreshCw, Save } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'

interface ModelPathsTabProps {
  /** 当前环境的 ComfyUI 根目录，用于定位 extra_model_paths.yaml */
  comfyuiPath: string
}

const EXAMPLE = `# 示例：多个模型库共享同一套目录结构
comfyui:
    base_path: D:/Models
    checkpoints: checkpoints
    loras: loras
    vae: vae

shared:
    base_path: E:/SharedModels
    loras: |
        anime
        realistic
`

/**
 * 模型路径页
 *
 * 直接读写 ComfyUI 根目录下的 extra_model_paths.yaml，不再维护一份与文件脱钩的表单配置。
 * 原表单式配置在保存时会按内存中的配置重写整个文件，用户手写的内容会被覆盖或删除。
 */
export function ModelPathsTab({ comfyuiPath }: ModelPathsTabProps) {
  const [content, setContent] = useState('')
  const [original, setOriginal] = useState('')
  const [filePath, setFilePath] = useState('')
  const [exists, setExists] = useState(false)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [feedback, setFeedback] = useState<{ type: 'ok' | 'err'; text: string } | null>(null)

  const dirty = content !== original

  const load = useCallback(async () => {
    const api = (window as any).pywebview?.api
    if (!comfyuiPath) {
      setFeedback({ type: 'err', text: '尚未配置 ComfyUI 路径，请先在「通用设置」中指定' })
      return
    }
    if (!api?.read_model_paths_yaml) {
      setFeedback({ type: 'err', text: '后端接口不可用，请重启应用' })
      return
    }

    setLoading(true)
    setFeedback(null)
    try {
      const result = await api.read_model_paths_yaml(comfyuiPath)
      if (result?.success) {
        setFilePath(result.path || '')
        setExists(Boolean(result.exists))
        setContent(result.content || '')
        setOriginal(result.content || '')
      } else {
        setFeedback({ type: 'err', text: result?.error_message || '读取失败' })
      }
    } catch (error: any) {
      setFeedback({ type: 'err', text: String(error?.message || error) })
    } finally {
      setLoading(false)
    }
  }, [comfyuiPath])

  useEffect(() => {
    void load()
  }, [load])

  const handleSave = async () => {
    const api = (window as any).pywebview?.api
    if (!api?.write_model_paths_yaml) {
      setFeedback({ type: 'err', text: '后端接口不可用，请重启应用' })
      return
    }

    setSaving(true)
    setFeedback(null)
    try {
      const result = await api.write_model_paths_yaml(comfyuiPath, content)
      if (result?.success) {
        setOriginal(content)
        setExists(true)
        const backup = result.backup_path ? `，原文件已备份为 ${result.backup_path}` : ''
        setFeedback({ type: 'ok', text: `已保存${backup}` })
      } else {
        setFeedback({ type: 'err', text: result?.error_message || '保存失败' })
      }
    } catch (error: any) {
      setFeedback({ type: 'err', text: String(error?.message || error) })
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card className="h-full flex flex-col">
      <CardHeader className="flex flex-row items-center justify-between gap-3 space-y-0">
        <div className="min-w-0">
          <CardTitle className="flex items-center gap-2">
            <FileCode2 className="h-4 w-4" />
            extra_model_paths.yaml
          </CardTitle>
          <p className="mt-1 truncate text-xs text-muted-foreground" title={filePath}>
            {filePath || '等待读取…'}
            {!loading && !exists && filePath ? '（文件不存在，保存后将创建）' : ''}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <Button variant="outline" size="sm" onClick={load} disabled={loading || saving}>
            <RefreshCw className={`mr-1 h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            重新读取
          </Button>
          <Button size="sm" onClick={handleSave} disabled={saving || loading || !dirty}>
            <Save className="mr-1 h-3.5 w-3.5" />
            {saving ? '保存中…' : '保存'}
          </Button>
        </div>
      </CardHeader>

      <CardContent className="flex-1 flex flex-col gap-3 pt-0">
        <div className="rounded-md border border-border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
          此处直接编辑 ComfyUI 的实际配置文件，保存时校验 YAML 语法并自动备份原文件。
          修改后需重启 ComfyUI 生效。
        </div>

        {feedback && (
          <div
            className={`flex items-start gap-2 rounded-md px-3 py-2 text-xs ${
              feedback.type === 'ok'
                ? 'bg-emerald-500/10 text-emerald-600'
                : 'bg-red-500/10 text-red-600'
            }`}
          >
            {feedback.type === 'ok' ? (
              <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            ) : (
              <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            )}
            <span className="break-all">{feedback.text}</span>
          </div>
        )}

        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          spellCheck={false}
          placeholder={EXAMPLE}
          className="min-h-[360px] flex-1 w-full resize-y rounded-md border border-border bg-background px-3 py-2 font-mono text-xs leading-relaxed text-foreground outline-none focus:border-primary"
        />

        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>{dirty ? '有未保存的修改' : '内容与文件一致'}</span>
          <span>{content.split('\n').length} 行</span>
        </div>
      </CardContent>
    </Card>
  )
}
