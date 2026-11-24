/**
 * Bridge service for communicating with the backend via pywebview.
 */

import type {
  EnvironmentConfig,
  EnvironmentListResponse,
  EnvironmentResponse,
  EnvironmentScanResult,
  DependenciesResponse,
  DirectorySelectResponse,
  ConfigExportResponse,
  ConfigImportResponse,
  PyTorchBackendResponse,
  FilteredComputeDevicesResponse,
} from '../types/environment';

// 导入 Mock 数据
import * as mockEnvApi from '../mocks/env';

export interface LoraModel {
  id: string;
  name: string;
  file_path: string;
  file_size?: number;
  file_hash?: string;
  size_kb?: number;
  preview_url?: string;
  preview_files?: string[];
  preview_blurred?: boolean;
  tags?: string[];
  trigger_words?: string[];
  notes?: string;
  is_local?: boolean;
  civitai_id?: string;
  civitai_version?: string;
  civitai_url?: string;
  category?: string;
  folder?: string;
  folder_id?: string;
  default_weight?: string;
  recommended_sampler?: string;
  created_at?: string;
  updated_at?: string;
}

export interface LoraFolderNode {
  id: string;
  name: string;
  path: string;
  children?: LoraFolderNode[];
}

/**
 * Environment API interface
 */
export interface EnvironmentAPI {
  getEnvironments(): Promise<EnvironmentListResponse>;
  addEnvironment(path: string, name?: string): Promise<EnvironmentResponse>;
  deleteEnvironment(envId: string): Promise<{ success: boolean; error_code?: number; error_message?: string }>;
  updateEnvironment(envId: string, config: Partial<EnvironmentConfig>): Promise<EnvironmentResponse>;
  set_current_environment(envId: string): Promise<{ success: boolean; error_code?: number; error_message?: string }>;
  scanEnvironment(path: string): Promise<EnvironmentScanResult>;
  getDependencies(envId: string): Promise<DependenciesResponse>;
  selectDirectory(): Promise<DirectorySelectResponse>;
  exportConfig(envId: string): Promise<ConfigExportResponse>;
  importConfig(configData: string): Promise<ConfigImportResponse>;
}

/**
 * 检查是否在开发环境（浏览器）
 */
const isDevelopment = (): boolean => {
  // 通过端口判断是否在纯浏览器开发环境
  // Vite 默认端口 5173，或其他开发服务器端口 3000
  const isPureBrowserDev = window.location.port === '5173' || window.location.port === '3000'
  return isPureBrowserDev
};

/**
 * Bridge service implementation
 */
class BridgeService implements EnvironmentAPI {
  /**
   * Call backend API
   */
  private async callApi<T>(methodName: string, ...args: any[]): Promise<T> {
    try {
      // console.log(`[BridgeService] 调用后端 API: ${methodName}`, args);
      
      // Check if pywebview is available
      if (!window.pywebview) {
        throw new Error('pywebview is not available');
      }

      // Call the API method using type assertion
      const api = window.pywebview.api as any;
      // console.log(`[BridgeService] pywebview.api 可用，开始调用 ${methodName}...`);
      
      const result = await api[methodName](...args);
      
      // console.log(`[BridgeService] ${methodName} 调用成功，结果:`, result);
      return result as T;
    } catch (error) {
      console.error(`[BridgeService] ${methodName} 调用失败:`, error);
      throw error;
    }
  }

  /**
   * Get app info
   */
  async getAppInfo() {
    return this.callApi<{ version: string; env: string }>('getAppInfo');
  }

  /**
   * Get app version
   */
  async getAppVersion(): Promise<string> {
    if (isDevelopment()) {
      return 'RC_0.7.3';
    }
    const info = await this.getAppInfo();
    return info.version;
  }

  /**
   * Close app
   */
  async closeApp() {
    return this.callApi<void>('closeApp');
  }

  /**
   * Get close behavior preference
   */
  async getCloseBehavior(): Promise<{ success: boolean; action: string | null; dontAskAgain: boolean }> {
    return this.callApi<{ success: boolean; action: string | null; dontAskAgain: boolean }>('getCloseBehavior');
  }

  /**
   * Set close behavior preference
   */
  async setCloseBehavior(action: string, dontAskAgain: boolean): Promise<{ success: boolean; message?: string }> {
    return this.callApi<{ success: boolean; message?: string }>('setCloseBehavior', action, dontAskAgain);
  }

  /**
   * Reset backend close-dialog pending flag (called when the close confirm dialog is dismissed)
   */
  async resetCloseDialogState(): Promise<{ success: boolean }> {
    if (isDevelopment()) {
      return { success: true };
    }
    return this.callApi<{ success: boolean }>('resetCloseDialogState');
  }

  /**
   * Minimize app
   */
  async minimizeApp() {
    return this.callApi<void>('minimizeApp');
  }

  /**
   * Minimize app to system tray
   */
  async minimizeToTray(): Promise<{ success: boolean; message?: string }> {
    return this.callApi<{ success: boolean; message?: string }>('minimizeToTray');
  }

  /**
   * Maximize app
   */
  async maximizeApp() {
    return this.callApi<void>('maximizeApp');
  }

  /**
   * Check if app is maximized
   */
  async isMaximized(): Promise<boolean> {
    if (isDevelopment()) {
      // 开发环境返回 false
      return false;
    }
    return this.callApi<boolean>('isMaximized');
  }

  /**
   * Toggle fullscreen
   */
  async toggleFullscreen() {
    return this.callApi<void>('toggleFullscreen');
  }

  /**
   * Check if app is fullscreen
   */
  async isFullscreen(): Promise<boolean> {
    if (isDevelopment()) {
      // 开发环境返回 false
      return false;
    }
    return this.callApi<boolean>('isFullscreen');
  }

  /**
   * Force release mouse (for ESC key to exit drag state)
   */
  async forceReleaseMouse(): Promise<{ success: boolean; error?: string }> {
    if (isDevelopment()) {
      console.log('[BridgeService] 开发环境模拟强制释放鼠标');
      return { success: true };
    }
    return this.callApi<{ success: boolean; error?: string }>('forceReleaseMouse');
  }

