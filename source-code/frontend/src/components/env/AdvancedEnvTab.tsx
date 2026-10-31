/**
 * 高级环境变量选项卡组件
 * 
 * 功能：
 * - 提供终端风格的代码编辑器
 * - 显示配置格式说明和示例
 * - 支持多行环境变量配置
 * - 统一深色终端风格背景
 * 
 * 需求：2.1, 2.2, 5.1, 6.1, 6.2
 */

import { useRef, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Terminal, AlertTriangle, Plus, Info } from 'lucide-react'
import { Textarea } from '@/components/ui'
import type { AdvancedEnvTabProps } from '@/types/environment'

/** 常用环境变量片段，点击后追加到编辑器 */
const SNIPPETS: Array<{ key: string; value: string; desc: string }> = [
  { key: 'PYTHONIOENCODING', value: 'utf-8', desc: '控制台编码，避免中文日志报 UnicodeEncodeError' },
  { key: 'PYTORCH_CUDA_ALLOC_CONF', value: 'expandable_segments:True', desc: '减少显存碎片，大分辨率/长视频更稳' },
  { key: 'CUDA_MODULE_LOADING', value: 'LAZY', desc: '延迟加载 CUDA 模块，启动更快、占用更低' },
  { key: 'HF_HOME', value: 'F:\\ai_cache\\huggingface', desc: 'HuggingFace 缓存目录，避免占满系统盘' },
  { key: 'HF_ENDPOINT', value: 'https://hf-mirror.com', desc: 'HuggingFace 国内镜像' },
]

