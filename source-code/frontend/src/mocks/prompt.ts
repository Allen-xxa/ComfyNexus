/**
 * 提示词管理 Mock 数据
 */

import type { Prompt, PromptCategory, FilterTag } from '@/stores/usePromptStore'

export type CategoryIconName = 
  | 'layers' 
  | 'star' 
  | 'folder' 
  | 'file-text'
  | 'user'
  | 'building'
  | 'sparkles'
  | 'image'

export type { Prompt, PromptCategory, FilterTag }

export const mockCategories: PromptCategory[] = [
  {
    id: 'all',
    name: '全部',
    icon: 'layers',
    parentId: null,
    sortOrder: 0,
    isSystem: true,
    children: []
  },
  {
    id: 'favorites',
    name: '收藏',
    icon: 'star',
    parentId: null,
    sortOrder: 1,
    isSystem: true,
    children: []
  },
  {
    id: 'portrait',
    name: '人像摄影',
    icon: 'user',
    parentId: null,
    sortOrder: 2,
    isSystem: false,
    children: [
      {
        id: 'portrait-realistic',
        name: '真实感人像',
        icon: 'file-text',
        parentId: 'portrait',
        sortOrder: 0,
        isSystem: false
      }
    ]
  },
  {
    id: 'architecture',
    name: '建筑与场景',
    icon: 'building',
    parentId: null,
    sortOrder: 3,
    isSystem: false,
    children: []
  },
  {
    id: 'cyberpunk',
    name: '赛博朋克',
    icon: 'sparkles',
    parentId: null,
    sortOrder: 4,
    isSystem: false,
    children: []
  },
  {
    id: 'anime',
    name: '动漫风格',
    icon: 'image',
    parentId: null,
    sortOrder: 5,
    isSystem: false,
    children: []
  }
]

export const mockFilterTags: FilterTag[] = [
  { id: 'all', name: '全部' },
  { id: 'cyberpunk', name: 'Cyberpunk' },
  { id: 'flux', name: 'Flux 专用' },
  { id: 'portrait', name: '人像' },
  { id: 'landscape', name: '风景' }
]

export const mockPrompts: Prompt[] = [
  {
    id: '1',
    name: '赛博霓虹大场景',
    positivePrompt: 'masterpiece, (cyberpunk city:1.2), neon lights, futuristic architecture, rain, wet streets, reflections, night scene, high contrast, vibrant colors, detailed environment',
    negativePrompt: '(worst quality:1.4), lowres, blurry, distorted, deformed, ugly, bad anatomy, bad proportions, duplicate, watermark, signature',
    previewImage: 'https://placehold.co/240x320/1a1a2e/00d4ff?text=Cyberpunk',
    remark: '强烈建议配合特定 LoRA 使用，雨天水面倒影细节极佳。',
    categoryId: 'cyberpunk',
    tags: ['Cyberpunk', '城市', '夜景'],
    createdAt: '2024-01-15T10:00:00Z',
    updatedAt: '2024-01-20T14:30:00Z',
    isFavorite: true,
    params: {
      model: 'sdxl/sd_xl_base_1.0.safetensors',
      sampler: 'dpmpp_2m',
      scheduler: 'karras',
      steps: 30,
      cfg: 7,
      seed: 1234567890,
      width: 1024,
      height: 1536,
      duration: null,
      assetType: 'image',
      sourceAssetId: ''
    }
  },
  {
    id: '2',
    name: '富士胶片质感人像',
    positivePrompt: 'RAW photo, film grain, Fujifilm XT4, 85mm lens, natural lighting, soft bokeh, skin texture, professional portrait, warm tones',
    negativePrompt: '(deformed pupils:1.4), cgi, plastic skin, overexposed, underexposed, noise, grainy, blurry',
    previewImage: 'https://placehold.co/240x320/2d2d2d/ffd700?text=Portrait',
    remark: '适合半身特写，自带高级胶片颗粒感。',
    categoryId: 'portrait-realistic',
    tags: ['Portrait', '胶片', '人像'],
    createdAt: '2024-01-16T09:00:00Z',
    updatedAt: '2024-01-18T16:20:00Z',
    isFavorite: false,
    params: {
      model: 'sd15/realisticVision_v60.safetensors',
      sampler: 'euler_a',
      scheduler: 'normal',
      steps: 28,
      cfg: 6.5,
      seed: 987654321,
      width: 768,
      height: 1152,
      duration: null,
      assetType: 'image',
      sourceAssetId: ''
    }
  },
  {
    id: '3',
    name: 'Flux 极简产品渲染',
    positivePrompt: 'product photography, minimalist, clean background, studio lighting, high detail, commercial quality, professional',
    negativePrompt: 'amateur, low quality, blurry, watermark, text, logo',
    previewImage: 'https://placehold.co/240x320/f5f5f5/333333?text=Product',
    remark: '专为 Flux 模型优化，适合产品展示。',
    categoryId: 'architecture',
    tags: ['Flux 专用', '产品', '极简'],
    createdAt: '2024-01-17T11:00:00Z',
    updatedAt: '2024-01-17T11:00:00Z',
    isFavorite: false,
    params: {
      model: 'flux/flux1-dev.safetensors',
      sampler: 'euler',
      scheduler: 'simple',
      steps: 20,
      cfg: 1,
      seed: 42,
      width: 1344,
      height: 768,
      duration: null,
      assetType: 'image',
      sourceAssetId: ''
    }
  },
  {
    id: '4',
    name: '二次元角色立绘',
    positivePrompt: 'anime style, character design, full body, clean lines, vibrant colors, detailed eyes, beautiful face',
    negativePrompt: 'realistic, photo, 3d, low quality, bad anatomy',
    previewImage: 'https://placehold.co/240x320/ff6b9d/ffffff?text=Anime',
    remark: '适合动漫风格角色生成。',
    categoryId: 'anime',
    tags: ['动漫', '角色', '二次元'],
    createdAt: '2024-01-18T14:00:00Z',
    updatedAt: '2024-01-18T14:00:00Z',
    isFavorite: true,
    params: {
      model: 'illustrious/illustriousXL_v01.safetensors',
      sampler: 'dpmpp_2m_sde',
      scheduler: 'karras',
      steps: 32,
      cfg: 5.5,
      seed: 20240118,
      width: 832,
      height: 1216,
      duration: null,
      assetType: 'image',
      sourceAssetId: ''
    }
  }
]