  /**
   * Restore window on drag (when maximized)
   * @param mouseX Mouse X position relative to screen
   * @param mouseY Mouse Y position relative to screen
   */
  async restoreWindowOnDrag(mouseX?: number, mouseY?: number): Promise<{ success: boolean; message?: string; windowX?: number; windowY?: number }> {
    if (isDevelopment()) {
      return { success: false, message: 'Development mode' }
    }
    return this.callApi<{ success: boolean; message?: string; windowX?: number; windowY?: number }>('restoreWindowOnDrag', mouseX, mouseY)
  }

  async moveWindow(x: number, y: number): Promise<void> {
    if (isDevelopment()) {
      return
    }
    return this.callApi<void>('moveWindow', x, y)
  }

  async moveWindowTo(x: number, y: number): Promise<void> {
    if (isDevelopment()) {
      return
    }
    return this.callApi<void>('moveWindowTo', x, y)
  }

  /**
   * 从全屏直接切换到最大化
   * 跳过中间的恢复窗口步骤，避免闪烁
   */
  async fullscreenToMaximize(): Promise<{ success: boolean; message?: string }> {
    if (isDevelopment()) {
      return { success: false, message: 'Development mode' }
    }
    return this.callApi<{ success: boolean; message?: string }>('fullscreenToMaximize')
  }

  /**
   * Resize window
   */
  async resizeWindow(width: number, height: number) {
    return this.callApi<boolean>('resizeWindow', width, height);
  }

  /**
   * Resize window with position (for drag resize from corners)
   */
  async resizeWindowWithPosition(width: number, height: number, x: number, y: number) {
    if (isDevelopment()) {
      console.log('[BridgeService] 开发环境模拟调整窗口大小和位置:', { width, height, x, y });
      return true;
    }
    return this.callApi<boolean>('resizeWindowWithPosition', width, height, x, y);
  }

  /**
   * Get all environments
   */
  async getEnvironments(): Promise<EnvironmentListResponse> {
    if (isDevelopment()) {
      // 使用 Mock 数据
      const environments = await mockEnvApi.fetchEnvironments();
      const currentEnv = environments.find(e => e.isActive);
      return {
        success: true,
        environments,
        current_environment_id: currentEnv?.id || null
      };
    }
    return this.callApi<EnvironmentListResponse>('get_environments');
  }

  /**
   * Add a new environment
   */
  async addEnvironment(path: string, name?: string): Promise<EnvironmentResponse> {
    if (isDevelopment()) {
      // 使用 Mock 数据
      const environment = await mockEnvApi.createEnvironment(path);
      return {
        success: true,
        environment
      };
    }
    // 获取当前语言设置
    const lang = localStorage.getItem('language') || 'zh-CN';
    const langCode = lang === 'zh-CN' ? 'zh' : 'en';
    return this.callApi<EnvironmentResponse>('add_environment', path, name, langCode);
  }

  /**
   * Delete an environment
   */
  async deleteEnvironment(envId: string): Promise<{ success: boolean; error_code?: number; error_message?: string }> {
    if (isDevelopment()) {
      // 使用 Mock 数据
      await mockEnvApi.deleteEnvironment(envId);
      return { success: true };
    }
    return this.callApi<{ success: boolean; error_code?: number; error_message?: string }>('delete_environment', envId);
  }

  /**
   * Update environment configuration
   */
  async updateEnvironment(envId: string, config: Partial<EnvironmentConfig>): Promise<EnvironmentResponse> {
    if (isDevelopment()) {
      // 使用 Mock 数据
      await mockEnvApi.saveEnvConfig(envId, config as EnvironmentConfig);
      const environment = await mockEnvApi.getEnvConfig(envId);
      return {
        success: true,
        environment
      };
    }
    return this.callApi<EnvironmentResponse>('update_environment', envId, config);
  }

  /**
   * Set the current active environment
   */
  async set_current_environment(envId: string): Promise<{ success: boolean; error_code?: number; error_message?: string }> {
    if (isDevelopment()) {
      // 使用 Mock 数据
      await mockEnvApi.switchEnvironment(envId);
      return { success: true };
    }
    return this.callApi<{ success: boolean; error_code?: number; error_message?: string }>('set_current_environment', envId);
  }

  /**
   * Reorder environments
   */
  async reorderEnvironments(envIds: string[]): Promise<{ success: boolean; message?: string; error_message?: string }> {
    if (isDevelopment()) {
      console.log('[BridgeService] 开发环境模拟重排环境顺序');
      return { success: true };
    }
    return this.callApi<{ success: boolean; message?: string; error_message?: string }>('reorder_environments', envIds);
  }

  /**
   * Scan a ComfyUI environment
   */
  async scanEnvironment(path: string): Promise<EnvironmentScanResult> {
    if (isDevelopment()) {
      // 使用 Mock 数据
      const isValid = await mockEnvApi.validateComfyUIPath(path);
      return {
        success: true,
        scan_result: {
          is_valid: isValid,
          python_version: '3.12.0',
          comfyui_version: '0.2.8',
          python_directory: `${path}\\python`,
          pip_directory: `${path}\\python\\Scripts\\pip`,
          available_gpus: ['NVIDIA RTX 4090'],
          dependencies: {}
        }
      };
    }
    // 获取当前语言设置
    const lang = localStorage.getItem('language') || 'zh-CN';
    const langCode = lang === 'zh-CN' ? 'zh' : 'en';
    return this.callApi<EnvironmentScanResult>('scan_environment', path, langCode);
  }

  /**
   * Get dependency information for an environment
   */
  async getDependencies(envId: string): Promise<DependenciesResponse> {
    if (isDevelopment()) {
      // 使用 Mock 数据
      const dependencies = await mockEnvApi.getDependencies(envId);
      return {
        success: true,
        dependencies
      };
    }
    return this.callApi<DependenciesResponse>('get_dependencies', envId);
  }

