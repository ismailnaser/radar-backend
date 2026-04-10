from datetime import timedelta

import os

from django.http import HttpRequest
from django.core.files.base import ContentFile
from django.utils import timezone
from rest_framework import serializers
from stores.models import StoreProfile

from .models import (
    Product,
    ProductGalleryImage,
    SponsoredAd,
    SponsoredAdGalleryImage,
    Subscription,
    Favorite,
    StoreFavorite,
    SubscriptionRenewalRequest,
)
from .media_utils import (
    MAX_GALLERY_IMAGES,
    product_gallery_urls,
    sponsored_ad_gallery_urls,
    product_has_any_visual,
    sync_product_cover_from_gallery,
    sync_sponsored_ad_cover_from_gallery,
)


def _absolute_media_url(request, relative_url):
    if not relative_url:
        return relative_url
    if not request or not isinstance(request, HttpRequest):
        return relative_url
    try:
        url = request.build_absolute_uri(relative_url)
        # Render / reverse proxy: تأكد من https لتفادي Mixed Content مع واجهة https
        xf_proto = (request.META.get('HTTP_X_FORWARDED_PROTO') or '').split(',')[0].strip().lower()
        if xf_proto == 'https' and url.startswith('http://'):
            url = 'https://' + url[len('http://') :]
        return url
    except Exception:
        return relative_url


def sponsored_ad_is_live(ad):
    if not ad:
        return False
    if ad.status != 'active' or not ad.approved_at:
        return False
    return ad.approved_at >= timezone.now() - timedelta(hours=24)


def assert_sponsored_ad_matches_product(ad, product):
    if ad.product_id is None:
        raise serializers.ValidationError(
            {'sponsored_ad': 'هذا الإعلان مستقل؛ يُرسل بدون منتج في الطلب.'}
        )
    if ad.product_id != product.id:
        raise serializers.ValidationError({'sponsored_ad': 'الإعلان لا يخص هذا المنتج.'})
    if not sponsored_ad_is_live(ad):
        raise serializers.ValidationError({'sponsored_ad': 'انتهت مدة الإعلان أو لم يعد نشطاً.'})


class ProductSerializer(serializers.ModelSerializer):
    store_name = serializers.ReadOnlyField(source='store.store_name')
    images = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Product
        fields = (
            'id',
            'store',
            'store_name',
            'name',
            'price',
            'description',
            'product_features',
            'image',
            'images',
            'is_archived',
            'created_at',
        )
        read_only_fields = ('store',)

    def get_images(self, obj):
        return product_gallery_urls(obj, self.context.get('request'))

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        imgs = product_gallery_urls(instance, request)
        data['images'] = imgs
        data['image'] = imgs[0] if imgs else (
            _absolute_media_url(request, instance.image.url) if instance.image else None
        )
        return data

    def create(self, validated_data):
        request = self.context.get('request')
        validated_data.pop('image', None)
        product = Product.objects.create(**validated_data)
        files = []
        if request:
            files = request.FILES.getlist('images')[:MAX_GALLERY_IMAGES]
            if not files and request.FILES.get('image'):
                files = [request.FILES['image']]
        if files:
            product.gallery_images.all().delete()
            for i, f in enumerate(files):
                ProductGalleryImage.objects.create(product=product, image=f, sort_order=i)
        sync_product_cover_from_gallery(product)
        return product

    def update(self, instance, validated_data):
        request = self.context.get('request')
        if request and request.FILES:
            validated_data.pop('image', None)
        instance = super().update(instance, validated_data)
        if request and request.FILES:
            files = request.FILES.getlist('images')[:MAX_GALLERY_IMAGES]
            if not files and request.FILES.get('image'):
                files = [request.FILES['image']]
            if files:
                instance.gallery_images.all().delete()
                for i, f in enumerate(files):
                    ProductGalleryImage.objects.create(product=instance, image=f, sort_order=i)
                sync_product_cover_from_gallery(instance)
        return instance

    def validate_product_features(self, value):
        if value is None:
            return []
        if isinstance(value, str):
            s = value.strip()
            if not s:
                return []
            try:
                value = __import__('json').loads(s)
            except Exception:
                raise serializers.ValidationError('صيغة غير صالحة. أرسل قائمة JSON.')
        if not isinstance(value, list):
            raise serializers.ValidationError('يجب أن تكون قائمة.')
        out = []
        for item in value:
            s = (item if isinstance(item, str) else str(item)).strip()
            if not s:
                continue
            if len(s) > 80:
                raise serializers.ValidationError('كل تفصيل بحد أقصى 80 حرفاً.')
            out.append(s)
        return out[:5]

