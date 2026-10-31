import { forwardRef, useRef, useImperativeHandle } from 'react'
import { GeneralTab } from './GeneralTab'
import { AccelerationTab, AccelerationTabRef } from './AccelerationTab'
import { ModelPathsTab } from './ModelPathsTab'
import { AdvancedEnvTab } from './AdvancedEnvTab'
import type { TabContainerProps, AccelerationTabProps } from '@/types/environment'

export const TabContainer = forwardRef<AccelerationTabRef, TabContainerProps & {
  onPresetSelect?: (presetId: string, presetConfig: Record<string, any>, presetName?: string) => void
  onShowToast?: (message: string, variant: 'success' | 'error') => void
  onCreatePreset?: (name: string, description: string, vramRequirement: string) => void
  onEditPreset?: (presetId: string, name: string, description: string, vramRequirement: string) => void
  onDeletePreset?: (presetId: string) => void
  onSaveAsPreset?: () => void
  onManagePresets?: () => void
}>(
  function TabContainer({
    activeTab,
    config,
    currentEnvId,
    onConfigChange,
    onRefreshDependencies,
    onPresetSelect,
    onShowToast,
    onCreatePreset,
    onEditPreset,
    onDeletePreset,
    onSaveAsPreset,
    onManagePresets
  }, ref) {
    const accelerationTabRef = useRef<AccelerationTabRef>(null)
    
    useImperativeHandle(ref, () => {
      return {
        openImportDialog: () => {
          if (accelerationTabRef.current) {
            accelerationTabRef.current.openImportDialog();
          }
        },
        openExportDialog: () => {
          if (accelerationTabRef.current) {
            accelerationTabRef.current.openExportDialog();
          }
        },
        openCreatePresetDialog: () => {
          if (accelerationTabRef.current) {
            accelerationTabRef.current.openCreatePresetDialog();
          }
        },
        reloadPresets: () => {
          if (accelerationTabRef.current) {
            accelerationTabRef.current.reloadPresets?.();
          }
        },
        getGeekModeState: () => {
          if (accelerationTabRef.current) {
            return accelerationTabRef.current.getGeekModeState();
          }
          return { enabled: false, hasUnsavedChanges: false };
        },
        toggleGeekMode: (enabled: boolean) => {
          if (accelerationTabRef.current) {
            accelerationTabRef.current.toggleGeekMode(enabled);
          }
        }
      };
    }, []);

    const handleGeneralChange = (changes: Partial<typeof config.general & typeof config.acceleration & { alias?: string }>) => {
      console.log('[TabContainer] handleGeneralChange 接收到变更:', changes)
      console.log('[TabContainer] 当前 config.general:', config.general)
      console.log('[TabContainer] 当前 config.acceleration:', config.acceleration)
      
      const generalChanges: any = {}
      const accelerationChanges: any = {}
      let aliasChange: { alias?: string } = {}

      const generalKeys = new Set(Object.keys(config.general))
      const accelerationKeys = new Set(Object.keys(config.acceleration))
      
      const knownAccelerationFields = new Set([
        'computeDevice', 'vramStrategy', 'cpuOnly', 'gpuOnly', 'reserveVram',
        'unetPrecision', 'vaePrecision', 'textEncPrecision', 'attentionMode', 'disableXformers',
        'disableSmartMemory', 'forceChannelsLast', 'cacheLru', 'deterministic', 'fastMode',
        'listenNetwork', 'listenAddress', 'port', 'enableCors', 'tlsKeyfile', 'tlsCertfile',
        'baseDirectory', 'inputDirectory', 'outputDirectory', 'tempDirectory', 'userDirectory', 'extraModelPathsConfig',
        'previewMethod', 'previewSize', 'safeMode', 'enableManager', 'logLevel', 'disableMetadata'
      ])
      
      console.log('[TabContainer] generalKeys:', Array.from(generalKeys))
      console.log('[TabContainer] accelerationKeys:', Array.from(accelerationKeys))

      Object.keys(changes).forEach(key => {
        console.log(`[TabContainer] 处理字段: ${key}, 值:`, (changes as any)[key])
        
        if (key === 'alias') {
          aliasChange = { alias: changes.alias }
          console.log('[TabContainer] 识别为 alias 字段')
        } else if (generalKeys.has(key)) {
          generalChanges[key] = (changes as any)[key]
          console.log(`[TabContainer] 识别为 general 字段: ${key}`)
        } else if (accelerationKeys.has(key) || knownAccelerationFields.has(key)) {
          accelerationChanges[key] = (changes as any)[key]
          console.log(`[TabContainer] 识别为 acceleration 字段: ${key}`)
          console.log(`[TabContainer] 赋值后 accelerationChanges:`, accelerationChanges)
        } else {
          console.warn(`[TabContainer] 未识别的字段: ${key}`)
        }
      })

      console.log('[TabContainer] generalChanges:', generalChanges)
      console.log('[TabContainer] accelerationChanges:', accelerationChanges)
      console.log('[TabContainer] aliasChange:', aliasChange)
      
      const finalChanges = {
        ...aliasChange,
        ...(Object.keys(generalChanges).length > 0 && { general: { ...config.general, ...generalChanges } }),
        ...(Object.keys(accelerationChanges).length > 0 && { acceleration: { ...config.acceleration, ...accelerationChanges } })
      }
      
      console.log('[TabContainer] 最终传递给 onConfigChange 的变更:', finalChanges)
      onConfigChange(finalChanges)
    }

    const handleAccelerationChange = (changes: Partial<typeof config.acceleration>) => {
      const currentAcceleration = config.acceleration || {}
      onConfigChange({
        acceleration: { ...currentAcceleration, ...changes }
      })
    }

    const handleRefreshDependencies = () => {
      onRefreshDependencies?.()
    }

    const handlePresetSelect = (presetId: string, presetConfig: Record<string, any>, presetName?: string) => {
      onPresetSelect?.(presetId, presetConfig, presetName)
    }

    return (
      <>
        {activeTab === 'general' && (
          <GeneralTab
            config={{ ...config.general, ...config.acceleration, alias: config.alias }}
            dependencies={config.dependencies}
            onConfigChange={handleGeneralChange}
            onRefreshDependencies={handleRefreshDependencies}
          />
        )}
        {activeTab === 'acceleration' && (
          <AccelerationTab
            ref={accelerationTabRef}
            {...({ config: config.acceleration } as AccelerationTabProps)}
            currentEnvId={currentEnvId}
            onConfigChange={handleAccelerationChange}
            onPresetSelect={handlePresetSelect}
            onShowToast={onShowToast}
            onCreatePreset={onCreatePreset}
            onEditPreset={onEditPreset}
            onDeletePreset={onDeletePreset}
            onSaveAsPreset={onSaveAsPreset}
            onManagePresets={onManagePresets}
          />
        )}
        {activeTab === 'modelPaths' && (
          <ModelPathsTab comfyuiPath={config.general?.comfyuiPath || ''} />
        )}
        {activeTab === 'advancedEnv' && (
          <AdvancedEnvTab
            value={config.advancedEnvVars || ''}
            onChange={(value) => onConfigChange({ advancedEnvVars: value })}
          />
        )}
      </>
    )
  }
)