  /**
   * Open directory selection dialog
   */
  async selectDirectory(): Promise<DirectorySelectResponse> {
    if (isDevelopment()) {
      // 在开发环境中，返回一个模拟路径
      return {
        success: true,
        path: 'C:\\ComfyUI-Dev'
      };
    }
    return this.callApi<DirectorySelectResponse>('select_directory');
  }

  /**
   * Export environment configuration
   */
  async exportConfig(envId: string): Promise<ConfigExportResponse> {
    if (isDevelopment()) {
      // 使用 Mock 数据
      const env = await mockEnvApi.getEnvConfig(envId);
      return {
        success: true,
        config: JSON.stringify(env, null, 2)
      };
    }
    return this.callApi<ConfigExportResponse>('export_config', envId);
  }

  /**
   * Import environment configuration
   */
  async importConfig(configData: string): Promise<ConfigImportResponse> {
    if (isDevelopment()) {
      // 在开发环境中，暂不支持导入
      return {
        success: false,
        error_message: '开发环境暂不支持导入配置'
      };
    }
    return this.callApi<ConfigImportResponse>('import_config', configData);
  }

  /**
   * Get compute devices list
   */
  async getComputeDevices(): Promise<import('../types/environment').ComputeDevice[]> {
    if (isDevelopment()) {
      // 使用 Mock 数据
      return mockEnvApi.getComputeDevices();
    }
    
    const response = await this.callApi<import('../types/environment').ComputeDevicesResponse>('get_compute_devices');
    if (response.success && response.devices) {
      return response.devices;
    }
    throw new Error(response.error_message || 'Failed to get compute devices');
  }

  /**
   * Get PyTorch backend info for an environment
   */
  async getPytorchBackend(envId: string): Promise<PyTorchBackendResponse> {
    if (isDevelopment()) {
      return {
        success: true,
        pytorchBackend: {
          backend: 'cuda',
          torchVersion: '2.4.0+cu124',
          cudaAvailable: true,
          xpuAvailable: false,
          ipexInstalled: false,
          error: null
        }
      };
    }
    return this.callApi<PyTorchBackendResponse>('get_pytorch_backend', envId);
  }

  /**
   * Get filtered compute devices list based on PyTorch backend compatibility
   */
  async getFilteredComputeDevices(envId: string): Promise<FilteredComputeDevicesResponse> {
    if (isDevelopment()) {
      const devices = await mockEnvApi.getComputeDevices();
      return {
        success: true,
        devices: devices.map(d => ({ ...d, compatible: true, incompatibilityReason: '' })),
        pytorchBackend: {
          backend: 'cuda',
          torchVersion: '2.4.0+cu124',
          cudaAvailable: true,
          xpuAvailable: false,
          ipexInstalled: false,
          error: null
        }
      };
    }
    return this.callApi<FilteredComputeDevicesResponse>('get_filtered_compute_devices', envId);
  }

  /**
   * Open file save dialog
   */
  async saveFileDialog(defaultName: string = '', fileFilter: string = 'JSON files (*.json)'): Promise<{
    success: boolean;
    path?: string;
    error_code?: string;
    error_message?: string;
  }> {
    if (isDevelopment()) {
      // 在开发环境中，返回一个模拟路径
      return {
        success: true,
        path: `C:\\Temp\\${defaultName}.json`
      };
    }
    return this.callApi('save_file_dialog', defaultName, fileFilter);
  }

  /**
   * Save preset data to file
   */
  async savePresetToFile(filePath: string, presetData: any): Promise<{
    success: boolean;
    message?: string;
    error_code?: string;
    error_message?: string;
  }> {
    if (isDevelopment()) {
      // 开发环境不实际保存文件
      console.log('[BridgeService] 开发环境模拟保存预设文件:', filePath);
      return {
        success: true,
        message: `预设已保存到 ${filePath}`
      };
    }
    return this.callApi('save_preset_to_file', filePath, presetData);
  }

  /**
   * Start async dependencies update
   * 启动异步依赖信息更新（后台更新所有环境的依赖信息）
   */
  async startAsyncDependenciesUpdate(): Promise<{ success: boolean; message?: string }> {
    if (isDevelopment()) {
      // 开发环境不执行异步更新
      console.log('[BridgeService] 开发环境跳过异步依赖信息更新');
      return {
        success: true,
        message: '开发环境跳过异步依赖信息更新'
      };
    }
    return this.callApi<{ success: boolean; message?: string }>('start_async_dependencies_update');
  }

  // ========== 预设管理 API ==========

  /**
   * 导出当前环境配置为预设
   */
  async exportPreset(envId: string, name: string, description: string = '', vramRequirement: string = 'N/A'): Promise<{
    success: boolean;
    data?: {
      preset: any;
      file_path: string;
    };
    error_code?: string;
    error_message?: string;
  }> {
    if (isDevelopment()) {
      // 开发环境模拟导出
      console.log('[BridgeService] 开发环境模拟导出预设');
      return {
        success: true,
        data: {
          preset: {
            id: `custom_${Date.now()}`,
            name,
            description,
            vram_requirement: vramRequirement,
            config: {}
          },
          file_path: 'dev://preset.json'
        }
      };
    }
    return this.callApi('export_preset', envId, name, description, vramRequirement);
  }

  async batchExportPresets(presetsData: any[], savePath: string): Promise<{
    success: boolean;
    message?: string;
    error_code?: string;
    error_message?: string;
  }> {
    if (isDevelopment()) {
      console.log('[BridgeService] 开发环境模拟批量导出预设');
      return { success: true, message: '预设已保存' };
    }
    return this.callApi('batch_export_presets', presetsData, savePath);
  }