class FavoriteSerializer(serializers.ModelSerializer):
    product_details = ProductSerializer(source='product', read_only=True)
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        required=False,
        allow_null=True,
    )
    sponsored_ad = serializers.PrimaryKeyRelatedField(
        queryset=SponsoredAd.objects.all(),
        required=False,
        allow_null=True,
    )
    standalone_ad_display = serializers.SerializerMethodField()

    class Meta:
        model = Favorite
        fields = (
            'id',
            'product',
            'product_details',
            'sponsored_ad',
            'standalone_ad_display',
            'created_at',
        )
        read_only_fields = ('user',)

    def get_standalone_ad_display(self, obj):
        if obj.product_id:
            return None
        sa = obj.sponsored_ad
        if not sa:
            return None
        request = self.context.get('request')
        imgs = sponsored_ad_gallery_urls(sa, request)
        img = imgs[0] if imgs else None
        return {
            'id': sa.id,
            'title': sa.title,
            'description': sa.description or '',
            'product_price': str(sa.product_price),
            'store': sa.store_id,
            'store_name': sa.store.store_name if sa.store_id else None,
            'image': img,
            'images': imgs,
        }

    def validate(self, attrs):
        sa = attrs.get('sponsored_ad')
        product = attrs.get('product')
        if sa is not None:
            if not sponsored_ad_is_live(sa):
                raise serializers.ValidationError(
                    {'sponsored_ad': 'انتهت مدة الإعلان أو لم يعد نشطاً.'}
                )
            if sa.product_id is None:
                if product is not None:
                    raise serializers.ValidationError(
                        {'product': 'إعلان مستقل — لا يُرسل منتجاً في الطلب.'}
                    )
                attrs['product'] = None
            else:
                if product is None:
                    raise serializers.ValidationError(
                        {'product': 'هذا الإعلان مرتبط بمنتج؛ أرسل معرّف المنتج.'}
                    )
                assert_sponsored_ad_matches_product(sa, product)
        else:
            if product is None:
                raise serializers.ValidationError(
                    {'product': 'أرسل منتجاً أو إعلاناً ممولاً صالحاً في الطلب.'}
                )
        return attrs


class StoreMiniForFavoriteSerializer(serializers.ModelSerializer):
    category_name = serializers.ReadOnlyField(source='category.name')

    class Meta:
        model = StoreProfile
        fields = ('id', 'store_name', 'category_name', 'logo', 'latitude', 'longitude', 'description')

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        if instance.logo:
            data['logo'] = _absolute_media_url(request, instance.logo.url)
        return data


class StoreFavoriteSerializer(serializers.ModelSerializer):
    store_details = StoreMiniForFavoriteSerializer(source='store', read_only=True)

    class Meta:
        model = StoreFavorite
        fields = ('id', 'store', 'store_details', 'created_at')
        read_only_fields = ('user',)

    def validate_store(self, value):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            if StoreFavorite.objects.filter(user=request.user, store=value).exists():
                raise serializers.ValidationError('هذا المتجر مضاف للمفضلة مسبقاً.')
        return value

