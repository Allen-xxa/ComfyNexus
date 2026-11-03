/**
 * 资产库 Mock 数据
 */

export interface Asset {
  id: string
  filename: string
  filePath: string
  thumbnailPath: string | null
  type: 'image' | 'video'
  width: number
  height: number
  size: number
  createdAt: string
  hasWorkflow: boolean
  isFavorite: boolean
  categoryId: string | null
  prompt?: string
  negativePrompt?: string
  model?: string
  sampler?: string
  steps?: number
  cfg?: number
  seed?: number
  duration?: number
  nsfwScore?: number
  nsfwLabel?: string
  tags?: string[]
  description?: string
  previewBlurred?: boolean
  rating?: number
  /** 缩略图 URL（前端计算：thumbnailPath 或 filePath） */
  thumbnail?: string
  /** 原图 URL（前端计算：filePath） */
  url?: string
}

export interface AssetCategory {
  id: string
  name: string
  isSystem: boolean
  parentId: string | null
  sortOrder: number
  folderPath?: string
  children?: AssetCategory[]
}

export interface GallerySettings {
  libraryPath: string
  lastScanTime: string | null
  nsfwAutoClassify: boolean
  nsfwThreshold: number
  nsfwAutoBlur: boolean
}

export const mockAssetCategories: AssetCategory[] = [
  {
    id: 'all',
    name: '全部',
    isSystem: true,
    parentId: null,
    sortOrder: 0
  },
  {
    id: 'favorites',
    name: '收藏',
    isSystem: true,
    parentId: null,
    sortOrder: 1
  },
  {
    id: 'local-library',
    name: '本地生成库',
    isSystem: false,
    parentId: null,
    sortOrder: 2,
    folderPath: '本地生成库',
    children: [
      {
        id: 'local-2026-03',
        name: '2026-03 存档',
        isSystem: false,
        parentId: 'local-library',
        sortOrder: 0,
        folderPath: '本地生成库/2026-03 存档'
      },
      {
        id: 'local-test',
        name: '测试出图',
        isSystem: false,
        parentId: 'local-library',
        sortOrder: 1,
        folderPath: '本地生成库/测试出图'
      }
    ]
  },
  {
    id: 'reference-library',
    name: '参考资产库',
    isSystem: false,
    parentId: null,
    sortOrder: 3,
    folderPath: '参考资产库',
    children: [
      {
        id: 'reference-pose',
        name: '姿势参考',
        isSystem: false,
        parentId: 'reference-library',
        sortOrder: 0,
        folderPath: '参考资产库/姿势参考'
      }
    ]
  }
]

const generateMockAsset = (index: number): Asset => {
  const height = Math.floor(Math.random() * 300) + 400
  const hasWorkflow = Math.random() > 0.4
  const isFavorite = Math.random() > 0.7
  const categoryIds = ['local-2026-03', 'local-test', 'reference-pose']
  const categoryId = categoryIds[Math.floor(Math.random() * categoryIds.length)]
  
  const prompts = [
    'masterpiece, best quality, 1girl, highly detailed, dynamic lighting, cinematic composition, beautiful face, detailed eyes',
    'cyberpunk city, neon lights, rain, night scene, futuristic architecture, reflections on wet streets',
    'anime style, cute girl, colorful hair, fantasy background, detailed eyes, beautiful face',
    'portrait photography, professional lighting, natural skin texture, soft bokeh background',
    'landscape, mountains, lake, sunset, dramatic sky, photorealistic, 8k resolution',
    'fantasy castle, magical atmosphere, glowing particles, ethereal lighting, detailed architecture'
  ]
  
  const negativePrompts = [
    'lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality',
    'blurry, low quality, watermark, signature, text, logo, bad composition',
    'realistic, photo, 3d, low quality, bad anatomy, deformed'
  ]
  
  const models = ['SDXL_Base_1.0', 'SDXL_Turbo', 'SD_1.5', 'Flux.1', 'SD_2.1']
  const samplers = ['Euler a', 'DPM++ 2M Karras', 'DPM++ SDE Karras', 'DDIM', 'UniPC']
  
  return {
    id: `asset-${index + 1}`,
    filename: `output_${String(index + 1).padStart(4, '0')}.png`,
    filePath: `D:\\ComfyUI\\output\\output_${String(index + 1).padStart(4, '0')}.png`,
    thumbnailPath: null,
    type: 'image',
    width: 1024,
    height: height * 2,
    size: Math.floor(Math.random() * 3000000) + 1000000,
    createdAt: new Date(Date.now() - Math.random() * 30 * 24 * 60 * 60 * 1000).toISOString(),
    hasWorkflow,
    isFavorite,
    categoryId,
    prompt: prompts[Math.floor(Math.random() * prompts.length)],
    negativePrompt: negativePrompts[Math.floor(Math.random() * negativePrompts.length)],
    model: models[Math.floor(Math.random() * models.length)],
    sampler: samplers[Math.floor(Math.random() * samplers.length)],
    steps: Math.floor(Math.random() * 20) + 20,
    cfg: Math.round((Math.random() * 4 + 5) * 10) / 10,
    seed: Math.floor(Math.random() * 1000000000)
  }
}

export const mockAssets: Asset[] = Array.from({ length: 18 }, (_, i) => generateMockAsset(i))
