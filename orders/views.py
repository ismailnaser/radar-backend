from rest_framework import generics, permissions, status
from rest_framework.response import Response
from .models import Cart, CartItem, VisitorStat
from .serializers import CartSerializer, CartItemSerializer, VisitorStatSerializer, SharedCartPublicSerializer
from stores.models import StoreProfile
from django.db.models import Sum, Count, Value, IntegerField, Prefetch
from django.db.models.functions import Coalesce
from products.models import Product
from products.ad_lifecycle import purge_expired_sponsored_ads


class CartListCreateView(generics.ListCreateAPIView):
    serializer_class = CartSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        purge_expired_sponsored_ads()
        return Cart.objects.filter(user=self.request.user).prefetch_related(
            Prefetch(
                'items',
                queryset=CartItem.objects.select_related('product', 'sponsored_ad').prefetch_related(
                    'product__gallery_images',
                    'sponsored_ad__gallery_images',
                ),
            ),
        )

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class CartDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CartSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        purge_expired_sponsored_ads()
        return Cart.objects.filter(user=self.request.user).prefetch_related(
            Prefetch(
                'items',
                queryset=CartItem.objects.select_related('product', 'sponsored_ad').prefetch_related(
                    'product__gallery_images',
                    'sponsored_ad__gallery_images',
                ),
            ),
        )


class SharedCartPublicView(generics.RetrieveAPIView):
    """صفحة مشاركة: أي شخص يملك الرابط يرى تفاصيل السلة (قراءة فقط)."""
    permission_classes = [permissions.AllowAny]
    serializer_class = SharedCartPublicSerializer
    queryset = Cart.objects.prefetch_related(
        Prefetch(
            'items',
            queryset=CartItem.objects.select_related('product', 'sponsored_ad').prefetch_related(
                'product__gallery_images',
                'sponsored_ad__gallery_images',
            ),
        ),
    )
    lookup_field = 'share_token'
    lookup_url_kwarg = 'share_token'

class CartItemCreateView(generics.CreateAPIView):
    serializer_class = CartItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        purge_expired_sponsored_ads()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cart = serializer.validated_data['cart']
        product = serializer.validated_data.get('product')
        quantity = serializer.validated_data['quantity']
        sa = serializer.validated_data.get('sponsored_ad')
        if cart.user_id != request.user.id:
            return Response({'detail': 'غير مصرح'}, status=status.HTTP_403_FORBIDDEN)
        if product is not None:
            existing = CartItem.objects.filter(cart=cart, product=product).first()
        else:
            existing = CartItem.objects.filter(
                cart=cart, product__isnull=True, sponsored_ad=sa
            ).first()
        if existing:
            existing.quantity += quantity
            upd = ['quantity']
            if sa is not None:
                existing.sponsored_ad = sa
                existing.sponsored_unit_price = sa.product_price
                upd.extend(['sponsored_ad', 'sponsored_unit_price'])
                if sa.product_id is None:
                    existing.standalone_line_title = (sa.title or '')[:200]
                    upd.append('standalone_line_title')
            existing.save(update_fields=upd)
            out = CartItemSerializer(existing, context=self.get_serializer_context())
            return Response(out.data, status=status.HTTP_200_OK)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class CartItemDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CartItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return (
            CartItem.objects.filter(cart__user=self.request.user)
            .select_related('product', 'sponsored_ad', 'cart')
            .prefetch_related('product__gallery_images', 'sponsored_ad__gallery_images')
        )

class MerchantStatsView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        if request.user.user_type != 'merchant':
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)
        
        store = StoreProfile.objects.get(user=request.user)
        
        # Visitor stats
        stats = VisitorStat.objects.filter(store=store).last()
        visitor_count = stats.visitor_count if stats else 0
        
        # الأكثر إضافة للسلة (للتوافق مع الواجهات القديمة)
        top_products = (
            CartItem.objects.filter(product__store=store)
            .values('product_id', 'product__name')
            .annotate(total=Sum('quantity'))
            .order_by('-total')[:5]
        )

        product_qs = (
            Product.objects.filter(store=store, is_archived=False)
            .annotate(
                in_carts_quantity=Coalesce(
                    Sum('cartitem__quantity'),
                    Value(0),
                    output_field=IntegerField(),
                ),
                favorites_count=Count('favorited_by', distinct=True),
            )
            .order_by('-in_carts_quantity', '-favorites_count', 'name')
        )
        product_list = list(product_qs)
        product_insights = [
            {
                'id': p.id,
                'name': p.name,
                'in_carts_quantity': int(p.in_carts_quantity),
                'favorites_count': int(p.favorites_count),
            }
            for p in product_list
        ]
        summary = {
            'active_products': len(product_list),
            'total_units_in_carts': sum(int(p.in_carts_quantity) for p in product_list),
            'total_favorite_marks': sum(int(p.favorites_count) for p in product_list),
        }

        return Response({
            'visitor_count': visitor_count,
            'top_products': list(top_products),
            'product_insights': product_insights,
            'summary': summary,
        })