  /**
   * 从预设数据导入配置到环境
   */
  async importPreset(presetData: any, envId: string): Promise<{
    success: boolean;
    error_code?: string;
    error_message?: string;
    data?: {
      preset_id: string;
      preset_name: string;
    };
  }> {
    if (isDevelopment()) {
      // 开发环境模拟导入
      console.log('[BridgeService] 开发环境模拟导入预设');
      return { 
        success: true,
        data: {
          preset_id: 'imported_preset',
          preset_name: presetData.name || '导入的预设'
        }
      };
    }
    return this.callApi('import_preset', presetData, envId);
  }

  /**
   * 创建用户预设
   */
  async createCustomPreset(
    envId: string,
    presetId?: string,
    name: string = '用户预设',
    description: string = ''
  ): Promise<{
    success: boolean;
    data?: {
      preset_id: string;
    };
    error_code?: string;
    error_message?: string;
  }> {
    if (isDevelopment()) {
      // 开发环境模拟创建
      console.log('[BridgeService] 开发环境模拟创建预设');
      return {
        success: true,
        data: {
          preset_id: presetId || `custom_${Date.now()}`
        }
      };
    }
    return this.callApi('create_custom_preset', envId, presetId, name, description);
  }

  /**
   * 删除用户预设
   */
  async deleteCustomPreset(presetId: string): Promise<{
    success: boolean;
    error_code?: string;
    error_message?: string;
  }> {
    if (isDevelopment()) {
      // 开发环境模拟删除
      console.log('[BridgeService] 开发环境模拟删除预设');
      return { success: true };
    }
    return this.callApi('delete_custom_preset', presetId);
  }

  /**
   * 更新用户预设
   */
  async updateCustomPreset(
    presetId: string,
    updates: Record<string, any>
  ): Promise<{
    success: boolean;
    error_code?: string;
    error_message?: string;
  }> {
    if (isDevelopment()) {
      // 开发环境模拟更新
      console.log('[BridgeService] 开发环境模拟更新预设');
      return { success: true };
    }
    return this.callApi('update_custom_preset', presetId, updates);
  }

  /**
   * 获取预设详细信息
   */
  async getPresetDetails(presetId: string): Promise<{
    success: boolean;
    data?: any;
    error_code?: string;
    error_message?: string;
  }> {
    if (isDevelopment()) {
      // 开发环境模拟获取
      console.log('[BridgeService] 开发环境模拟获取预设详情');
      return {
        success: true,
        data: {
          id: presetId,
          name: '示例预设',
          description: '开发环境示例',
          vram_requirement: '8GB+',
          config: {}
        }
      };
    }
    return this.callApi('get_preset_details', presetId);
  }

  /**
   * 获取所有预设列表（包含索引信息）
   */
  async getAllPresets(): Promise<{
    success: boolean;
    data?: any[];
    error_code?: string;
    error_message?: string;
  }> {
    if (isDevelopment()) {
      // 开发环境使用 Mock 数据
      console.log('[BridgeService] 开发环境使用 Mock 预设列表');
      return {
        success: true,
        data: mockEnvApi.PRESETS.map(preset => ({
          id: preset.id,
          name: preset.name,
          description: preset.description,
          vram_requirement: preset.vramRequirement,
          type: 'builtin'
        }))
      };
    }
    return this.callApi('get_all_presets');
  }

  /**
   * 检测目录结构，识别模型路径配置
   */
  async detectModelPathsStructure(path: string): Promise<{
    success: boolean;
    is_comfyui_style?: boolean;
    detected_paths?: Record<string, string>;
    error_message?: string;
  }> {
    if (isDevelopment()) {
      console.log('[BridgeService] 开发环境模拟检测目录结构');
      // 开发环境模拟：如果路径包含 models，返回模拟的检测结果
      if (path.toLowerCase().includes('comfyui') || path.toLowerCase().includes('models')) {
        return {
          success: true,
          is_comfyui_style: true,
          detected_paths: {
            checkpoints: 'models/checkpoints',
            clip: 'models/clip',
            loras: 'models/loras',
            vae: 'models/vae',
            embeddings: 'models/embeddings'
          }
        };
      }
      return {
        success: true,
        is_comfyui_style: false,
        detected_paths: {}
      };
    }
    return this.callApi('detect_model_paths_structure', path);
  }

  // ========== ComfyUI 进程管理 API ==========

  /**
   * 启动 ComfyUI
   */
  async startComfyUI(envId: string): Promise<{
    success: boolean;
    message?: string;
    error?: string;
  }> {
    if (isDevelopment()) {
      console.log('[BridgeService] 开发环境模拟启动 ComfyUI');
      return {
        success: true,
        message: 'ComfyUI 启动成功 (Mock)'
      };
    }
    return this.callApi('start_comfyui', envId);
  }

  /**
   * 停止 ComfyUI
   */
  async stopComfyUI(): Promise<{
    success: boolean;
    message?: string;
    error?: string;
  }> {
    if (isDevelopment()) {
      console.log('[BridgeService] 开发环境模拟停止 ComfyUI');
      return {
        success: true,
        message: 'ComfyUI 已停止 (Mock)'
      };
    }
    return this.callApi('stop_comfyui');
  }

  /**
   * 获取 ComfyUI 运行状态
   */
  async getComfyUIStatus(): Promise<{
    success: boolean;
    is_running: boolean;
    pid?: number;
    env_id?: string;
    error?: string;
  }> {
    if (isDevelopment()) {
      console.log('[BridgeService] 开发环境返回 Mock 状态');
      return {
        success: true,
        is_running: false,
        pid: undefined,
        env_id: undefined
      };
    }
    return this.callApi('get_comfyui_status');
  }

  // ========== 极客模式 API ==========

  /**
   * 获取所有极客模式预设
   */
  async getGeekPresets(): Promise<import('../types/environment').GeekPreset[]> {
    if (isDevelopment()) {
      console.log('[BridgeService] 开发环境返回 Mock 极客模式预设');
      return [
        {
          id: 'geek_1',
          name: '高性能配置',
          description: '适用于高端显卡的极客配置',
          args: '--listen 0.0.0.0\n--port 8188\n--gpu-only\n--highvram\n--fp16-vae',
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString()
        }
      ];
    }
    const result = await this.callApi<{ success: boolean; data?: any[]; error?: string }>('get_geek_presets');
    if (result.success && Array.isArray(result.data)) {
      return result.data;
    }
    return [];
  }

