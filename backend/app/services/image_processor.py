import base64
import io
from typing import Tuple
from PIL import Image
from fastapi import UploadFile, HTTPException


class ImageProcessor:
    """处理用户上传的图片，校验、压缩并转为 base64。"""

    SUPPORTED_FORMATS = {"image/jpeg", "image/png", "image/jpg", "image/webp"}
    MAX_SIZE = (1920, 1920)
    MAX_PIXELS = 1920 * 1920  # 约 370 万像素，防止解压炸弹
    JPEG_QUALITY = 85
    MAX_FILE_SIZE_MB = 10

    @classmethod
    async def process(cls, file: UploadFile) -> Tuple[str, str]:
        if file.content_type not in cls.SUPPORTED_FORMATS:
            raise HTTPException(
                status_code=400,
                detail="Unsupported image format. Allowed: JPEG, PNG, WebP."
            )

        content = await file.read()
        if len(content) > cls.MAX_FILE_SIZE_MB * 1024 * 1024:
            raise HTTPException(
                status_code=400,
                detail=f"Image too large. Max size: {cls.MAX_FILE_SIZE_MB}MB."
            )

        try:
            img = Image.open(io.BytesIO(content))

            # 限制解码后的像素数量，防止解压炸弹
            width, height = img.size
            if width * height > cls.MAX_PIXELS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Image resolution too large. Max pixels: {cls.MAX_PIXELS}."
                )

            img = cls._fix_orientation(img)
            img.thumbnail(cls.MAX_SIZE, Image.LANCZOS)

            # 统一转换为 RGB，避免 CMYK 等模式问题
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGBA")
            elif img.mode != "RGB":
                img = img.convert("RGB")

            buffer = io.BytesIO()
            if file.content_type == "image/png":
                img.save(buffer, format="PNG")
                mime_type = "image/png"
            else:
                # JPEG / WebP 统一用 JPEG 输出，压缩体积
                if img.mode == "RGBA":
                    img = img.convert("RGB")
                img.save(buffer, format="JPEG", quality=cls.JPEG_QUALITY, optimize=True)
                mime_type = "image/jpeg"

            base64_str = base64.b64encode(buffer.getvalue()).decode("utf-8")
            return base64_str, mime_type
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=400, detail="Failed to process image. Please upload a valid image file.")

    @staticmethod
    def _fix_orientation(img: Image.Image) -> Image.Image:
        """根据 EXIF Orientation 旋转图片。"""
        try:
            exif = img._getexif()
            if exif is None:
                return img
            orientation = exif.get(274)
            rotations = {
                3: Image.ROTATE_180,
                6: Image.ROTATE_270,
                8: Image.ROTATE_90,
            }
            if orientation in rotations:
                img = img.transpose(rotations[orientation])
        except Exception:
            pass
        return img
