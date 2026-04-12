import logging
import traceback

from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Product, SponsoredAd, Subscription, Favorite, StoreFavorite, SubscriptionRenewalRequest
from .serializers import (
    ProductSerializer,
    SponsoredAdSerializer,
    SubscriptionSerializer,
    FavoriteSerializer,
    StoreFavoriteSerializer,
    SubscriptionRenewalRequestSerializer,
)
from stores.models import CommunityServicePoint, StoreProfile
from stores.subscription_visibility import (
    ensure_subscription_for_store,
    queryset_public_stores_only,
    store_is_publicly_visible,
)
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from django.db.models import Q, Sum

from .ad_lifecycle import purge_expired_sponsored_ads

logger = logging.getLogger(__name__)


class MerchantRequiredPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.user_type == 'merchant'


def user_is_app_admin(user):
    if not user or not user.is_authenticated:
        return False
    return bool(
        getattr(user, 'user_type', None) == 'admin'
        or user.is_superuser
        or user.is_staff
    )


class AdminRequiredPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        return user_is_app_admin(request.user)

class MerchantProductListCreateView(generics.ListCreateAPIView):
    serializer_class = ProductSerializer
    permission_classes = [MerchantRequiredPermission]

    def get_queryset(self):
        return Product.objects.filter(store__user=self.request.user).prefetch_related('gallery_images')

    def perform_create(self, serializer):
        store = StoreProfile.objects.get(user=self.request.user)
        serializer.save(store=store)

class MerchantProductUpdateDeleteView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ProductSerializer
    permission_classes = [MerchantRequiredPermission]

    def get_queryset(self):
        return Product.objects.filter(store__user=self.request.user).prefetch_related('gallery_images')

class AdRequestView(generics.ListCreateAPIView):
    serializer_class = SponsoredAdSerializer
    permission_classes = [MerchantRequiredPermission]

    def get_queryset(self):
        return (
            SponsoredAd.objects.filter(store__user=self.request.user)
            .prefetch_related('gallery_images')
            .order_by('-created_at')
        )

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

    def create(self, request, *args, **kwargs):
        """يلتقط أي استثناء أثناء إنشاء طلب الإعلان ويطبع التفاصيل كاملة في السجلات (stdout + logger)."""
        try:
            return super().create(request, *args, **kwargs)
        except Exception as exc:
            err_line = f"[POST merchant/ads] {type(exc).__name__}: {exc}"
            print(err_line, flush=True)
            print(traceback.format_exc(), flush=True)
            logger.exception("POST /api/products/merchant/ads/ failed: %s", err_line)
            raise

    def perform_create(self, serializer):
        store = StoreProfile.objects.get(user=self.request.user)
        ad = serializer.save(store=store)
        try:
            from users.models import AdminNotificationEvent

            AdminNotificationEvent.objects.create(
                event_type=AdminNotificationEvent.TYPE_AD_REQUEST,
                title="طلب إعلان ممول جديد",
                body=f"المتجر: {getattr(store, 'store_name', '—')}",
                created_by=self.request.user,
                related_app="products",
                related_id=getattr(ad, "id", None),
            )
        except Exception:
            pass


class MerchantAdUpdateDeleteView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = SponsoredAdSerializer
    permission_classes = [MerchantRequiredPermission]

    def get_queryset(self):
        return SponsoredAd.objects.filter(store__user=self.request.user)

    def update(self, request, *args, **kwargs):
        ad = self.get_object()
        if ad.status != 'pending':
            return Response({"error": "Cannot edit ad unless pending"}, status=status.HTTP_400_BAD_REQUEST)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        ad = self.get_object()
        if ad.status != 'pending':
            return Response({"error": "Cannot delete ad unless pending"}, status=status.HTTP_400_BAD_REQUEST)
        return super().destroy(request, *args, **kwargs)


class AdminSponsoredAdListView(generics.ListAPIView):
    """كل الإعلانات الممولة (للمراجعة) — ?status=pending|active|rejected"""
    serializer_class = SponsoredAdSerializer
    permission_classes = [AdminRequiredPermission]

    def get_queryset(self):
        qs = SponsoredAd.objects.select_related("store").order_by("-created_at")
        st = self.request.query_params.get("status")
        if st in ("pending", "active", "rejected", "expired"):
            qs = qs.filter(status=st)
        return qs

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx


