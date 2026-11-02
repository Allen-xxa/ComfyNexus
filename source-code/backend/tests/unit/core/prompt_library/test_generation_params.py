"""提示词库生成参数测试

覆盖「资产库转入提示词库」所依赖的参数提取与序列化行为：
参数只在请求里出现过才落库、越界丢弃、非数字拒绝、旧数据可读。
"""

import pytest

from backend.src.core.prompt_library.models import Prompt
from backend.src.core.prompt_library.service import (
    _default_generation_params,
    _extract_generation_params,
)

PARAM_FIELDS = {
    'model', 'sampler', 'scheduler', 'steps', 'cfg', 'seed',
    'width', 'height', 'duration', 'asset_type', 'source_asset_id',
}


class TestExtractGenerationParams:
    def test_只保留请求里出现过的字段(self):
        params = _extract_generation_params({'model': 'flux1-dev.safetensors'})

        assert params == {'model': 'flux1-dev.safetensors'}

    def test_完整参数全部保留(self):
        data = {
            'model': 'flux1-dev.safetensors',
            'sampler': 'euler',
            'scheduler': 'simple',
            'steps': 20,
            'cfg': 1.0,
            'seed': 42,
            'width': 1344,
            'height': 768,
            'duration': None,
            'asset_type': 'image',
            'source_asset_id': 'asset-1',
        }

        params = _extract_generation_params(data)

        assert set(params) == PARAM_FIELDS
        assert params['steps'] == 20
        assert params['cfg'] == 1.0

    def test_字符串数字会被转换(self):
        params = _extract_generation_params({'steps': '28', 'cfg': '6.5'})

        assert params['steps'] == 28
        assert params['cfg'] == 6.5

    def test_浮点步数取整(self):
        params = _extract_generation_params({'steps': 28.9})

        assert params['steps'] == 28

    def test_空值写成默认值(self):
        params = _extract_generation_params({'steps': None, 'model': None, 'cfg': ''})

        assert params['steps'] is None
        assert params['cfg'] is None
        assert params['model'] == ''

    def test_超出范围丢弃为None(self):
        params = _extract_generation_params({'steps': 0, 'cfg': 999.0, 'width': -1})

        assert params['steps'] is None
        assert params['cfg'] is None
        assert params['width'] is None

    def test_种子可到int64上限(self):
        params = _extract_generation_params({'seed': 2 ** 63 - 1})

        assert params['seed'] == 2 ** 63 - 1

    def test_非数字抛ValueError(self):
        with pytest.raises(ValueError):
            _extract_generation_params({'steps': 'abc'})

    def test_cfg保留四位小数(self):
        params = _extract_generation_params({'cfg': 6.123456789})

        assert params['cfg'] == 6.1235

    def test_空字典返回空(self):
        assert _extract_generation_params({}) == {}


class TestDefaultGenerationParams:
    def test_默认值覆盖所有字段(self):
        params = _default_generation_params()

        assert set(params) == PARAM_FIELDS
        assert params['steps'] is None
        assert params['model'] == ''
        assert params['source_asset_id'] == ''


class TestPromptSerialization:
    def test_参数字段可往返(self):
        prompt = Prompt(
            id='p1',
            name='配方',
            positive_prompt='a cat',
            category_id='c1',
            model='flux1-dev.safetensors',
            sampler='euler',
            scheduler='simple',
            steps=20,
            cfg=1.0,
            seed=42,
            width=1344,
            height=768,
            duration=5.0,
            asset_type='video',
            source_asset_id='asset-1',
        )

        restored = Prompt.from_dict(prompt.to_dict())

        assert restored == prompt

    def test_旧数据缺少参数字段仍可读取(self):
        legacy = {
            'id': 'p2',
            'name': '旧配方',
            'positive_prompt': 'old',
            'category_id': 'c1',
            'tags': [],
        }

        restored = Prompt.from_dict(legacy)

        assert restored.steps is None
        assert restored.model == ''
        assert restored.source_asset_id == ''

    def test_旧数据参数为null时字符串字段回落空串(self):
        restored = Prompt.from_dict({'id': 'p3', 'name': 'x', 'positive_prompt': '',
                                     'category_id': 'c1', 'model': None})

        assert restored.model == ''
