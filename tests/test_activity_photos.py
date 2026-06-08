from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from backend.app import app

client = TestClient(app)


def test_upload_activity_photo_and_list_photos() -> None:
    with TemporaryDirectory() as tmpdir:
        photos_dir = Path(tmpdir) / 'uploads' / 'photos'
        import backend.routes.activity_photos as activity_photos

        original_dir = activity_photos.PHOTOS_DIR
        activity_photos.PHOTOS_DIR = photos_dir
        try:
            response = client.post(
                '/api/v1/activities/12/photos',
                files={'photo': ('run.png', b'photo-bytes', 'image/png')},
            )
            assert response.status_code == 201
            payload = response.json()
            assert payload['message'] == '照片上传成功'
            assert payload['data']['activity_id'] == 12
            assert payload['data']['file_name'] == '12_run.png'

            response = client.get('/api/v1/activities/12/photos?page=1&page_size=10')
            assert response.status_code == 200
            payload = response.json()
            assert payload['message'] == '照片列表获取成功'
            assert payload['data']['total'] == 1
            assert payload['data']['items'][0]['file_name'] == '12_run.png'
        finally:
            activity_photos.PHOTOS_DIR = original_dir


def test_upload_activity_photo_rejects_invalid_extension() -> None:
    response = client.post(
        '/api/v1/activities/12/photos',
        files={'photo': ('run.txt', b'photo-bytes', 'text/plain')},
    )
    assert response.status_code == 422
    assert response.json() == {'detail': '仅支持 jpg、jpeg、png、gif、webp 格式'}


def test_list_activity_photos_rejects_invalid_activity_id() -> None:
    response = client.get('/api/v1/activities/0/photos')
    assert response.status_code == 422
    assert response.json() == {'detail': '活动ID必须大于 0'}
