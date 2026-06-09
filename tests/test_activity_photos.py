from __future__ import annotations

from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient

import backend.database as database
from backend.app import app


def _client(tmp_path: Path) -> TestClient:
    database.init_db(tmp_path / 'test.db')
    return TestClient(app, raise_server_exceptions=False)


def test_上传活动照片_有效图片_返回201并保存元数据(tmp_path: Path) -> None:
    """上传合法图片时返回 201，并在响应中包含保存后的文件元数据。"""
    client = _client(tmp_path)
    payload = {'photo': ('run.jpg', BytesIO(b'fake-jpeg-bytes'), 'image/jpeg')}

    response = client.post('/api/v1/activities/1/photos', files=payload)

    assert response.status_code == 201
    assert response.json()['message'] == '照片上传成功'
    assert response.json()['data']['file_name'] == '1_run.jpg'


def test_上传活动照片_缺少文件_返回422(tmp_path: Path) -> None:
    """缺少必填文件参数时返回 422 校验错误。"""
    client = _client(tmp_path)

    response = client.post('/api/v1/activities/1/photos')

    assert response.status_code == 422
    assert response.json()['detail'] == 'Field required'


def test_上传活动照片_活动id为0_返回422(tmp_path: Path) -> None:
    """活动 ID 不大于 0 时拒绝上传并返回 422。"""
    client = _client(tmp_path)
    payload = {'photo': ('run.jpg', BytesIO(b'fake-jpeg-bytes'), 'image/jpeg')}

    response = client.post('/api/v1/activities/0/photos', files=payload)

    assert response.status_code == 422
    assert response.json()['detail'] == '活动ID必须大于 0'


def test_上传活动照片_空文件_返回422(tmp_path: Path) -> None:
    """上传空内容文件时返回 422。"""
    client = _client(tmp_path)
    payload = {'photo': ('run.jpg', BytesIO(b''), 'image/jpeg')}

    response = client.post('/api/v1/activities/1/photos', files=payload)

    assert response.status_code == 422
    assert response.json()['detail'] == '图片文件不能为空'


def test_上传活动照片_不支持扩展名_返回422(tmp_path: Path) -> None:
    """上传不支持的文件类型时返回 422。"""
    client = _client(tmp_path)
    payload = {'photo': ('run.txt', BytesIO(b'not-image'), 'text/plain')}

    response = client.post('/api/v1/activities/1/photos', files=payload)

    assert response.status_code == 422
    assert '仅支持' in response.json()['detail']


def test_查看活动照片_页码越界_返回空列表(tmp_path: Path) -> None:
    """查询超出已有图片范围的页码时返回空 items。"""
    client = _client(tmp_path)
    payload = {'photo': ('run.jpg', BytesIO(b'fake-jpeg-bytes'), 'image/jpeg')}
    client.post('/api/v1/activities/2/photos', files=payload)

    response = client.get('/api/v1/activities/2/photos', params={'page': 2, 'page_size': 10})

    assert response.status_code == 200
    assert response.json()['data']['items'] == []


def test_查看活动照片_有效分页_按文件名排序返回200(tmp_path: Path) -> None:
    """已上传多张照片时按文件名排序并返回分页结果。"""
    client = _client(tmp_path)
    for name in ['b.jpg', 'a.jpg']:
        client.post('/api/v1/activities/3/photos', files={'photo': (name, BytesIO(b'x'), 'image/jpeg')})

    response = client.get('/api/v1/activities/3/photos', params={'page': 1, 'page_size': 1})

    assert response.status_code == 200
    assert response.json()['data']['total'] == 2
    assert response.json()['data']['items'][0]['file_name'] == '3_a.jpg'


def test_查看活动照片_活动id为负数_返回422(tmp_path: Path) -> None:
    """查询活动照片时活动 ID 不合法会直接返回 422。"""
    client = _client(tmp_path)

    response = client.get('/api/v1/activities/-1/photos')

    assert response.status_code == 422
    assert response.json()['detail'] == '活动ID必须大于 0'