class SponsoredAdSerializer(serializers.ModelSerializer):
    store_name = serializers.ReadOnlyField(source='store.store_name')
    payment_method_label = serializers.SerializerMethodField(read_only=True)
    product_details = ProductSerializer(source='product', read_only=True)
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        required=False,
        allow_null=True,
    )
    description = serializers.CharField(required=False, allow_blank=True, default='')
    image = serializers.ImageField(required=False, allow_null=True)
    images = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = SponsoredAd
        fields = (
            'id',
            'store',
            'store_name',
            'product',
            'product_details',
            'title',
            'description',
            'product_price',
            'payment_method',
            'payment_method_label',
            'image',
            'images',
            'payment_receipt_image',
            'status',
            'approved_at',
            'created_at',
        )
        read_only_fields = ('store', 'status', 'approved_at')

    def get_payment_method_label(self, obj):
        return obj.get_payment_method_display()

    def get_images(self, obj):
        return sponsored_ad_gallery_urls(obj, self.context.get('request'))

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        imgs = sponsored_ad_gallery_urls(instance, request)
        data['images'] = imgs
        data['image'] = imgs[0] if imgs else (
            _absolute_media_url(request, instance.image.url) if instance.image else None
        )
        if instance.payment_receipt_image:
            data['payment_receipt_image'] = _absolute_media_url(request, instance.payment_receipt_image.url)
        return data

    def create(self, validated_data):
        request = self.context.get("request")
        product = validated_data.get("product")

        gallery_files = []
        if request:
            gallery_files = request.FILES.getlist("images")[:MAX_GALLERY_IMAGES]
        if not gallery_files and request and request.FILES.get("image"):
            gallery_files = [request.FILES["image"]]

        pre_image = validated_data.get("image")
        if product and not pre_image and not gallery_files:
            first = ProductGalleryImage.objects.filter(product=product).order_by("sort_order", "id").first()
            if first:
                with first.image.open("rb") as f:
                    validated_data["image"] = ContentFile(f.read(), name=os.path.basename(first.image.name))
            elif product.image:
                with product.image.open("rb") as f:
                    validated_data["image"] = ContentFile(f.read(), name=os.path.basename(product.image.name))

        if gallery_files:
            validated_data.pop("image", None)

        ad = super().create(validated_data)

        if gallery_files:
            ad.gallery_images.all().delete()
            for i, f in enumerate(gallery_files):
                SponsoredAdGalleryImage.objects.create(sponsored_ad=ad, image=f, sort_order=i)
        elif product:
            pimgs = list(product.gallery_images.order_by("sort_order", "id")[:MAX_GALLERY_IMAGES])
            if pimgs:
                ad.gallery_images.all().delete()
                for i, gi in enumerate(pimgs):
                    with gi.image.open("rb") as src:
                        SponsoredAdGalleryImage.objects.create(
                            sponsored_ad=ad,
                            image=ContentFile(src.read(), name=os.path.basename(gi.image.name)),
                            sort_order=i,
                        )

        sync_sponsored_ad_cover_from_gallery(ad)
        return ad

    def validate(self, attrs):
        request = self.context.get("request")
        if request and request.method == "POST":
            receipt_file = attrs.get("payment_receipt_image") or request.FILES.get("payment_receipt_image")
            if not receipt_file:
                raise serializers.ValidationError({"payment_receipt_image": "يرجى رفع إشعار الدفع لطلب الإعلان."})
            price = attrs.get("product_price")
            if price is None:
                raise serializers.ValidationError({"product_price": "يرجى إدخال سعر المنتج المعروض في الإعلان."})
            if price <= 0:
                raise serializers.ValidationError({"product_price": "سعر المنتج يجب أن يكون أكبر من صفر."})
            pm = attrs.get("payment_method")
            valid_pm = {c[0] for c in SponsoredAd.PAYMENT_METHOD_CHOICES}
            if not pm or pm not in valid_pm:
                raise serializers.ValidationError(
                    {"payment_method": "يرجى اختيار طريقة الدفع (محفظة بال باي، بنك فلسطين، أو أخرى)."}
                )
            prod = attrs.get("product")
            store = StoreProfile.objects.get(user=request.user)
            if prod is not None:
                if prod.store_id != store.id:
                    raise serializers.ValidationError({"product": "المنتج يجب أن يكون من منتجات متجرك."})
            uploaded_image = attrs.get("image") or request.FILES.get("image")
            multi_images = bool(request.FILES.getlist("images")) if request else False
            has_uploaded_visual = bool(uploaded_image) or multi_images
            strict_description = prod is None or (prod is not None and product_has_any_visual(prod))
            desc_raw = (attrs.get("description") or "").strip()
            if strict_description and not desc_raw:
                raise serializers.ValidationError({"description": "يرجى إدخال تفاصيل الإعلان."})
            attrs["description"] = desc_raw
            if prod is None and not has_uploaded_visual:
                raise serializers.ValidationError({"image": "يرجى إرفاق صورة للإعلان."})
            if prod is not None and not product_has_any_visual(prod) and not has_uploaded_visual:
                attrs["image"] = None
            if prod is not None and product_has_any_visual(prod) and not has_uploaded_visual:
                attrs.pop("image", None)
        if request and request.method in ("PUT", "PATCH"):
            if "product_price" in attrs and attrs["product_price"] is not None:
                if attrs["product_price"] <= 0:
                    raise serializers.ValidationError({"product_price": "سعر المنتج يجب أن يكون أكبر من صفر."})
            if "payment_method" in attrs:
                valid_pm = {c[0] for c in SponsoredAd.PAYMENT_METHOD_CHOICES}
                if attrs["payment_method"] not in valid_pm:
                    raise serializers.ValidationError({"payment_method": "قيمة غير صالحة."})
            if "product" in attrs:
                store = StoreProfile.objects.get(user=request.user)
                p = attrs["product"]
                if p is not None and p.store_id != store.id:
                    raise serializers.ValidationError({"product": "المنتج يجب أن يكون من منتجات متجرك."})
        return attrs

class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = '__all__'
        read_only_fields = ('store', 'start_date')


class SubscriptionRenewalRequestSerializer(serializers.ModelSerializer):
    store_name = serializers.ReadOnlyField(source='store.store_name')
    decided_by_username = serializers.SerializerMethodField()

    class Meta:
        model = SubscriptionRenewalRequest
        fields = (
            'id',
            'store',
            'store_name',
            'receipt_image',
            'notes',
            'payment_method',
            'amount_ils',
            'status',
            'created_at',
            'decided_at',
            'decided_by_username',
        )
        read_only_fields = ('store', 'status', 'created_at', 'decided_at', 'decided_by_username', 'amount_ils')

    def get_decided_by_username(self, obj):
        if obj.decided_by_id and obj.decided_by:
            return obj.decided_by.username
        return None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        if instance.receipt_image:
            data['receipt_image'] = _absolute_media_url(request, instance.receipt_image.url)
        return data