  /**
   * 创建极客模式预设
   */
  async createGeekPreset(name: string, description: string, args: string, presetId?: string): Promise<import('../types/environment').GeekPreset> {
    if (isDevelopment()) {
      console.log('[BridgeService] 开发环境模拟创建极客模式预设');
      return {
        id: presetId || `geek_${Date.now()}`,
        name,
        description,
        args,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      };
    }
    return this.callApi('create_geek_preset', name, description, args, presetId);
  }

  /**
   * 删除极客模式预设
   */
  async deleteGeekPreset(presetId: string): Promise<void> {
    if (isDevelopment()) {
      console.log('[BridgeService] 开发环境模拟删除极客模式预设');
      return;
    }
    return this.callApi('delete_geek_preset', presetId);
  }

  /**
   * 更新极客模式预设
   */
  async updateGeekPreset(
    presetId: string,
    name?: string,
    description?: string,
    args?: string
  ): Promise<import('../types/environment').GeekPreset> {
    if (isDevelopment()) {
      console.log('[BridgeService] 开发环境模拟更新极客模式预设');
      return {
        id: presetId,
        name: name || '示例预设',
        description: description || '开发环境示例',
        args: args || '--listen 0.0.0.0\n--port 8188',
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      };
    }
    const result = await this.callApi<{ success: boolean; data?: any; error?: string }>(
      'update_geek_preset',
      presetId,
      name,
      description,
      args
    );
    if (result.success && result.data) {
      return result.data;
    }
    throw new Error(result.error || 'Failed to update geek preset');
  }

  /**
   * 加载极客模式预设
   */
  async loadGeekPreset(presetId: string): Promise<import('../types/environment').GeekPreset> {
    if (isDevelopment()) {
      console.log('[BridgeService] 开发环境模拟加载极客模式预设');
      return {
        id: presetId,
        name: '示例预设',
        description: '开发环境示例',
        args: '--listen 0.0.0.0\n--port 8188',
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      };
    }
    return this.callApi('load_geek_preset', presetId);
  }

  /**
   * 验证极客模式参数
   */
  async validateGeekArgs(args: string): Promise<{
    success: boolean;
    errors?: string[];
  }> {
    if (isDevelopment()) {
      console.log('[BridgeService] 开发环境模拟验证极客模式参数');
      return { success: true };
    }
    return this.callApi('validate_geek_args', args);
  }

  // ========== LoRA 管理 API ==========

  /**
   * 获取 LoRA 完整配置
   */
  async loraGetConfig(): Promise<{
    success: boolean;
    config?: {
      display?: {
        grid_columns?: number;
        preview_short_edge?: number;
        minimal_list?: boolean;
        sort_order?: 'asc' | 'desc';
      };
      civitai?: {
        api_key?: string;
        nsfw_enabled?: boolean;
        preview_download_limit?: number;
      };
      scan_paths?: Array<{
        id: string;
        path: string;
        name?: string;
        category?: string;
        enabled?: boolean;
      }>;
      categories?: Array<{
        id: string;
        name: string;
      }>;
    };
    message?: string;
  }> {
    if (isDevelopment()) {
      console.log('[BridgeService] 开发环境模拟获取 LoRA 配置');
      return {
        success: true,
        config: {
          display: {
            grid_columns: 2,
            preview_short_edge: 234,
            minimal_list: false,
            sort_order: 'asc'
          },
          civitai: {
            api_key: '',
            nsfw_enabled: false,
            preview_download_limit: 5
          },
          scan_paths: [],
          categories: []
        }
      };
    }
    return this.callApi('lora_get_config');
  }

  /**
   * 更新 LoRA 配置
   */
  async loraUpdateConfig(updates: Record<string, any>): Promise<{
    success: boolean;
    config?: any;
    message?: string;
  }> {
    if (isDevelopment()) {
      console.log('[BridgeService] 开发环境模拟更新 LoRA 配置');
      return { success: true, config: updates };
    }
    return this.callApi('lora_update_config', updates);
  }

  /**
   * 重置 LoRA 配置
   */
  async loraResetConfig(): Promise<{
    success: boolean;
    config?: any;
    message?: string;
  }> {
    if (isDevelopment()) {
      console.log('[BridgeService] 开发环境模拟重置 LoRA 配置');
      return { success: true };
    }
    return this.callApi('lora_reset_config');
  }

  // ========== 工作流配置 API ==========

  /**
   * 获取工作流配置
   */
  async workflowGetConfig(): Promise<{
    success: boolean;
    config?: {
      version?: string;
      use_global_path?: boolean;
      global_path?: string;
      env_paths?: Record<string, string>;
    };
    message?: string;
  }> {
    return this.callApi('workflow_get_config');
  }

  /**
   * 更新工作流配置
   */
  async workflowUpdateConfig(updates: Record<string, any>): Promise<{
    success: boolean;
    config?: any;
    message?: string;
  }> {
    return this.callApi('workflow_update_config', updates);
  }

  /**
   * 设置指定环境的工作流目录
   */
  async workflowSetEnvPath(envId: string, path: string): Promise<{
    success: boolean;
    message?: string;
  }> {
    return this.callApi('workflow_set_env_path', envId, path);
  }

  /**
   * 设置全局工作流目录
   */
  async workflowSetGlobalPath(path: string): Promise<{
    success: boolean;
    message?: string;
  }> {
    return this.callApi('workflow_set_global_path', path);
  }

  /**
   * 设置是否使用全局工作流目录
   */
  async workflowSetUseGlobalPath(useGlobal: boolean): Promise<{
    success: boolean;
    message?: string;
  }> {
    return this.callApi('workflow_set_use_global_path', useGlobal);
  }

  /**
   * 移除指定环境的工作流目录配置
   */
  async workflowRemoveEnvPath(envId: string): Promise<{
    success: boolean;
    message?: string;
  }> {
    return this.callApi('workflow_remove_env_path', envId);
  }

