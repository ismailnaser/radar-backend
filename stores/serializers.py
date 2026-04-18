import json

from rest_framework import serializers
from datetime import timedelta

from django.utils import timezone

from django.core.exceptions import ObjectDoesNotExist

from django.db.models import Avg, Count

from .models import (
    Category,
    CommunityServiceCategory,
    CommunityServicePoint,
    Service,
    StoreProfile,
    StoreRating,
)
from products.models import Product, SponsoredAd
from products.media_utils import product_gallery_urls, sponsored_ad_gallery_urls
from .store_hours import is_store_open_now


_ARABIC_INDIC = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')
_PERSIAN_INDIC = str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789')


def _normalize_whatsapp_digits(raw: str) -> str:
    """أرقام لاتينية فقط؛ دعم الأرقام العربية/الفارسية؛ تحويل شائع 05… محلي إلى 970…"""
    if not raw:
        return ''
    s = str(raw).translate(_ARABIC_INDIC).translate(_PERSIAN_INDIC)
    digits = ''.join(c for c in s if c.isdigit())
    if not digits:
        return ''
    if len(digits) == 10 and digits[0] == '0' and digits[1] == '5':
        digits = '970' + digits[1:]
    elif len(digits) == 9 and digits[0] == '5':
        digits = '970' + digits
    return digits


def _contact_whatsapp_url(raw):
    digits = _normalize_whatsapp_digits(raw or '')
    if len(digits) < 8:
        return None
    return f'https://wa.me/{digits}'


def _safe_build_absolute_uri(request, relative_url):
    """يمنع سقوط التسلسل عند DisallowedHost أو أي خطأ في build_absolute_uri."""
    if not request or not relative_url:
        return relative_url
    try:
        return request.build_absolute_uri(relative_url)
    except Exception:
        return relative_url