class AdminSponsoredAdDetailView(generics.RetrieveAPIView):
    """تفاصيل إعلان واحد للمراجعة (إشعار الدفع داخل التطبيق)."""
    serializer_class = SponsoredAdSerializer
    permission_classes = [AdminRequiredPermission]
    queryset = SponsoredAd.objects.select_related("store")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx


class AdminPendingCountsView(APIView):
    """عدد الطلبات المعلّقة: إعلانات ممولة + تجديد اشتراك + نقاط خدمات مجتمعية — لشارات لوحة المدير."""

    permission_classes = [AdminRequiredPermission]

    def get(self, request):
        pending_ads = SponsoredAd.objects.filter(status="pending").count()
        pending_renewals = SubscriptionRenewalRequest.objects.filter(status="pending").count()
        pending_community_points = CommunityServicePoint.objects.filter(
            status=CommunityServicePoint.STATUS_PENDING
        ).count()
        pending_total = pending_ads + pending_renewals + pending_community_points
        return Response(
            {
                "pending_ads": pending_ads,
                "pending_renewals": pending_renewals,
                "pending_community_points": pending_community_points,
                "pending_total": pending_total,
            }
        )


class AdminSubscriptionRenewalListView(generics.ListAPIView):
    """طلبات تجديد الاشتراك — ?status=pending|approved|rejected"""
    serializer_class = SubscriptionRenewalRequestSerializer
    permission_classes = [AdminRequiredPermission]

    def get_queryset(self):
        qs = SubscriptionRenewalRequest.objects.select_related("store", "decided_by").order_by("-created_at")
        st = self.request.query_params.get("status")
        if st in ("pending", "approved", "rejected"):
            qs = qs.filter(status=st)
        return qs

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx


class AdminAdSetStatusView(generics.GenericAPIView):
    permission_classes = [AdminRequiredPermission]

    def post(self, request, pk):
        ad = get_object_or_404(SponsoredAd, pk=pk)
        new_status = request.data.get("status")
        if new_status not in ("pending", "active", "rejected"):
            return Response({"error": "Invalid status"}, status=status.HTTP_400_BAD_REQUEST)
        ad.status = new_status
        if new_status == "active":
            ad.approved_at = timezone.now()
        else:
            ad.approved_at = None
        ad.save(update_fields=["status", "approved_at"])
        # سجل أرباح الإعلان عند تفعيله لأول مرة
        if new_status == "active":
            from .models import FinanceTransfer

            FinanceTransfer.objects.get_or_create(
                sponsored_ad=ad,
                defaults={
                    "kind": FinanceTransfer.KIND_AD,
                    "store": ad.store,
                    "payment_method": ad.payment_method,
                    "amount_ils": Decimal("5.00"),
                },
            )
        return Response({"message": "updated", "status": ad.status, "approved_at": ad.approved_at})

class SubscriptionStatusView(generics.RetrieveAPIView):
    serializer_class = SubscriptionSerializer
    permission_classes = [MerchantRequiredPermission]

    def get_object(self):
        store = StoreProfile.objects.get(user=self.request.user)
        return ensure_subscription_for_store(store)


class MerchantSubscriptionRenewalRequestListCreateView(generics.ListCreateAPIView):
    serializer_class = SubscriptionRenewalRequestSerializer
    permission_classes = [MerchantRequiredPermission]

    def get_queryset(self):
        return SubscriptionRenewalRequest.objects.filter(store__user=self.request.user).order_by('-created_at')

    def perform_create(self, serializer):
        store = StoreProfile.objects.get(user=self.request.user)
        # رسوم تجديد الاشتراك ثابتة (10 شيكل) — تُستخدم في تقارير الأرباح.
        req = serializer.save(store=store, amount_ils=Decimal("10.00"))
        try:
            from users.models import AdminNotificationEvent

            AdminNotificationEvent.objects.create(
                event_type=AdminNotificationEvent.TYPE_SUBSCRIPTION_RENEWAL,
                title="طلب تجديد اشتراك جديد",
                body=f"المتجر: {getattr(store, 'store_name', '—')}",
                created_by=self.request.user,
                related_app="products",
                related_id=getattr(req, "id", None),
            )
        except Exception:
            pass


