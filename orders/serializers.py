from decimal import Decimal
from rest_framework import serializers
from .models import Cart, CartItem, VisitorStat
from products.serializers import (
    ProductSerializer,
    _absolute_media_url,
    assert_sponsored_ad_matches_product,
    sponsored_ad_is_live,
)
from products.models import Product, SponsoredAd
from products.media_utils import product_gallery_urls, sponsored_ad_gallery_urls

class CartItemSerializer(serializers.ModelSerializer):
    product_details = ProductSerializer(source='product', read_only=True)
    line_title = serializers.SerializerMethodField()
    line_image = serializers.SerializerMethodField()
    line_images = serializers.SerializerMethodField()
    is_standalone_ad_line = serializers.SerializerMethodField()
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
    sponsored_unit_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True, allow_null=True
    )
    catalog_unit_price = serializers.SerializerMethodField()
    effective_unit_price = serializers.SerializerMethodField()
    line_total_effective = serializers.SerializerMethodField()
    is_promotional_line = serializers.SerializerMethodField()
    is_expired_line = serializers.BooleanField(read_only=True)
    expired_message = serializers.CharField(read_only=True)

    class Meta:
        model = CartItem
        fields = (
            'id',
            'cart',
            'product',
            'product_details',
            'line_title',
            'line_image',
            'line_images',
            'is_standalone_ad_line',
            'standalone_line_title',
            'quantity',
            'note',
            'sponsored_ad',
            'sponsored_unit_price',
            'catalog_unit_price',
            'effective_unit_price',
            'line_total_effective',
            'is_promotional_line',
            'is_expired_line',
            'expired_message',
        )
        read_only_fields = ('standalone_line_title',)

    def get_line_title(self, obj):
        if obj.product_id:
            return obj.product.name
        return (obj.standalone_line_title or '').strip() or 'عرض ممول'

    def get_line_images(self, obj):
        request = self.context.get('request')
        if obj.product_id:
            return product_gallery_urls(obj.product, request)
        sa = getattr(obj, 'sponsored_ad', None)
        if sa:
            return sponsored_ad_gallery_urls(sa, request)
        return []

    def get_line_image(self, obj):
        imgs = self.get_line_images(obj)
        if imgs:
            return imgs[0]
        return None

    def get_is_standalone_ad_line(self, obj):
        return obj.product_id is None

    def get_catalog_unit_price(self, obj):
        if obj.product_id:
            return str(obj.product.price)
        return ''

    def get_effective_unit_price(self, obj):
        return str(obj.effective_unit_price)

    def get_line_total_effective(self, obj):
        return str(obj.line_total_effective)

    def get_is_promotional_line(self, obj):
        return obj.is_promotional_line

    def create(self, validated_data):
        sa = validated_data.get('sponsored_ad')
        sponsored_unit_price = sa.product_price if sa is not None else None
        standalone_line_title = ''
        if sa is not None and sa.product_id is None:
            standalone_line_title = (sa.title or '')[:200]
        return CartItem.objects.create(
            sponsored_unit_price=sponsored_unit_price,
            standalone_line_title=standalone_line_title,
            **validated_data,
        )

    def validate_quantity(self, value):
        if value < 1:
            raise serializers.ValidationError('الكمية يجب أن تكون على الأقل ١')
        return value

    def validate_note(self, value):
        if value and len(value) > 2000:
            raise serializers.ValidationError('الملاحظة طويلة جداً')
        return value

    def validate(self, attrs):
        cart = attrs.get('cart')
        if cart is None and self.instance:
            cart = self.instance.cart
        request = self.context.get('request')
        if request and cart and cart.user_id != request.user.id:
            raise serializers.ValidationError({'cart': 'غير مصرح باستخدام هذه السلة'})
        if self.instance and getattr(self.instance, 'is_expired_line', False):
            raise serializers.ValidationError({'detail': 'هذا السطر منتهي الصلاحية ولا يمكن تعديله. احذفه من السلة.'})
        sa = attrs.get('sponsored_ad')
        if sa is None and self.instance:
            sa = self.instance.sponsored_ad
        product = attrs.get('product')
        if product is None and self.instance:
            product = self.instance.product
        if sa is None:
            if product is None:
                raise serializers.ValidationError(
                    {'product': 'اختر منتجاً أو أرسل رقم إعلان ممول صالح.'}
                )
            return attrs

        if not sponsored_ad_is_live(sa):
            raise serializers.ValidationError(
                {'sponsored_ad': 'انتهت مدة الإعلان أو لم يعد نشطاً.'}
            )

        if sa.product_id is None:
            if product is not None:
                raise serializers.ValidationError(
                    {'product': 'إعلان مستقل لا يُربط بمنتج في السلة.'}
                )
        else:
            if product is None:
                raise serializers.ValidationError(
                    {'product': 'هذا الإعلان مرتبط بمنتج من متجرك؛ أرسل معرّف ذلك المنتج.'}
                )
            assert_sponsored_ad_matches_product(sa, product)
        return attrs

