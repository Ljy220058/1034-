from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status

from ..models import ApiResponse

router = APIRouter(prefix='/api/v1/activities', tags=['activity-photos'])
PHOTOS_DIR = Path('uploads/photos')
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}


def _ensure_photos_dir() -> Path:
    """Ensure the photo upload directory exists.

    Returns:
        The resolved upload directory.
    """
    PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    return PHOTOS_DIR


def _safe_filename(filename: str) -> str:
    """Normalize an uploaded filename.

    Args:
        filename: Original file name.

    Returns:
        Sanitized file name.

    Raises:
        HTTPException: If the filename is invalid.
    """
    name = Path(filename).name.strip()
    if not name or name in {'.', '..'}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='图片文件名无效')
    return name


def _validate_extension(filename: str) -> None:
    """Validate the uploaded file extension.

    Args:
        filename: Sanitized file name.

    Raises:
        HTTPException: If the file type is unsupported.
    """
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='仅支持 jpg、jpeg、png、gif、webp 格式')


def _build_photo_item(activity_id: int, path: Path) -> dict[str, Any]:
    """Build a photo metadata item.

    Args:
        activity_id: Activity ID.
        path: Stored file path.

    Returns:
        A serializable photo metadata dictionary.
    """
    stat = path.stat()
    return {
        'activity_id': activity_id,
        'file_name': path.name,
        'file_path': str(path),
        'size_bytes': stat.st_size,
    }


@router.post('/{activity_id}/photos', response_model=ApiResponse, status_code=201)
async def upload_activity_photo(
    activity_id: int,
    photo: UploadFile = File(..., description='活动照片文件'),
) -> ApiResponse:
    """Upload a photo for an activity.

    Args:
        activity_id: Activity ID.
        photo: Uploaded image file.

    Returns:
        ApiResponse containing stored photo metadata.

    Raises:
        HTTPException: When the file is missing or invalid.
    """
    if activity_id <= 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='活动ID必须大于 0')
    filename = _safe_filename(photo.filename or '')
    _validate_extension(filename)
    upload_dir = _ensure_photos_dir()
    target_path = upload_dir / f'{activity_id}_{filename}'
    content = await photo.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='图片文件不能为空')
    target_path.write_bytes(content)
    return ApiResponse(data=_build_photo_item(activity_id, target_path), message='照片上传成功')


@router.get('/{activity_id}/photos', response_model=ApiResponse)
def list_activity_photos(
    activity_id: int,
    page: int = Query(default=1, ge=1, description='页码，从 1 开始'),
    page_size: int = Query(default=10, ge=1, le=100, description='每页条数'),
) -> ApiResponse:
    """List activity photos with pagination.

    Args:
        activity_id: Activity ID.
        page: Page number.
        page_size: Page size.

    Returns:
        Paginated list of stored photo metadata.
    """
    if activity_id <= 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='活动ID必须大于 0')
    upload_dir = _ensure_photos_dir()
    prefix = f'{activity_id}_'
    items = sorted((path for path in upload_dir.iterdir() if path.is_file() and path.name.startswith(prefix)), key=lambda item: item.name)
    start = (page - 1) * page_size
    end = start + page_size
    data = {
        'activity_id': activity_id,
        'page': page,
        'page_size': page_size,
        'total': len(items),
        'items': [_build_photo_item(activity_id, path) for path in items[start:end]],
    }
    return ApiResponse(data=data, message='照片列表获取成功')