  /**
   * 初始化所有环境的工作流目录配置
   */
  async workflowInitializeAllEnvPaths(): Promise<{
    success: boolean;
    message?: string;
  }> {
    return this.callApi('workflow_initialize_all_env_paths');
  }

  /**
   * 获取 LoRA 扫描路径列表
   */
  async loraGetScanPaths(): Promise<{
    success: boolean;
    paths?: Array<{
      id: string;
      path: string;
      name?: string;
      category?: string;
      enabled?: boolean;
    }>;
    message?: string;
  }> {
    if (isDevelopment()) {
      console.log('[BridgeService] 开发环境模拟获取扫描路径');
      return { success: true, paths: [] };
    }
    return this.callApi('lora_get_scan_paths');
  }

  /**
   * 添加 LoRA 扫描路径
   */
  async loraAddScanPath(path: string, name?: string, category?: string): Promise<{
    success: boolean;
    path?: any;
    message?: string;
  }> {
    if (isDevelopment()) {
      console.log('[BridgeService] 开发环境模拟添加扫描路径');
      return { success: true, path: { id: `path_${Date.now()}`, path, name, category } };
    }
    return this.callApi('lora_add_scan_path', path, name, category);
  }

  /**
   * 更新 LoRA 扫描路径
   */
  async loraUpdateScanPath(pathId: string, updates: Record<string, any>): Promise<{
    success: boolean;
    message?: string;
  }> {
    if (isDevelopment()) {
      console.log('[BridgeService] 开发环境模拟更新扫描路径');
      return { success: true };
    }
    return this.callApi('lora_update_scan_path', pathId, updates);
  }

  /**
   * 删除 LoRA 扫描路径
   */
  async loraRemoveScanPath(pathId: string): Promise<{
    success: boolean;
    message?: string;
  }> {
    if (isDevelopment()) {
      console.log('[BridgeService] 开发环境模拟删除扫描路径');
      return { success: true };
    }
    return this.callApi('lora_remove_scan_path', pathId);
  }

  /**
   * 获取 LoRA 分类列表
   */
  async loraGetCategories(): Promise<{
    success: boolean;
    categories?: Array<{ id: string; name: string }>;
    message?: string;
  }> {
    if (isDevelopment()) {
      console.log('[BridgeService] 开发环境模拟获取分类');
      return { success: true, categories: [] };
    }
    return this.callApi('lora_get_categories');
  }

  /**
   * 添加 LoRA 分类
   */
  async loraAddCategory(name: string, id?: string): Promise<{
    success: boolean;
    category?: { id: string; name: string };
    message?: string;
  }> {
    if (isDevelopment()) {
      console.log('[BridgeService] 开发环境模拟添加分类');
      return { success: true, category: { id: id || `cat_${Date.now()}`, name } };
    }
    return this.callApi('lora_add_category', name, id);
  }

  /**
   * 更新 LoRA 分类
   */
  async loraUpdateCategory(categoryId: string, updates: Record<string, any>): Promise<{
    success: boolean;
    message?: string;
  }> {
    if (isDevelopment()) {
      console.log('[BridgeService] 开发环境模拟更新分类');
      return { success: true };
    }
    return this.callApi('lora_update_category', categoryId, updates);
  }

  /**
   * 删除 LoRA 分类
   */
  async loraRemoveCategory(categoryId: string): Promise<{
    success: boolean;
    message?: string;
  }> {
    if (isDevelopment()) {
      console.log('[BridgeService] 开发环境模拟删除分类');
      return { success: true };
    }
    return this.callApi('lora_remove_category', categoryId);
  }

  /**
   * 获取 LoRA 显示配置
   */
  async loraGetDisplayConfig(): Promise<{
    success: boolean;
    display?: {
      grid_columns?: number;
      preview_short_edge?: number;
      minimal_list?: boolean;
      sort_order?: 'asc' | 'desc';
    };
    message?: string;
  }> {
    if (isDevelopment()) {
      console.log('[BridgeService] 开发环境模拟获取显示配置');
      return {
        success: true,
        display: {
          grid_columns: 2,
          preview_short_edge: 234,
          minimal_list: false,
          sort_order: 'asc'
        }
      };
    }
    return this.callApi('lora_get_display_config');
  }

  /**
   * 更新 LoRA 显示配置
   */
  async loraUpdateDisplayConfig(updates: Record<string, any>): Promise<{
    success: boolean;
    message?: string;
  }> {
    if (isDevelopment()) {
      console.log('[BridgeService] 开发环境模拟更新显示配置');
      return { success: true };
    }
    return this.callApi('lora_update_display_config', updates);
  }

  /**
   * 同步 LoRA 模型
   */
  async loraSyncModels(): Promise<{
    success: boolean;
    result?: {
      added: number;
      updated: number;
      removed: number;
      unchanged: number;
    };
    total?: number;
    models?: LoraModel[];
    message?: string;
    error?: string;
  }> {
    if (isDevelopment()) {
      console.log('[BridgeService] 开发环境模拟同步模型');
      return { success: true, result: { added: 0, updated: 0, removed: 0, unchanged: 0 }, models: [] };
    }
    return this.callApi('lora_sync_models');
  }

  /**
   * 从 Civitai 拉取 LoRA 信息
   */
  async loraPullFromCivitai(full: boolean = false): Promise<{
    success: boolean;
    message?: string;
    error?: string;
  }> {
    if (isDevelopment()) {
      console.log('[BridgeService] 开发环境模拟从 Civitai 拉取');
      return { success: true, message: '拉取完成' };
    }
    return this.callApi('lora_pull_from_civitai', full);
  }

  /**
   * 停止 LoRA 拉取
   */
  async loraStopPull(): Promise<{
    success: boolean;
    message?: string;
  }> {
    if (isDevelopment()) {
      console.log('[BridgeService] 开发环境模拟停止拉取');
      return { success: true };
    }
    return this.callApi('lora_stop_pull');
  }

