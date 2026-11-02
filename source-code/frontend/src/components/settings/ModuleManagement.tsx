/**
 * 模块管理组件
 */

import { useTranslation } from 'react-i18next'
import { useState } from 'react'
import { Card, CardHeader, CardTitle, CardContent, Button } from '@/components/ui'
import { Switch } from '@/components/ui/Switch'
import { MODULE_REGISTRY } from '@/types/module'
import { useModuleConfigStore } from '@/stores/useModuleConfigStore'
import * as Icons from 'lucide-react'
import { cn } from '@/lib/utils'

export function ModuleManagement() {
  const { t } = useTranslation()
  const { modules, toggleModule, saveConfig, resetConfig } = useModuleConfigStore()
  const [showResetConfirm, setShowResetConfirm] = useState(false)
  const [notification, setNotification] = useState<{ message: string; type: 'success' | 'error' } | null>(null)

  const handleToggleModule = async (moduleId: string) => {
    toggleModule(moduleId)
    const success = await saveConfig()
    if (success) {
      setNotification({ message: t('module.configUpdated'), type: 'success' })
      setTimeout(() => setNotification(null), 2000)
    }
  }

  const handleReset = () => {
    setShowResetConfirm(true)
  }

  const confirmReset = async () => {
    await resetConfig()
    setShowResetConfirm(false)
    setNotification({ message: t('module.configReset'), type: 'success' })
    setTimeout(() => setNotification(null), 2000)
  }

  const coreModules = Object.values(MODULE_REGISTRY).filter(m => m.category === 'core')
  const managementModules = Object.values(MODULE_REGISTRY).filter(m => m.category === 'management')
  const toolModules = Object.values(MODULE_REGISTRY).filter(m => m.category === 'tool')
  const assetModules = Object.values(MODULE_REGISTRY).filter(m => m.category === 'asset')

  const ModuleItem = ({ moduleId }: { moduleId: string }) => {
    const module = MODULE_REGISTRY[moduleId]
    if (!module) return null

    const Icon = (Icons as any)[module.icon] || Icons.Circle
    const isEnabled = modules[moduleId]?.enabled ?? false

    return (
      <div className="flex items-center justify-between rounded-lg border border-border p-3 transition-colors hover:bg-accent">
        <div className="flex flex-1 items-center gap-3">
          <Icon className="size-5 text-muted-foreground" />
          <div className="flex-1">
            <div className="text-sm font-medium">{module.name}</div>
            <div className="text-xs text-muted-foreground">{module.description}</div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {['home', 'system-settings', 'about'].includes(module.id) && (
            <span className="bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-200 rounded px-2 py-1 text-xs">
              {t('dependency.core')}
            </span>
          )}
          <Switch
            checked={isEnabled}
            onCheckedChange={() => handleToggleModule(moduleId)}
            disabled={['home', 'system-settings', 'about'].includes(moduleId)}
          />
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {notification && (
        <div className="animate-in fade-in slide-in-from-top-2 fixed left-1/2 top-20 z-50 -translate-x-1/2 duration-300">
          <div className={cn(
            "px-6 py-3 rounded-lg border backdrop-blur-md shadow-lg transition-all",
            notification.type === 'success'
              ? "bg-green-50/80 border-green-200 text-green-800 dark:bg-green-900/60 dark:border-green-700 dark:text-green-200"
              : "bg-red-50/80 border-red-200 text-red-800 dark:bg-red-900/60 dark:border-red-700 dark:text-red-200"
          )}>
            <p className="whitespace-nowrap text-sm font-medium">{notification.message}</p>
          </div>
        </div>
      )}

      {/* 两列布局 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* 左列：核心模块 + 工具模块 */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">{t("module.coreModules")}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {coreModules.map((module) => (
                <ModuleItem key={module.id} moduleId={module.id} />
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">{t("module.toolModules")}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {toolModules.map((module) => (
                <ModuleItem key={module.id} moduleId={module.id} />
              ))}
            </CardContent>
          </Card>
        </div>

        {/* 右列：管理模块 + 资产模块 */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">{t("module.managementModules")}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {managementModules.map((module) => (
                <ModuleItem key={module.id} moduleId={module.id} />
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">{t("module.assetModules")}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {assetModules.map((module) => (
                <ModuleItem key={module.id} moduleId={module.id} />
              ))}
            </CardContent>
          </Card>
        </div>
      </div>

      <div className="flex gap-3">
        <Button
          onClick={handleReset}
          variant="outline"
          className="flex-1"
        >
          {t('module.resetToDefault')}
        </Button>
      </div>

      <div className="border-blue-200 bg-blue-50 dark:border-blue-800 dark:bg-blue-900/20 rounded-lg border p-3">
        <p className="text-blue-900 dark:text-blue-200 text-sm">
          {t('module.configNote')}
        </p>
      </div>

      {showResetConfirm && (
        <div className="bg-black/50 fixed inset-0 z-50 flex items-center justify-center">
          <Card className="w-96">
            <CardHeader>
              <CardTitle>{t("module.confirmReset")}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground">
                {t('module.confirmResetMessage')}
              </p>
              <div className="flex gap-3">
                <Button
                  onClick={() => setShowResetConfirm(false)}
                  variant="outline"
                  className="flex-1"
                >
                  {t('common.cancel')}
                </Button>
                <Button
                  onClick={confirmReset}
                  className="flex-1"
                >
                  {t('common.confirm')}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}
