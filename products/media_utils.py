"""عناوين مطلقة لمعارض الصور (منتج / إعلان)."""
import os

from django.core.files.base import ContentFile
from django.http import HttpRequest

MAX_GALLERY_IMAGES = 5


def _abs_url(request, relative_url):
    if not relative_url:
        return None
    if not request or not isinstance(request, HttpRequest):
        return relative_url
    try:
        url = request.build_absolute_uri(relative_url)
        xf_proto = (request.META.get('HTTP_X_FORWARDED_PROTO') or '').split(',')[0].strip().lower()
        if xf_proto == 'https' and url.startswith('http://'):
            url = 'https://' + url[len('http://') :]
        return url
    except Exception:
        return relative_url


def product_gallery_urls(product, request):
    if not product:
        return []
    urls = []
    for gi in product.gallery_images.all().order_by('sort_order', 'id'):
        if gi.image:
            urls.append(_abs_url(request, gi.image.url))
    if not urls and product.image:
        urls.append(_abs_url(request, product.image.url))
    return urls


def sponsored_ad_gallery_urls(ad, request):
    if not ad:
        return []
    urls = []
    for gi in ad.gallery_images.all().order_by('sort_order', 'id'):
        if gi.image:
            urls.append(_abs_url(request, gi.image.url))
    if not urls and ad.image:
        urls.append(_abs_url(request, ad.image.url))
    return urls


def product_has_any_visual(product) -> bool:
    if not product:
        return False
    if product.image:
        return True
    return product.gallery_images.exists()


def sync_product_cover_from_gallery(product):
    """يضبط صورة الغلاف من أول عنصر في المعرض فقط إن وُجد معرض."""
    first = product.gallery_images.order_by('sort_order', 'id').first()
    if not first:
        return
    with first.image.open('rb') as src:
        data = src.read()
    name = os.path.basename(first.image.name)
    product.image.save(name, ContentFile(data), save=True)


def sync_sponsored_ad_cover_from_gallery(ad):
    """يضبط صورة الإعلان من المعرض إن وُجد؛ وإلا تُترك الحقل كما حفظته create()."""
    first = ad.gallery_images.order_by('sort_order', 'id').first()
    if not first:
        return
    with first.image.open('rb') as src:
        data = src.read()
    name = os.path.basename(first.image.name)
    ad.image.save(name, ContentFile(data), save=True)