  /**
   * 获取 LoRA 拉取状态
   */
  async loraGetPullStatus(): Promise<{
    pulling: boolean;
    stopping: boolean;
    progress?: any;
  }> {
    if (isDevelopment()) {
      console.log('[BridgeService] 开发环境模拟获取拉取状态');
      return { pulling: false, stopping: false, progress: null };
    }
    return this.callApi('lora_get_pull_status');
  }

  /**
   * 获取 LoRA 模型列表
   */
  async loraGetModels(): Promise<{
    success: boolean;
    count?: number;
    models?: LoraModel[];
    message?: string;
  }> {
    if (isDevelopment()) {
      console.log('[BridgeService] 开发环境模拟获取模型列表');
      return { success: true, count: 0, models: [] };
    }
    return this.callApi('lora_get_models');
  }

  /**
   * 更新 LoRA 模型
   */
  async loraUpdateModel(modelId: string, updates: Record<string, any>): Promise<{
    success: boolean;
    message?: string;
  }> {
    if (isDevelopment()) {
      console.log('[BridgeService] 开发环境模拟更新模型');
      return { success: true };
    }
    return this.callApi('lora_update_model', modelId, updates);
  }

  async loraBatchUpdateFolder(modelIds: string[], folderId: string): Promise<{
    success: boolean;
    message: string;
    updated_count: number;
  }> {
    if (isDevelopment()) {
      console.log('[BridgeService] 开发环境模拟批量更新分组');
      return { success: true, message: '已更新分组', updated_count: modelIds.length };
    }
    return this.callApi('lora_batch_update_folder', modelIds, folderId);
  }

  async loraDeleteModel(modelId: string): Promise<{
    success: boolean;
    message?: string;
  }> {
    if (isDevelopment()) {
      console.log('[BridgeService] 开发环境模拟删除模型');
      return { success: true };
    }
    return this.callApi('lora_delete_model', modelId);
  }

  /**
   * 重命名 LoRA 模型
   */
  async loraRenameModel(modelId: string, newName: string): Promise<{
    success: boolean;
    message?: string;
    model?: LoraModel;
    old_path?: string;
    new_path?: string;
  }> {
    if (isDevelopment()) {
      console.log('[BridgeService] 开发环境模拟重命名模型');
      return { success: true };
    }
    return this.callApi('lora_rename_model', modelId, newName);
  }

  /**
   * 获取 LoRA 文件夹列表
   */
  async loraGetFolders(): Promise<{
    success: boolean;
    folders?: string[];
    message?: string;
  }> {
    if (isDevelopment()) {
      console.log('[BridgeService] 开发环境模拟获取文件夹列表');
      return { success: true, folders: [] };
    }
    return this.callApi('lora_get_folders');
  }

  /**
   * 获取 LoRA 分类及其模型数量
   */
  async loraGetCategoriesWithCount(): Promise<{
    success: boolean;
    categories?: Array<{ id: string; name: string; count: number }>;
    message?: string;
  }> {
    if (isDevelopment()) {
      console.log('[BridgeService] 开发环境模拟获取分类及数量');
      return { success: true, categories: [] };
    }
    return this.callApi('lora_get_categories_with_count');
  }

  /**
   * 获取 LoRA 文件夹结构
   */
  async loraGetFolderStructure(): Promise<{
    success: boolean;
    folders?: LoraFolderNode[];
    message?: string;
  }> {
    if (isDevelopment()) {
      console.log('[BridgeService] 开发环境模拟获取文件夹结构');
      return { success: true, folders: [] };
    }
    return this.callApi('lora_get_folder_structure');
  }

  /**
   * 同步 LoRA 文件夹结构
   */
  async loraSyncFolderStructure(): Promise<{
    success: boolean;
    message?: string;
  }> {
    if (isDevelopment()) {
      console.log('[BridgeService] 开发环境模拟同步文件夹结构');
      return { success: true };
    }
    return this.callApi('lora_sync_folder_structure');
  }

  /**
   * 创建 LoRA 文件夹
   */
  async loraCreateFolder(scanPathId: string, folderName: string, parentFolderId?: string): Promise<{
    success: boolean;
    message?: string;
    folder?: LoraFolderNode;
  }> {
    if (isDevelopment()) {
      console.log('[BridgeService] 开发环境模拟创建文件夹');
      return { success: true };
    }
    return this.callApi('lora_create_folder', scanPathId, folderName, parentFolderId);
  }

  /**
   * 重命名 LoRA 文件夹
   */
  async loraUpdateFolder(folderId: string, newName?: string, newParentId?: string): Promise<{
    success: boolean;
    message?: string;
    folder?: LoraFolderNode;
  }> {
    if (isDevelopment()) {
      console.log('[BridgeService] 开发环境模拟更新文件夹');
      return { success: true };
    }
    return this.callApi('lora_update_folder', folderId, newName, newParentId);
  }

  /**
   * 删除 LoRA 文件夹
   */
  async loraDeleteFolder(folderId: string): Promise<{
    success: boolean;
    message?: string;
  }> {
    if (isDevelopment()) {
      console.log('[BridgeService] 开发环境模拟删除文件夹');
      return { success: true };
    }
    return this.callApi('lora_delete_folder', folderId);
  }

  /**
   * 上传 LoRA 预览图
   */
  async loraUploadPreview(modelId: string, file: File | number[], filename?: string): Promise<{
    success: boolean;
    preview_url?: string;
    message?: string;
    filename?: string;
  }> {
    if (isDevelopment()) {
      console.log('[BridgeService] 开发环境模拟上传预览图');
      return { success: true, preview_url: 'dev://preview.jpg' };
    }
    
    let fileData: number[];
    let actualFilename: string;
    
    if (file instanceof File) {
      const arrayBuffer = await file.arrayBuffer();
      fileData = Array.from(new Uint8Array(arrayBuffer));
      actualFilename = file.name;
    } else {
      fileData = file;
      actualFilename = filename || 'preview.jpg';
    }
    
    return this.callApi('lora_upload_preview', modelId, fileData, actualFilename);
  }