export function AdvancedEnvTab({
  value,
  onChange
}: AdvancedEnvTabProps) {
  const { t } = useTranslation()
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const lineNumbersRef = useRef<HTMLDivElement>(null)
  const [lineCount, setLineCount] = useState(1)

  useEffect(() => {
    const lines = value.split('\n').length
    setLineCount(Math.max(lines, 16))
  }, [value])

  const handleScroll = () => {
    if (textareaRef.current && lineNumbersRef.current) {
      lineNumbersRef.current.scrollTop = textareaRef.current.scrollTop
    }
  }

  /** 追加一条环境变量；已存在同名键时不再重复添加 */
  const insertSnippet = (key: string, val: string) => {
    const exists = new RegExp(`^\\s*${key}\\s*=`, 'm').test(value)
    if (exists) {
      return
    }
    const line = `${key}=${val}`
    const next = value.trim() ? `${value.replace(/\s*$/, '')}\n${line}` : line
    onChange(next)
    requestAnimationFrame(() => {
      if (textareaRef.current) {
        textareaRef.current.scrollTop = textareaRef.current.scrollHeight
      }
    })
  }

  return (
    <div className="space-y-12">
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-x-12 gap-y-6 items-start">
        <div className="lg:col-span-4 lg:sticky lg:top-36 space-y-6">
          <div>
            <h3 className="text-base font-bold text-foreground flex items-center gap-2">
              <Terminal className="size-4 text-muted-foreground" />
              {t('env.acceleration.advanced.envVarConfig')}
            </h3>
            <p className="text-[13px] text-muted-foreground mt-2.5 leading-relaxed">
              {t('env.acceleration.advanced.configFormatNote')}
            </p>
          </div>

          <div className="bg-primary/5 border-l-4 border-l-primary/60 p-5 rounded-r-lg">
            <h4 className="text-[13px] font-semibold text-primary mb-2">
              {t('env.acceleration.advanced.example')}
            </h4>
            <ul className="list-disc list-inside space-y-1.5 text-[13px] text-primary/80">
              <li>{t('env.acceleration.advanced.oneVarPerLine')}</li>
              <li>{t('env.acceleration.advanced.supportComment')}</li>
              <li>{t('env.acceleration.advanced.spaceInValue')}</li>
            </ul>
            <div className="mt-4 bg-background/60 p-3 rounded-lg border border-primary/20 font-mono text-[12px] text-foreground">
              # {t('env.acceleration.advanced.tip1')}<br />
              {t('env.cudaVisibleDevicesExample')}
            </div>
          </div>

          <div className="text-[12px] text-muted-foreground bg-surface p-4 rounded-xl border border-border-subtle">
            <p className="font-bold text-foreground mb-1 flex items-center gap-1.5">
              <AlertTriangle className="size-3.5 text-warning" />
              {t('env.acceleration.advanced.tip')}
            </p>
            {t('env.acceleration.advanced.tip4')}
          </div>

          <div className="rounded-xl border border-border-subtle bg-surface p-4 space-y-3">
            <p className="text-[13px] font-bold text-foreground flex items-center gap-1.5">
              <Info className="size-3.5 text-primary" />
              这一页管什么
            </p>
            <p className="text-[12px] leading-relaxed text-muted-foreground">
              这里写的是<strong className="text-foreground">操作系统环境变量</strong>，启动 ComfyUI 时注入到它的子进程。
              命令行参数（如 <code className="font-mono">--lowvram</code>）请到「加速与架构」页设置，两者互不影响。
            </p>
            <p className="text-[12px] leading-relaxed text-muted-foreground">
              显卡选择相关的 <code className="font-mono">CUDA_VISIBLE_DEVICES</code> 会被应用的设备选择覆盖，
              选卡请用「加速与架构」。
            </p>

            <div className="pt-1">
              <p className="mb-2 text-[12px] font-semibold text-foreground">常用变量（点击追加）</p>
              <div className="flex flex-col gap-1.5">
                {SNIPPETS.map((snippet) => (
                  <button
                    key={snippet.key}
                    type="button"
                    onClick={() => insertSnippet(snippet.key, snippet.value)}
                    className="group flex items-start gap-2 rounded-lg border border-border-subtle px-2.5 py-2 text-left transition-colors hover:border-primary/50 hover:bg-primary/5"
                  >
                    <Plus className="mt-0.5 size-3.5 shrink-0 text-muted-foreground group-hover:text-primary" />
                    <span className="min-w-0">
                      <span className="block truncate font-mono text-[11px] text-foreground">
                        {snippet.key}={snippet.value}
                      </span>
                      <span className="block text-[11px] text-muted-foreground">{snippet.desc}</span>
                    </span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="lg:col-span-8">
          {/* eslint-disable-next-line no-restricted-syntax */}
          <div className="bg-[hsl(var(--bg-base))] rounded-xl overflow-hidden border border-border-subtle shadow-soft-lg min-h-[500px] flex flex-col">
            <div className="bg-surface-active border-b border-border-subtle px-4 py-3 flex items-center">
              <div className="flex gap-2">
                {/* eslint-disable-next-line no-restricted-syntax */}
                <div className="w-3 h-3 rounded-full bg-[#ff5f56]" />
                {/* eslint-disable-next-line no-restricted-syntax */}
                <div className="w-3 h-3 rounded-full bg-[#ffbd2e]" />
                {/* eslint-disable-next-line no-restricted-syntax */}
                <div className="w-3 h-3 rounded-full bg-[#27c93f]" />
              </div>
              <div className="flex-1 text-center">
                <span className="text-xs font-mono text-content-muted">
                  {t('env.terminalTitle')}
                </span>
              </div>
            </div>

            <div className="flex flex-1 font-mono text-[13px] leading-relaxed">
              <div
                ref={lineNumbersRef}
                className="py-4 pl-4 pr-3 text-right select-none border-r border-border-subtle bg-surface-active/50 overflow-hidden"
                style={{ minWidth: '3rem' }}
              >
                {Array.from({ length: lineCount }, (_, i) => i + 1).map(lineNum => (
                  <div
                    key={lineNum}
                    className="text-content-muted"
                    style={{ minHeight: '1.5rem', lineHeight: '1.5rem' }}
                  >
                    {lineNum}
                  </div>
                ))}
              </div>

              <Textarea
                ref={textareaRef}
                value={value}
                onChange={(e) => onChange(e.target.value)}
                onScroll={handleScroll}
                placeholder={t('common.placeholder.envVarsExample')}
                className="flex-1 p-4 bg-transparent text-content-primary resize-none focus:outline-none placeholder:text-content-muted"
                style={{
                  fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                  lineHeight: '1.5rem'
                }}
                spellCheck={false}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