class AdminSubscriptionRenewalRequestApproveView(generics.GenericAPIView):
    permission_classes = [AdminRequiredPermission]

    def post(self, request, pk):
        req = get_object_or_404(SubscriptionRenewalRequest, pk=pk)
        if req.status != 'pending':
            return Response({"error": "Request already decided"}, status=status.HTTP_400_BAD_REQUEST)
        req.approve(decided_by=request.user, days=30)
        # سجل التحويل (إن لم يُسجّل)
        from .models import FinanceTransfer

        FinanceTransfer.objects.get_or_create(
            subscription_renewal=req,
            defaults={
                "kind": FinanceTransfer.KIND_SUBSCRIPTION_RENEWAL,
                "store": req.store,
                "payment_method": req.payment_method,
                "amount_ils": req.amount_ils or Decimal("10.00"),
            },
        )
        return Response({"message": "approved"})


class AdminSubscriptionRenewalRequestRejectView(generics.GenericAPIView):
    permission_classes = [AdminRequiredPermission]

    def post(self, request, pk):
        req = get_object_or_404(SubscriptionRenewalRequest, pk=pk)
        if req.status != 'pending':
            return Response({"error": "Request already decided"}, status=status.HTTP_400_BAD_REQUEST)
        req.reject(decided_by=request.user)
        return Response({"message": "rejected"})

class PublicProductListView(generics.ListAPIView):
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        base = Product.objects.filter(is_archived=False).select_related('store')
        store_id = self.request.query_params.get('store_id')
        if store_id is not None and str(store_id).strip() != '':
            try:
                sid = int(store_id)
            except (TypeError, ValueError):
                return Product.objects.none()
            store = StoreProfile.objects.filter(pk=sid).first()
            if not store or not store_is_publicly_visible(store):
                return Product.objects.none()
            return base.filter(store_id=sid)
        visible_ids = queryset_public_stores_only(StoreProfile.objects.all()).values_list('pk', flat=True)
        return base.filter(store_id__in=visible_ids)

class PublicAdListView(generics.ListAPIView):
    serializer_class = SponsoredAdSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        purge_expired_sponsored_ads()
        cutoff = timezone.now() - timedelta(hours=24)
        visible_stores = queryset_public_stores_only(StoreProfile.objects.all())
        qs = (
            SponsoredAd.objects.filter(
                status='active',
                approved_at__isnull=False,
                approved_at__gte=cutoff,
                store__in=visible_stores,
            )
            .select_related('store', 'store__category', 'product')
            .prefetch_related('gallery_images')
            .order_by('-approved_at')
        )
        raw_cat = self.request.query_params.get('category')
        if raw_cat is not None and str(raw_cat).strip() != '':
            try:
                cid = int(raw_cat)
                if cid > 0:
                    qs = qs.filter(store__category_id=cid)
            except (TypeError, ValueError):
                pass
        return qs

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx

class FavoriteViewSet(viewsets.ModelViewSet):
    serializer_class = FavoriteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return (
            Favorite.objects.filter(user=self.request.user)
            .select_related('product', 'product__store', 'sponsored_ad', 'sponsored_ad__store')
            .prefetch_related('product__gallery_images', 'sponsored_ad__gallery_images')
        )

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = serializer.validated_data.get('product')
        sponsored_ad = serializer.validated_data.get('sponsored_ad')
        if product is None and sponsored_ad is not None and sponsored_ad.product_id is None:
            fav = Favorite.objects.filter(
                user=request.user,
                product__isnull=True,
                sponsored_ad=sponsored_ad,
            ).first()
            if fav:
                created = False
            else:
                fav = Favorite.objects.create(
                    user=request.user,
                    product=None,
                    sponsored_ad=sponsored_ad,
                )
                created = True
        else:
            fav, created = Favorite.objects.get_or_create(
                user=request.user,
                product=product,
                defaults={'sponsored_ad': sponsored_ad},
            )
            if not created and sponsored_ad is not None:
                fav.sponsored_ad = sponsored_ad
                fav.save(update_fields=['sponsored_ad'])
        out = FavoriteSerializer(fav, context=self.get_serializer_context())
        return Response(out.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class StoreFavoriteViewSet(viewsets.ModelViewSet):
    serializer_class = StoreFavoriteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return StoreFavorite.objects.filter(user=self.request.user).select_related('store', 'store__category')

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


def user_is_primary_admin(user):
    if not user or not user.is_authenticated:
        return False
    return bool(getattr(user, "is_primary_admin", False) or user.is_superuser)


class PrimaryAdminRequiredPermission(permissions.BasePermission):
    message = "هذا الإجراء متاح للمدير الأساسي فقط."

    def has_permission(self, request, view):
        return user_is_primary_admin(request.user)


class AdminFinanceTransfersView(APIView):
    """تقارير الأرباح/التحويلات — للمدير الأساسي فقط.

    Query params:
      - q: بحث باسم المتجر أو اسم المستخدم أو الجوال
      - from: YYYY-MM-DD
      - to: YYYY-MM-DD
      - method: balipay_wallet|bank_palestine|other
      - kind: sponsored_ad|subscription_renewal
    """

    permission_classes = [PrimaryAdminRequiredPermission]

    def get(self, request):
        from .models import FinanceTransfer

        def abs_media(u):
            if not u:
                return None
            try:
                url = request.build_absolute_uri(u)
                xf_proto = (request.META.get("HTTP_X_FORWARDED_PROTO") or "").split(",")[0].strip().lower()
                if xf_proto == "https" and url.startswith("http://"):
                    url = "https://" + url[len("http://") :]
                return url
            except Exception:
                return u

        qs = (
            FinanceTransfer.objects.select_related("store", "store__user")
            .order_by("-created_at")
        )

        q = (request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(
                Q(store__store_name__icontains=q)
                | Q(store__user__username__icontains=q)
                | Q(store__user__phone_number__icontains=q)
            )

        method = (request.query_params.get("method") or "").strip()
        if method in ("balipay_wallet", "bank_palestine", "other"):
            qs = qs.filter(payment_method=method)

        kind = (request.query_params.get("kind") or "").strip()
        if kind in ("sponsored_ad", "subscription_renewal"):
            qs = qs.filter(kind=kind)

        from_raw = (request.query_params.get("from") or "").strip()
        to_raw = (request.query_params.get("to") or "").strip()
        # التاريخ باليوم (حسب created_at)
        if from_raw:
            try:
                qs = qs.filter(created_at__date__gte=from_raw)
            except Exception:
                pass
        if to_raw:
            try:
                qs = qs.filter(created_at__date__lte=to_raw)
            except Exception:
                pass

        total_amount = qs.aggregate(total=Sum("amount_ils")).get("total") or Decimal("0.00")
        total_count = qs.count()

        results = []
        for t in qs[:500]:
            u = getattr(t.store, "user", None)
            receipt_url = None
            try:
                if getattr(t, "sponsored_ad_id", None) and getattr(t, "sponsored_ad", None):
                    img = getattr(t.sponsored_ad, "payment_receipt_image", None)
                    if img:
                        receipt_url = abs_media(img.url)
                elif getattr(t, "subscription_renewal_id", None) and getattr(t, "subscription_renewal", None):
                    img = getattr(t.subscription_renewal, "receipt_image", None)
                    if img:
                        receipt_url = abs_media(img.url)
            except Exception:
                receipt_url = None
            results.append(
                {
                    "id": t.id,
                    "kind": t.kind,
                    "kind_label": t.get_kind_display(),
                    "store_id": t.store_id,
                    "store_name": t.store.store_name,
                    "merchant_username": getattr(u, "username", None),
                    "merchant_phone": getattr(u, "phone_number", None),
                    "payment_method": t.payment_method,
                    "payment_method_label": t.get_payment_method_display(),
                    "amount_ils": str(t.amount_ils),
                    "created_at": t.created_at,
                    "receipt_image": receipt_url,
                }
            )

        return Response(
            {
                "meta": {
                    "total_count": total_count,
                    "total_amount_ils": str(total_amount),
                },
                "results": results,
            }
        )