  /**
   * 获取 LoRA 预览图列表
   */
  async loraGetPreviewList(modelId: string): Promise<{
    success: boolean;
    files?: string[];
    message?: string;
  }> {
    if (isDevelopment()) {
      console.log('[BridgeService] 开发环境模拟获取预览图列表');
      return { success: true, files: [] };
    }
    return this.callApi('lora_get_preview_list', modelId);
  }

  /**
   * 删除 LoRA 预览图
   */
  async loraDeletePreview(modelId: string, filename?: string): Promise<{
    success: boolean;
    message?: string;
  }> {
    if (isDevelopment()) {
      console.log('[BridgeService] 开发环境模拟删除预览图');
      return { success: true };
    }
    return this.callApi('lora_delete_preview', modelId, filename);
  }

  /**
   * 批量导出 LoRA 预览图到模型文件所在目录
   */
  async loraBatchExportPreviews(modelIds: string[]): Promise<{
    success: boolean;
    exported_count: number;
    skipped_count: number;
    failed_count: number;
    details?: Array<{ model_id: string; name?: string; status: string; target?: string; error?: string }>;
    message?: string;
  }> {
    if (isDevelopment()) {
      console.log('[BridgeService] 开发环境模拟批量导出预览图');
      return { success: true, exported_count: 0, skipped_count: 0, failed_count: 0, details: [] };
    }
    return this.callApi('lora_batch_export_previews', modelIds);
  }

  /**
   * 获取 Civitai 配置
   */
  async loraGetCivitaiConfig(): Promise<{
    success: boolean;
    config?: {
      api_key?: string;
      nsfw_enabled?: boolean;
      preview_download_limit?: number;
    };
    message?: string;
  }> {
    if (isDevelopment()) {
      console.log('[BridgeService] 开发环境模拟获取 Civitai 配置');
      return { success: true, config: { api_key: '', nsfw_enabled: false, preview_download_limit: 5 } };
    }
    return this.callApi('lora_get_civitai_config');
  }

  /**
   * 更新 Civitai 配置
   */
  async loraUpdateCivitaiConfig(updates: Record<string, any>): Promise<{
    success: boolean;
    message?: string;
  }> {
    if (isDevelopment()) {
      console.log('[BridgeService] 开发环境模拟更新 Civitai 配置');
      return { success: true };
    }
    return this.callApi('lora_update_civitai_config', updates);
  }

  /**
   * 设置 Civitai API Key
   */
  async loraSetCivitaiApiKey(apiKey: string): Promise<{
    success: boolean;
    message?: string;
  }> {
    if (isDevelopment()) {
      console.log('[BridgeService] 开发环境模拟设置 Civitai API Key');
      return { success: true };
    }
    return this.callApi('lora_set_civitai_api_key', apiKey);
  }

  // ==================== 插件市场 API ====================

  async marketplaceInstallPlugin(githubUrl: string, autoInstallDeps: boolean = true): Promise<{
    success: boolean;
    task_id?: string;
    message?: string;
  }> {
    if (isDevelopment()) {
      console.log('[BridgeService] 开发环境模拟安装插件:', githubUrl);
      return { success: true, task_id: 'mock-task-id' };
    }
    return this.callApi('marketplace_install_plugin', githubUrl, autoInstallDeps);
  }

  async marketplaceGetInstallProgress(taskId: string): Promise<{
    success: boolean;
    progress?: {
      status: string;
      stage?: string;
      progress: number;
      message: string;
    };
    error?: string;
  }> {
    if (isDevelopment()) {
      return { success: true, progress: { status: 'completed', progress: 100, message: '安装完成' } };
    }
    return this.callApi('marketplace_get_install_progress', taskId);
  }

  async marketplaceCancelInstallation(taskId: string): Promise<{
    success: boolean;
    message?: string;
  }> {
    if (isDevelopment()) {
      return { success: true };
    }
    return this.callApi('marketplace_cancel_installation', taskId);
  }

  async uploadWorkflowPreview(filename: string, imageData: string): Promise<{
    success: boolean;
    previewPath?: string;
    error?: string;
  }> {
    if (isDevelopment()) {
      return { success: true, previewPath: 'images/mock_preview.png' };
    }
    return this.callApi('upload_workflow_preview', filename, imageData);
  }

  async deleteWorkflowPreview(filename: string, previewIndex: number): Promise<{
    success: boolean;
    error?: string;
  }> {
    if (isDevelopment()) {
      return { success: true };
    }
    return this.callApi('delete_workflow_preview', filename, previewIndex);
  }

  async initializeNodeTypeMapAsync(): Promise<{
    success: boolean;
    message?: string;
    error?: string;
  }> {
    if (isDevelopment()) {
      return { success: true, message: '开发环境模拟' };
    }
    return this.callApi('initialize_node_type_map_async');
  }

  /**
   * 获取工作流数量
   */
  async workflowGetCount(): Promise<{
    success: boolean;
    count?: number;
    message?: string;
  }> {
    if (isDevelopment()) {
      console.log('[BridgeService] 开发环境模拟获取工作流数量');
      return { success: true, count: 0 };
    }
    return this.callApi<{ success: boolean; workflows?: unknown[] }>('get_workflows').then(result => ({
      success: result.success,
      count: result.workflows ? result.workflows.length : 0
    }));
  }

  /**
   * 获取提示词数量
   */
  async promptGetCount(): Promise<{
    success: boolean;
    count?: number;
    message?: string;
  }> {
    if (isDevelopment()) {
      console.log('[BridgeService] 开发环境模拟获取提示词数量');
      return { success: true, count: 0 };
    }
    return this.callApi<{ success: boolean; prompts?: unknown[] }>('prompt_get_all').then(result => ({
      success: result.success,
      count: result.prompts ? result.prompts.length : 0
    }));
  }
}

// Export singleton instance
export const bridgeService = new BridgeService();

