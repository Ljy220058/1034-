from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from backend.app import app

client = TestClient(app)


def test_upload_activity_photo_正常文件_返回201并保存元数据() -> None:
    """上传合法图片时返回 201，并写入活动照片元数据。"""
    with TemporaryDirectory() as tmpdir:
        import backend.routes.activity_photos as activity_photos

        original_dir = activity_photos.PHOTOS_DIR
        activity_photos.PHOTOS_DIR = Path(tmpdir) / 'uploads' / 'photos'
        try:
            response = client.post('/api/v1/activities/12/photos', files={'photo': ('run.png', b'photo-bytes', 'image/png')})
            assert response.status_code == 201
            data = response.json()['data']
            assert data['activity_id'] == 12 and data['file_name'] == '12_run.png'
        finally:
            activity_photos.PHOTOS_DIR = original_dir


def test_upload_activity_photo_活动id非法_返回422() -> None:
    """活动 ID 小于等于 0 时拒绝上传。"""
    response = client.post('/api/v1/activities/0/photos', files={'photo': ('run.png', b'photo-bytes', 'image/png')})
    assert response.status_code == 422
    assert response.json() == {'detail': '活动ID必须大于 0'}


def test_upload_activity_photo_空文件名_返回422() -> None:
    """空文件名在表单解析阶段会被 FastAPI 拒绝。"""
    response = client.post('/api/v1/activities/12/photos', files={'photo': ('', b'photo-bytes', 'image/png')})
    assert response.status_code == 422
    assert 'Expected UploadFile' in response.json()['detail']


def test_upload_activity_photo_不支持的扩展名_返回422() -> None:
    """非图片扩展名会被拒绝。"""
    response = client.post('/api/v1/activities/12/photos', files={'photo': ('run.txt', b'photo-bytes', 'text/plain')})
    assert response.status_code == 422
    assert response.json() == {'detail': '仅支持 jpg、jpeg、png、gif、webp 格式'}


def test_upload_activity_photo_空内容_返回422() -> None:
    """空文件内容不会被保存。"""
    response = client.post('/api/v1/activities/12/photos', files={'photo': ('run.png', b'', 'image/png')})
    assert response.status_code == 422
    assert response.json() == {'detail': '图片文件不能为空'}


def test_list_activity_photos_分页参数越界_返回422() -> None:
    """页码必须大于等于 1，越界时返回 422。"""
    response = client.get('/api/v1/activities/12/photos?page=0&page_size=10')
    assert response.status_code == 422
    assert response.json()['detail'] == '输入校验失败'


def test_list_activity_photos_有文件时返回分页列表() -> None:
    """列表接口返回已上传照片和总数。"""
    with TemporaryDirectory() as tmpdir:
        import backend.routes.activity_photos as activity_photos

        original_dir = activity_photos.PHOTOS_DIR
        photos_dir = Path(tmpdir) / 'uploads' / 'photos'
        activity_photos.PHOTOS_DIR = photos_dir
        try:
            photos_dir.mkdir(parents=True, exist_ok=True)
            (photos_dir / '12_a.png').write_bytes(b'a')
            (photos_dir / '12_b.png').write_bytes(b'bb')
            response = client.get('/api/v1/activities/12/photos?page=1&page_size=1')
            assert response.status_code == 200
            data = response.json()['data']
            assert data['total'] == 2 and data['items'][0]['file_name'] == '12_a.png'
        finally:
            activity_photos.PHOTOS_DIR = original_dir
