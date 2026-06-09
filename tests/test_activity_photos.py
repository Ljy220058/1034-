from __future__ import annotations

from io import BytesIO

import pytest
from fastapi.testclient import TestClient

from backend.app import app


@pytest.fixture()
def client() -> TestClient:
    """提供独立的 FastAPI 测试客户端。"""
    return TestClient(app)


def test_上传活动照片_有效图片_返回201(client: TestClient):
    """有效图片上传后返回 201，并写入照片元数据。"""
    # Arrange
    files = {'photo': ('run.jpg', BytesIO(b'jpeg-bytes'), 'image/jpeg')}

    # Act
    response = client.post('/api/v1/activities/1/photos', files=files)

    # Assert
    assert response.status_code == 201
    payload = response.json()
    assert payload['message'] == '照片上传成功'
    assert payload['data']['activity_id'] == 1


def test_上传活动照片_未认证访问_仍可上传成功(client: TestClient):
    """该上传接口当前不要求认证，匿名请求也应成功。"""
    # Arrange
    files = {'photo': ('run.jpg', BytesIO(b'jpeg-bytes'), 'image/jpeg')}

    # Act
    response = client.post('/api/v1/activities/1/photos', files=files)

    # Assert
    assert response.status_code == 201


def test_上传活动照片_id为0_返回422(client: TestClient):
    """活动 ID 小于等于 0 时返回 422。"""
    # Arrange
    files = {'photo': ('run.jpg', BytesIO(b'jpeg-bytes'), 'image/jpeg')}

    # Act
    response = client.post('/api/v1/activities/0/photos', files=files)

    # Assert
    assert response.status_code == 422
    assert response.json()['detail'] == '活动ID必须大于 0'


def test_上传活动照片_缺少photo字段_返回422(client: TestClient):
    """缺少必填文件字段时返回 422。"""
    # Arrange
    files = {}

    # Act
    response = client.post('/api/v1/activities/1/photos', files=files)

    # Assert
    assert response.status_code == 422


def test_上传活动照片_扩展名非法_返回422(client: TestClient):
    """不支持的文件后缀会被拒绝。"""
    # Arrange
    files = {'photo': ('run.txt', BytesIO(b'text'), 'text/plain')}

    # Act
    response = client.post('/api/v1/activities/1/photos', files=files)

    # Assert
    assert response.status_code == 422
    assert response.json()['detail'] == '仅支持 jpg、jpeg、png、gif、webp 格式'


def test_上传活动照片_空文件内容_返回422(client: TestClient):
    """空文件内容会被拒绝。"""
    # Arrange
    files = {'photo': ('run.jpg', BytesIO(b''), 'image/jpeg')}

    # Act
    response = client.post('/api/v1/activities/1/photos', files=files)

    # Assert
    assert response.status_code == 422
    assert response.json()['detail'] == '图片文件不能为空'