class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)

    class Meta:
        model = Cart
        fields = ('id', 'name', 'notes', 'share_token', 'user', 'created_at', 'items')
        read_only_fields = ('user', 'share_token')

    def validate_notes(self, value):
        if value and len(value) > 4000:
            raise serializers.ValidationError('الملاحظة طويلة جداً')
        return value

class SharedCartPublicSerializer(serializers.ModelSerializer):
    """عرض عام للسلة عبر الرابط — بدون بيانات حساسة."""
    items = serializers.SerializerMethodField()
    total = serializers.SerializerMethodField()
    is_owner = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ('name', 'notes', 'items', 'total', 'is_owner')

    def get_is_owner(self, obj):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if not user or not getattr(user, 'is_authenticated', False):
            return False
        return obj.user_id == user.id

    def get_items(self, obj):
        request = self.context.get('request')
        out = []
        for it in obj.items.select_related('product', 'sponsored_ad').prefetch_related(
            'product__gallery_images',
            'sponsored_ad__gallery_images',
        ).all():
            store_id = None
            store_name = ''
            product_id = None
            product_features = []
            if it.product_id:
                p = it.product
                product_id = p.id
                store_id = p.store_id
                store_name = getattr(getattr(p, 'store', None), 'store_name', '') or ''
                name = p.name
                desc = p.description or ''
                product_features = getattr(p, 'product_features', None) or []
                catalog_price = str(p.price)
                imgs = product_gallery_urls(p, request)
                img = imgs[0] if imgs else None
            else:
                name = (it.standalone_line_title or '').strip() or 'عرض ممول'
                sa = it.sponsored_ad
                if sa:
                    store_id = sa.store_id
                    store_name = getattr(getattr(sa, 'store', None), 'store_name', '') or ''
                    desc = (sa.description or '').strip()
                else:
                    desc = ''
                catalog_price = ''
                imgs = sponsored_ad_gallery_urls(sa, request) if sa else []
                img = imgs[0] if imgs else None
            unit = it.effective_unit_price
            line_total = it.line_total_effective
            out.append({
                'id': it.id,
                'product_id': product_id,
                'store_id': store_id,
                'store_name': store_name,
                'product_name': name,
                'description': desc,
                'product_features': product_features,
                'price': str(unit),
                'catalog_price': catalog_price,
                'quantity': it.quantity,
                'line_total': str(line_total),
                'is_promotional_line': it.is_promotional_line,
                'is_standalone_ad_line': it.product_id is None,
                'is_expired_line': bool(getattr(it, 'is_expired_line', False)),
                'expired_message': (getattr(it, 'expired_message', '') or '').strip(),
                'note': it.note or '',
                'image': img or None,
                'images': imgs,
            })
        return out

    def get_total(self, obj):
        total = Decimal('0')
        for it in obj.items.select_related('product', 'sponsored_ad').all():
            total += it.line_total_effective
        return str(total)


class VisitorStatSerializer(serializers.ModelSerializer):
    class Meta:
        model = VisitorStat
        fields = '__all__'
