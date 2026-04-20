"""تحويل رفعات الصور إلى WebP (Pillow) قبل الحفظ في التخزين."""

from __future__ import annotations

import os
from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

DEFAULT_WEBP_QUALITY = 80
DEFAULT_MAX_WIDTH = 800


def image_file_to_webp_content(
    django_file,
    *,
    quality: int = DEFAULT_WEBP_QUALITY,
    max_width: int = DEFAULT_MAX_WIDTH,
) -> ContentFile | None:
    """
    يقرأ ملف صورة (UploadedFile / مفتوح من FieldFile) ويعيد ContentFile باسم ينتهي بـ .webp
    """
    if django_file is None:
        return None
    try:
        django_file.open('rb')
        try:
            raw = django_file.read()
        finally:
            django_file.close()
    except Exception:
        return None
    if not raw:
        return None

    try:
        buf = BytesIO(raw)
        img = Image.open(buf)
        img.load()
        if getattr(img, 'n_frames', 1) > 1:
            img.seek(0)
            img = img.copy()
        else:
            img = ImageOps.exif_transpose(img)
        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
            img = img.convert('RGBA')
        elif img.mode == 'P':
            img = img.convert('RGB')
        elif img.mode not in ('RGB', 'RGBA'):
            img = img.convert('RGB')

        if isinstance(max_width, int) and max_width > 0 and img.width > max_width:
            new_height = max(1, int(round((img.height * max_width) / img.width)))
            resample = getattr(Image, "Resampling", Image).LANCZOS
            img = img.resize((max_width, new_height), resample)

        out = BytesIO()
        save_kw = dict(format='WEBP', quality=quality, method=6)
        if img.mode == 'RGBA':
            save_kw['lossless'] = False
        img.save(out, **save_kw)
        out.seek(0)
    except (UnidentifiedImageError, OSError, ValueError):
        return None

    old_name = getattr(django_file, 'name', None) or 'image'
    base = os.path.splitext(os.path.basename(str(old_name)))[0] or 'image'
    new_name = f'{base}.webp'
    return ContentFile(out.read(), name=new_name)


def assign_webp_if_new_upload(instance, field_name: str, *, quality: int = DEFAULT_WEBP_QUALITY) -> None:
    """
    إذا وُجدت رفعة جديدة (غير محفوظة بعد) على ImageField، تستبدل بملف WebP.
    """
    fieldfile = getattr(instance, field_name, None)
    if fieldfile is None:
        return
    if getattr(fieldfile, '_committed', True):
        return
    try:
        inner = fieldfile.file
    except Exception:
        return
    if inner is None:
        return
    new_file = image_file_to_webp_content(inner, quality=quality)
    if new_file is not None:
        setattr(instance, field_name, new_file)


class WebPImageFieldsMixin:
    """
    عرّف على الموديل:
      webp_image_fields = ('image', 'logo')
    ثم أضف المixin قبل Model في الوراثة.
    """

    webp_image_fields: tuple[str, ...] = ()
    webp_quality: int = DEFAULT_WEBP_QUALITY

    def save(self, *args, **kwargs):
        q = getattr(self, 'webp_quality', DEFAULT_WEBP_QUALITY)
        for name in getattr(self, 'webp_image_fields', ()) or ():
            assign_webp_if_new_upload(self, name, quality=q)
        super().save(*args, **kwargs)
