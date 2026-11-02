/**
 * 路由配置
 */

import { createBrowserRouter, Navigate } from 'react-router-dom'
import { MainLayout } from '@/components/layout/MainLayout'
import { lazy } from 'react'

// 懒加载所有页面组件
// 使用新开发的首页组件（包含 SystemMonitorGrid、FolderShortcutBar 等）
const HomePage = lazy(() => import('@/components/home/HomePage'))
const WorkspacePage = lazy(() => import('@/pages/WorkspacePage'))
const TerminalPage = lazy(() => import('@/pages/TerminalPage'))
const VersionManagePage = lazy(() => import('@/pages/VersionManagePage'))
const PluginManagePage = lazy(() => import('@/pages/PluginManagePage'))
const PluginMarketPage = lazy(() => import('@/pages/PluginMarketPage'))
const DependencyManagePage = lazy(() => import('@/pages/DependencyManagePage'))
const LoraManagePage = lazy(() => import('@/pages/LoraManagePage'))
const AIAssistantPage = lazy(() => import('@/pages/AIAssistantPage'))
const WorkflowManagePage = lazy(() => import('@/pages/WorkflowManagePage'))
const PromptManagePage = lazy(() => import('@/pages/PromptManagePage'))
const AssetLibraryPage = lazy(() => import('@/pages/AssetLibraryPage'))
const MonitorCenterPage = lazy(() => import('@/pages/MonitorCenterPage'))
const EnvManagePage = lazy(() => import('@/pages/EnvManagePage'))
const SystemSettingsPage = lazy(() => import('@/pages/SystemSettingsPage'))
const AboutPage = lazy(() => import('@/pages/AboutPage'))

/**
 * 路由配置
 */
export const router = createBrowserRouter([
  {
    path: '/',
    element: <MainLayout />,
    children: [
      {
        index: true,
        element: <HomePage />,
      },
      {
        path: 'workspace',
        element: <WorkspacePage />,
      },
      {
        path: 'terminal',
        element: <TerminalPage />,
      },
      {
        path: 'version',
        element: <VersionManagePage />,
      },
      {
        path: 'plugin',
        element: <PluginManagePage />,
      },
      {
        path: 'plugin-market',
        element: <PluginMarketPage />,
      },
      {
        path: 'dependency',
        element: <DependencyManagePage />,
      },
      {
        path: 'model',
        element: <LoraManagePage />,
      },
      {
        path: 'ai-assistant',
        element: <AIAssistantPage />,
      },
      {
        path: 'workflow',
        element: <WorkflowManagePage />,
      },
      {
        path: 'prompt',
        element: <PromptManagePage />,
      },
      {
        path: 'gallery',
        element: <AssetLibraryPage />,
      },
      {
        path: 'monitor',
        element: <MonitorCenterPage />,
      },
      {
        path: 'env',
        element: <EnvManagePage />,
      },
      {
        path: 'settings',
        element: <SystemSettingsPage />,
      },
      {
        path: 'about',
        element: <AboutPage />,
      },
      {
        path: '*',
        element: <Navigate to="/" replace />,
      },
    ],
  },
])