def _sync_merchant_profile_complete_from_store(store):
    """يحدّث علم اكتمال ملف التاجر وفق بيانات أساسية للمتجر."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    u = getattr(store, 'user', None)
    if u is None or getattr(u, 'user_type', None) != 'merchant':
        return
    addr = (store.location_address or '').strip()
    name = (store.store_name or '').strip()
    has_cat = bool(store.category_id)
    try:
        if not has_cat and store.categories.exists():
            has_cat = True
    except Exception:
        pass
    ok = bool(name and len(addr) >= 5 and has_cat)
    if u.merchant_profile_complete != ok:
        u.merchant_profile_complete = ok
        u.save(update_fields=['merchant_profile_complete'])


def store_rating_summary(instance):
    """متوسط بعدد التقييمات؛ يدعم queryset مُعلَّم بـ rating_avg و rating_n."""
    if getattr(instance, 'rating_avg', None) is not None:
        return (round(float(instance.rating_avg), 2), int(getattr(instance, 'rating_n', 0) or 0))
    agg = StoreRating.objects.filter(store=instance).aggregate(avg=Avg('stars'), n=Count('id'))
    avg = agg['avg']
    return (round(float(avg), 2) if avg is not None else None, int(agg['n'] or 0))


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        if instance.image:
            data['image'] = _safe_build_absolute_uri(request, instance.image.url) if request else instance.image.url
        return data

class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = '__all__'

class StoreProfileSerializer(serializers.ModelSerializer):
    category_name = serializers.ReadOnlyField(source='category.name')
    category_image = serializers.SerializerMethodField()
    categories = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Category.objects.all(),
        required=False,
    )
    categories_names = serializers.SerializerMethodField()
    merchant_profile_complete = serializers.SerializerMethodField()
    rating_average = serializers.SerializerMethodField()
    rating_count = serializers.SerializerMethodField()
    contact_whatsapp_url = serializers.SerializerMethodField()
    is_open_now = serializers.SerializerMethodField()

    class Meta:
        model = StoreProfile
        fields = (
            'id', 'store_name', 'description', 'logo', 'category', 'category_name',
            'categories', 'categories_names',
            'merchant_profile_complete',
            'category_image', 'latitude', 'longitude', 'location_address',
            'rating_average', 'rating_count',
            'contact_whatsapp', 'contact_whatsapp_url',
            'store_features', 'business_hours_note', 'business_hours_weekly', 'store_timezone',
            'is_open_now',
        )

    def get_category_image(self, obj):
        cat = obj.category
        if not cat or not cat.image:
            return None
        request = self.context.get('request')
        url = cat.image.url
        return _safe_build_absolute_uri(request, url) if request else url

    def get_rating_average(self, obj):
        avg, _ = store_rating_summary(obj)
        return avg

    def get_rating_count(self, obj):
        _, n = store_rating_summary(obj)
        return n

    def get_categories_names(self, obj):
        try:
            return [c.name for c in obj.categories.all()]
        except Exception:
            return []

    def get_merchant_profile_complete(self, obj):
        u = getattr(obj, 'user', None)
        return bool(getattr(u, 'merchant_profile_complete', False))

    def get_contact_whatsapp_url(self, obj):
        return _contact_whatsapp_url(getattr(obj, 'contact_whatsapp', '') or '')

    def get_is_open_now(self, obj):
        return is_store_open_now(
            getattr(obj, 'business_hours_weekly', None) or {},
            getattr(obj, 'store_timezone', None) or 'Asia/Gaza',
        )

    def validate_store_features(self, value):
        if value is None:
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError('المميزات يجب أن تكون قائمة نصوص.')
        out = []
        for item in value:
            s = (item if isinstance(item, str) else str(item)).strip()
            if not s:
                continue
            if len(s) > 80:
                raise serializers.ValidationError('كل ميزة بحد أقصى 80 حرفاً.')
            out.append(s)
        if len(out) > 10:
            raise serializers.ValidationError('بحد أقصى 10 مميزات.')
        return out

    def validate_business_hours_weekly(self, value):
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError('جدول المواعيد يجب أن يكون كائناً.')
        normalized = {}
        for i in range(7):
            k = str(i)
            raw = value.get(k)
            if raw is None:
                raw = value.get(i)
            if raw is None:
                continue
            if not isinstance(raw, list):
                raise serializers.ValidationError(f'يوم {k}: القيمة يجب أن تكون قائمة فترات.')
            day_slots = []
            for it in raw:
                if not isinstance(it, dict):
                    continue
                st = (it.get('start') or '').strip() if isinstance(it.get('start'), str) else ''
                en = (it.get('end') or '').strip() if isinstance(it.get('end'), str) else ''
                if not st and not en:
                    continue
                day_slots.append({'start': st, 'end': en})
            normalized[k] = day_slots
        return normalized

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        if instance.logo:
            data['logo'] = (
                _safe_build_absolute_uri(request, instance.logo.url) if request else instance.logo.url
            )
        return data

    def validate(self, attrs):
        for key in ('store_features', 'business_hours_weekly', 'categories'):
            if key not in attrs:
                continue
            val = attrs[key]
            if isinstance(val, str):
                s = val.strip()
                if not s:
                    if key == 'store_features':
                        attrs[key] = []
                    elif key == 'categories':
                        attrs[key] = []
                    else:
                        attrs[key] = {}
                else:
                    try:
                        attrs[key] = json.loads(s)
                    except json.JSONDecodeError:
                        raise serializers.ValidationError({key: 'صيغة JSON غير صالحة.'})

        lat = attrs.get('latitude', getattr(self.instance, 'latitude', None) if self.instance else None)
        lng = attrs.get('longitude', getattr(self.instance, 'longitude', None) if self.instance else None)
        if lat is not None and lng is not None:
            try:
                lat_f = float(lat)
                lng_f = float(lng)
            except (TypeError, ValueError):
                raise serializers.ValidationError({'latitude': 'قيمة خط العرض غير صالحة'})
            # قيم قريبة من (0،0) غالباً خطأ (نقرة خاطئة أو افتراضي) وليست داخل قطاع غزة
            if abs(lat_f) < 0.25 and abs(lng_f) < 0.25:
                raise serializers.ValidationError({
                    'latitude': 'حدد موقع المتجر على الخريطة داخل قطاع غزة — الإحداثيات الحالية قريبة جداً من صفر.',
                })
        return attrs

    def update(self, instance, validated_data):
        cats = validated_data.pop('categories', None)
        inst = super().update(instance, validated_data)
        if cats is not None:
            # cats may be list of ids (from JSON) or list of Category instances
            try:
                inst.categories.set(cats)
            except TypeError:
                # if ids were provided, resolve them
                inst.categories.set(Category.objects.filter(id__in=cats))

            # حافظ على حقل category القديم (الأول كافتراضي) لتوافق الصفحات القديمة
            first = None
            try:
                first = inst.categories.first()
            except Exception:
                first = None
            if first and (inst.category_id is None or inst.category_id not in inst.categories.values_list('id', flat=True)):
                inst.category = first
                inst.save(update_fields=['category'])
        _sync_merchant_profile_complete_from_store(inst)
        return inst


class StoreProductMiniSerializer(serializers.ModelSerializer):
    images = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Product
        fields = ('id', 'name', 'price', 'description', 'product_features', 'image', 'images', 'is_archived')

    def get_images(self, obj):
        return product_gallery_urls(obj, self.context.get('request'))

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        imgs = product_gallery_urls(instance, request)
        data['images'] = imgs
        if imgs:
            data['image'] = imgs[0]
        elif request and instance.image:
            data['image'] = _safe_build_absolute_uri(request, instance.image.url)
        elif instance.image:
            data['image'] = instance.image.url
        else:
            data['image'] = None
        return data


class StoreAdMiniSerializer(serializers.ModelSerializer):
    catalog_product_price = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = SponsoredAd
        fields = (
            'id',
            'title',
            'description',
            'product',
            'product_price',
            'catalog_product_price',
            'image',
            'images',
            'payment_receipt_image',
            'status',
            'created_at',
        )

    def get_catalog_product_price(self, obj):
        if obj.product_id:
            return str(obj.product.price)
        return None

    def get_images(self, obj):
        return sponsored_ad_gallery_urls(obj, self.context.get('request'))

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        imgs = sponsored_ad_gallery_urls(instance, request)
        data['images'] = imgs
        if imgs:
            data['image'] = imgs[0]
        elif instance.image:
            data['image'] = (
                _safe_build_absolute_uri(request, instance.image.url) if request else instance.image.url
            )
        else:
            data['image'] = None
        if instance.payment_receipt_image:
            data['payment_receipt_image'] = (
                _safe_build_absolute_uri(request, instance.payment_receipt_image.url)
                if request
                else instance.payment_receipt_image.url
            )
        return data


class StoreProfileDetailSerializer(StoreProfileSerializer):
    products = StoreProductMiniSerializer(many=True, read_only=True)
    sponsored_ads = StoreAdMiniSerializer(many=True, read_only=True, source='ads')

    class Meta(StoreProfileSerializer.Meta):
        fields = StoreProfileSerializer.Meta.fields + ('products', 'sponsored_ads')


class PrimaryAdminStoreRowSerializer(serializers.ModelSerializer):
    """صف واحد لكل متجر — للمدير الأساسي (بحث، خريطة، جوال، اشتراك، تعليق)."""

    merchant_username = serializers.CharField(source='user.username', read_only=True)
    merchant_phone = serializers.CharField(source='user.phone_number', read_only=True)
    category_name = serializers.SerializerMethodField()
    subscription_end_date = serializers.SerializerMethodField()
    subscription_is_active = serializers.SerializerMethodField()
    is_publicly_visible = serializers.SerializerMethodField()
    map_preview_url = serializers.SerializerMethodField()
    rating_average = serializers.SerializerMethodField()
    rating_count = serializers.SerializerMethodField()

    class Meta:
        model = StoreProfile
        fields = (
            'id',
            'store_name',
            'description',
            'latitude',
            'longitude',
            'location_address',
            'category_name',
            'merchant_username',
            'merchant_phone',
            'subscription_end_date',
            'subscription_is_active',
            'is_suspended_by_admin',
            'is_publicly_visible',
            'map_preview_url',
            'rating_average',
            'rating_count',
        )

    def get_category_name(self, obj):
        return obj.category.name if obj.category_id else None

    def _subscription(self, obj):
        try:
            return obj.subscription
        except ObjectDoesNotExist:
            return None

    def get_subscription_end_date(self, obj):
        sub = self._subscription(obj)
        return sub.end_date if sub else None

    def get_subscription_is_active(self, obj):
        sub = self._subscription(obj)
        return bool(sub.is_active) if sub else False

    def get_is_publicly_visible(self, obj):
        from .subscription_visibility import store_is_publicly_visible

        return store_is_publicly_visible(obj)

    def get_map_preview_url(self, obj):
        lat, lng = obj.latitude, obj.longitude
        if lat is None or lng is None:
            return None
        return f'https://www.openstreetmap.org/?mlat={lat}&mlon={lng}#map=16/{lat}/{lng}'

    def get_rating_average(self, obj):
        avg, _ = store_rating_summary(obj)
        return avg

    def get_rating_count(self, obj):
        _, n = store_rating_summary(obj)
        return n


class StorePublicProfileSerializer(StoreProfileSerializer):
    """متجر للعرض العام: منتجات غير مؤرشفة فقط، وإعلانات نشطة فقط."""
    products = serializers.SerializerMethodField()
    sponsored_ads = serializers.SerializerMethodField()
    is_owner = serializers.SerializerMethodField()
    my_rating = serializers.SerializerMethodField()

    class Meta(StoreProfileSerializer.Meta):
        fields = StoreProfileSerializer.Meta.fields + ('products', 'sponsored_ads', 'is_owner', 'my_rating')

    def get_is_owner(self, obj):
        request = self.context.get('request')
        user = getattr(request, 'user', None) if request else None
        if not user or not user.is_authenticated:
            return False
        if getattr(user, 'user_type', None) != 'merchant':
            return False
        profile = getattr(user, 'store_profile', None)
        if profile is None:
            return False
        return profile.pk == obj.pk

    def get_my_rating(self, obj):
        request = self.context.get('request')
        user = getattr(request, 'user', None) if request else None
        if not user or not user.is_authenticated or getattr(user, 'user_type', None) != 'shopper':
            return None
        r = StoreRating.objects.filter(store=obj, shopper=user).first()
        return r.stars if r else None

    def get_products(self, obj):
        qs = obj.products.filter(is_archived=False).order_by('-created_at')
        return StoreProductMiniSerializer(qs, many=True, context=self.context).data

    def get_sponsored_ads(self, obj):
        cutoff = timezone.now() - timedelta(hours=24)
        qs = (
            obj.ads.filter(status='active', approved_at__isnull=False, approved_at__gte=cutoff)
            .select_related('product')
            .order_by('-approved_at')
        )
        return StoreAdMiniSerializer(qs, many=True, context=self.context).data


class CommunityServiceCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = CommunityServiceCategory
        fields = ('id', 'name', 'slug', 'image', 'description_hint', 'sort_order', 'is_active')

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        if instance.image:
            data['image'] = _safe_build_absolute_uri(request, instance.image.url) if request else instance.image.url
        return data


class CommunityServicePointPublicSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_slug = serializers.CharField(source='category.slug', read_only=True)
    institution_scope_label = serializers.CharField(source='get_institution_scope_display', read_only=True)

    class Meta:
        model = CommunityServicePoint
        fields = (
            'id',
            'category',
            'category_name',
            'category_slug',
            'title',
            'detail_description',
            'latitude',
            'longitude',
            'address_text',
            'water_is_potable',
            'institution_scope',
            'institution_scope_label',
        )


class CommunityServicePointMineSerializer(CommunityServicePointPublicSerializer):
    submitted_by_username = serializers.CharField(source='submitted_by.username', read_only=True)

    class Meta(CommunityServicePointPublicSerializer.Meta):
        fields = CommunityServicePointPublicSerializer.Meta.fields + (
            'status',
            'rejection_reason',
            'created_at',
            'submitted_by_username',
        )


class CommunityServicePointAdminSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_slug = serializers.CharField(source='category.slug', read_only=True)
    submitted_by_username = serializers.CharField(source='submitted_by.username', read_only=True)
    reviewed_by_username = serializers.SerializerMethodField()

    class Meta:
        model = CommunityServicePoint
        fields = (
            'id',
            'category',
            'category_name',
            'category_slug',
            'title',
            'detail_description',
            'latitude',
            'longitude',
            'address_text',
            'water_is_potable',
            'institution_scope',
            'status',
            'is_hidden_by_admin',
            'submitted_by',
            'submitted_by_username',
            'reviewed_by',
            'reviewed_by_username',
            'reviewed_at',
            'rejection_reason',
            'created_at',
            'updated_at',
        )

    def get_reviewed_by_username(self, obj):
        u = obj.reviewed_by
        return u.username if u else None


def _validate_community_point_category_fields(category, data):
    slug = category.slug
    water = data.get('water_is_potable')
    inst = (data.get('institution_scope') or '').strip()

    if slug == 'water':
        if water is None:
            raise serializers.ValidationError(
                {'water_is_potable': 'حدد هل المياه صالحة للشرب (نعم/لا) لهذا القسم.'}
            )
    else:
        data['water_is_potable'] = None

    if slug == 'institution':
        valid = {c[0] for c in CommunityServicePoint.INSTITUTION_SCOPE_CHOICES if c[0]}
        if inst not in valid:
            raise serializers.ValidationError(
                {'institution_scope': 'اختر نطاق المؤسسة: محلية، عالمية، أو خيرية.'}
            )
        data['institution_scope'] = inst
    else:
        data['institution_scope'] = ''

    return data


class CommunityServicePointSubmitSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommunityServicePoint
        fields = (
            'category',
            'title',
            'detail_description',
            'latitude',
            'longitude',
            'address_text',
            'water_is_potable',
            'institution_scope',
        )

    def validate(self, attrs):
        cat = attrs.get('category')
        if not cat or not cat.is_active:
            raise serializers.ValidationError({'category': 'قسم غير صالح أو غير نشط.'})
        la = attrs.get('latitude')
        lo = attrs.get('longitude')
        if la is None or lo is None:
            raise serializers.ValidationError('الإحداثيات مطلوبة.')
        try:
            la, lo = float(la), float(lo)
        except (TypeError, ValueError):
            raise serializers.ValidationError({'latitude': 'إحداثيات غير صالحة.'})
        if not (-90 <= la <= 90) or not (-180 <= lo <= 180):
            raise serializers.ValidationError({'latitude': 'نطاق الإحداثيات غير صالح.'})
        attrs['latitude'] = la
        attrs['longitude'] = lo
        return _validate_community_point_category_fields(cat, attrs)

    def create(self, validated_data):
        request = self.context['request']
        return CommunityServicePoint.objects.create(
            submitted_by=request.user,
            status=CommunityServicePoint.STATUS_PENDING,
            **validated_data,
        )


class CommunityServicePointAdminCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommunityServicePoint
        fields = (
            'category',
            'title',
            'detail_description',
            'latitude',
            'longitude',
            'address_text',
            'water_is_potable',
            'institution_scope',
        )

    def validate(self, attrs):
        cat = attrs.get('category')
        if not cat:
            raise serializers.ValidationError({'category': 'القسم مطلوب.'})
        la = attrs.get('latitude')
        lo = attrs.get('longitude')
        if la is None or lo is None:
            raise serializers.ValidationError('الإحداثيات مطلوبة.')
        try:
            la, lo = float(la), float(lo)
        except (TypeError, ValueError):
            raise serializers.ValidationError({'latitude': 'إحداثيات غير صالحة.'})
        attrs['latitude'] = la
        attrs['longitude'] = lo
        return _validate_community_point_category_fields(cat, attrs)

    def create(self, validated_data):
        request = self.context['request']
        now = timezone.now()
        return CommunityServicePoint.objects.create(
            submitted_by=request.user,
            reviewed_by=request.user,
            reviewed_at=now,
            status=CommunityServicePoint.STATUS_APPROVED,
            **validated_data,
        )


class CommunityServicePointAdminUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommunityServicePoint
        fields = (
            'category',
            'title',
            'detail_description',
            'latitude',
            'longitude',
            'address_text',
            'water_is_potable',
            'institution_scope',
            'is_hidden_by_admin',
        )

    def validate(self, attrs):
        # allow partial updates; normalize based on (possibly updated) category
        cat = attrs.get('category') or getattr(self.instance, 'category', None)
        if not cat:
            raise serializers.ValidationError({'category': 'القسم مطلوب.'})

        # merge current values so conditional validation doesn't fail on partial updates
        if self.instance is not None:
            for k in ('water_is_potable', 'institution_scope'):
                if k not in attrs:
                    attrs[k] = getattr(self.instance, k)

        la = attrs.get('latitude', getattr(self.instance, 'latitude', None))
        lo = attrs.get('longitude', getattr(self.instance, 'longitude', None))
        if la is None or lo is None:
            raise serializers.ValidationError('الإحداثيات مطلوبة.')
        try:
            la, lo = float(la), float(lo)
        except (TypeError, ValueError):
            raise serializers.ValidationError({'latitude': 'إحداثيات غير صالحة.'})
        attrs['latitude'] = la
        attrs['longitude'] = lo
        return _validate_community_point_category_fields(cat, attrs)
