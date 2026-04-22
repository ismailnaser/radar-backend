import json

from django.db import DatabaseError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, NotFound
from rest_framework.parsers import JSONParser, FormParser, MultiPartParser
from rest_framework.views import APIView
from django.db.models import Avg, Count, Prefetch, Q
from django.utils.text import slugify

from .models import (
    Category,
    CommunityServiceCategory,
    CommunityServicePoint,
    Service,
    StoreProfile,
    StoreRating,
)
from .serializers import (
    CategorySerializer,
    CommunityServiceCategorySerializer,
    CommunityServicePointAdminCreateSerializer,
    CommunityServicePointAdminSerializer,
    CommunityServicePointAdminUpdateSerializer,
    CommunityServicePointMineSerializer,
    CommunityServicePointPublicSerializer,
    CommunityServicePointSubmitSerializer,
    ServiceSerializer,
    StoreProfileSerializer,
    StoreProfileDetailSerializer,
    StorePublicProfileSerializer,
    PrimaryAdminStoreRowSerializer,
)
from django.db.models import F
from products.models import Product, SponsoredAd
from products.views import AdminRequiredPermission
from math import radians, cos, sin, asin, sqrt

from .subscription_visibility import queryset_public_stores_only, store_is_publicly_visible, ensure_subscription_for_store
from users.views import PrimaryAdminPermission

class CategoryListView(generics.ListAPIView):
    queryset = Category.objects.all().order_by('id')
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]

class ServiceListView(generics.ListAPIView):
    queryset = Service.objects.all()
    serializer_class = ServiceSerializer
    permission_classes = [permissions.AllowAny]

class NearbyStoreListView(generics.ListAPIView):
    serializer_class = StoreProfileSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        lat = self.request.query_params.get('lat')
        lng = self.request.query_params.get('lng')
        queryset = queryset_public_stores_only(StoreProfile.objects.all()).annotate(
            rating_avg=Avg('ratings__stars'),
            rating_n=Count('ratings', distinct=True),
        )

        if lat and lng:
            lat = float(lat)
            lng = float(lng)
            pass

        category_raw = self.request.query_params.get('category')
        if category_raw:
            raw = str(category_raw).strip()
            parts = [p.strip() for p in raw.split(',') if p.strip()]
            if len(parts) > 1:
                try:
                    ids = [int(p) for p in parts]
                except ValueError:
                    ids = []
                if ids:
                    queryset = queryset.filter(Q(category_id__in=ids) | Q(categories__id__in=ids)).distinct()
            else:
                queryset = queryset.filter(Q(category_id=raw) | Q(categories__id=raw)).distinct()

        return queryset

class StoreDetailView(generics.RetrieveAPIView):
    queryset = StoreProfile.objects.all().prefetch_related(
        Prefetch(
            'products',
            queryset=Product.objects.prefetch_related('gallery_images'),
        ),
        Prefetch(
            'ads',
            queryset=SponsoredAd.objects.prefetch_related('gallery_images'),
        ),
    )
    serializer_class = StorePublicProfileSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        from products.ad_lifecycle import purge_expired_sponsored_ads

        purge_expired_sponsored_ads()
        return super().get_queryset()

    def _can_access_public_store(self, request, store):
        if store_is_publicly_visible(store):
            return True
        user = getattr(request, 'user', None)
        if user and user.is_authenticated:
            if getattr(user, 'user_type', None) == 'merchant' and store.user_id == user.id:
                return True
            if getattr(user, 'user_type', None) == 'admin' or user.is_superuser or user.is_staff:
                return True
        return False

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        if not self._can_access_public_store(request, instance):
            if getattr(instance, 'is_suspended_by_admin', False):
                raise NotFound('تم تعليق المتجر إدارياً.')
            raise NotFound('المتجر غير متاح حالياً — ربما انتهى الاشتراك أو أُوقِف من الإدارة.')
        from orders.models import VisitorStat
        from django.utils import timezone

        stat, _created = VisitorStat.objects.get_or_create(store=instance, date=timezone.now().date())
        stat.visitor_count += 1
        stat.save()

        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class ShopperStoreRatingView(APIView):
    """متسوّق مسجّل: إرسال تقييم 1–5 لمتجر عام الظهور (يُحدَّث إن وُجد تقييم سابق)."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        if getattr(request.user, 'user_type', None) != 'shopper':
            msg = (
                'التقييم متاح لحساب «متسوّق» فقط. إذا كنت مسجّلاً كتاجر أو مدير، أنشئ حساب متسوّق أو '
                'سجّل الدخول بحساب متسوّق.'
            )
            return Response({'detail': msg, 'error': msg}, status=status.HTTP_403_FORBIDDEN)

        store = get_object_or_404(StoreProfile.objects.all(), pk=pk)
        if not store_is_publicly_visible(store):
            msg = 'المتجر غير متاح للتقييم حالياً (انتهى الاشتراك، تعليق إداري، أو إخفاء عن العامة).'
            return Response({'detail': msg, 'error': msg}, status=status.HTTP_404_NOT_FOUND)

        raw = request.data.get('stars', request.data.get('rating'))
        try:
            stars = int(raw)
        except (TypeError, ValueError):
            err = 'أرسل الحقل stars كرقم صحيح بين 1 و 5 في جسم الطلب (JSON).'
            return Response({'detail': err, 'error': err}, status=status.HTTP_400_BAD_REQUEST)
        if stars < 1 or stars > 5:
            err = 'عدد النجوم يجب أن يكون بين 1 و 5.'
            return Response({'detail': err, 'error': err}, status=status.HTTP_400_BAD_REQUEST)

        try:
            StoreRating.objects.update_or_create(
                store=store,
                shopper=request.user,
                defaults={'stars': stars},
            )
        except DatabaseError:
            err = 'تعذر حفظ التقييم. نفّذ على الخادم: python manage.py migrate'
            return Response({'detail': err, 'error': err}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        agg = StoreRating.objects.filter(store=store).aggregate(avg=Avg('stars'), n=Count('id'))
        avg = agg['avg']
        return Response(
            {
                'stars': stars,
                'rating_average': round(float(avg), 2) if avg is not None else None,
                'rating_count': agg['n'] or 0,
            }
        )


class PrimaryAdminStoreListView(generics.ListAPIView):
    """كل المتاجر للمدير الأساسي — بحث (?q) وفلترة قسم (?category) مثل الخريطة."""

    serializer_class = PrimaryAdminStoreRowSerializer
    permission_classes = [PrimaryAdminPermission]

    def get_queryset(self):
        qs = (
            StoreProfile.objects.select_related('user', 'category', 'subscription')
            .all()
            .annotate(rating_avg=Avg('ratings__stars'), rating_n=Count('ratings', distinct=True))
            .order_by('store_name', 'id')
        )
        q = (self.request.query_params.get('q') or '').strip()
        if q:
            qs = qs.filter(
                Q(store_name__icontains=q)
                | Q(user__username__icontains=q)
                | Q(user__phone_number__icontains=q)
                | Q(location_address__icontains=q)
            )
        raw_cat = self.request.query_params.get('category')
        if raw_cat is not None and str(raw_cat).strip() != '':
            try:
                cid = int(raw_cat)
                if cid > 0:
                    qs = qs.filter(category_id=cid)
            except (TypeError, ValueError):
                pass
        return qs

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        total_all_stores = StoreProfile.objects.count()
        serializer = self.get_serializer(queryset, many=True)
        return Response(
            {
                'results': serializer.data,
                'meta': {
                    'total_all_stores': total_all_stores,
                    'total_filtered': queryset.count(),
                },
            }
        )


class PrimaryAdminStoreSuspendView(generics.GenericAPIView):
    """تعليق أو إلغاء تعليق متجر من قبل المدير الأساسي."""

    permission_classes = [PrimaryAdminPermission]

    def patch(self, request, pk):
        store = get_object_or_404(StoreProfile.objects.select_related('user', 'subscription'), pk=pk)
        suspended = request.data.get('is_suspended_by_admin')
        if suspended is None:
            return Response(
                {'error': 'أرسل الحقل is_suspended_by_admin (true/false).'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        store.is_suspended_by_admin = bool(suspended)
        store.save(update_fields=['is_suspended_by_admin'])
        return Response(PrimaryAdminStoreRowSerializer(store, context={'request': request}).data)


class ShopperOrMerchantPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and getattr(u, 'user_type', None) in ('shopper', 'merchant'))


class CommunityCategoryListView(generics.ListAPIView):
    queryset = CommunityServiceCategory.objects.filter(is_active=True).order_by('sort_order', 'id')
    serializer_class = CommunityServiceCategorySerializer
    permission_classes = [permissions.AllowAny]


class PrimaryAdminStoreCategoriesView(APIView):
    """إدارة أقسام المتاجر — للمدير الأساسي فقط."""

    permission_classes = [PrimaryAdminPermission]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        qs = Category.objects.all().order_by('id')
        return Response({'results': CategorySerializer(qs, many=True, context={'request': request}).data})

    def post(self, request):
        name = (request.data.get('name') or '').strip()
        if not name:
            return Response({'error': 'اسم القسم مطلوب.'}, status=status.HTTP_400_BAD_REQUEST)
        cat = Category.objects.create(name=name, image=request.FILES.get('image'))
        return Response(CategorySerializer(cat, context={'request': request}).data, status=status.HTTP_201_CREATED)


class PrimaryAdminStoreCategoryDeleteView(APIView):
    """حذف قسم متجر (سيصبح category = null للمتاجر المرتبطة)."""

    permission_classes = [PrimaryAdminPermission]

    def delete(self, request, pk):
        cat = get_object_or_404(Category, pk=pk)
        cat.delete()
        return Response({'message': 'deleted'})


class PrimaryAdminCommunityCategoriesView(APIView):
    """إدارة أقسام الخدمات المجتمعية — للمدير الأساسي فقط."""

    permission_classes = [PrimaryAdminPermission]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        qs = CommunityServiceCategory.objects.all().order_by('sort_order', 'id')
        return Response({'results': CommunityServiceCategorySerializer(qs, many=True, context={'request': request}).data})

    def post(self, request):
        name = (request.data.get('name') or '').strip()
        if not name:
            return Response({'error': 'اسم القسم مطلوب.'}, status=status.HTTP_400_BAD_REQUEST)
        slug = (request.data.get('slug') or '').strip()
        if not slug:
            slug = slugify(name, allow_unicode=True)[:80]
        base = slug
        i = 1
        while CommunityServiceCategory.objects.filter(slug=slug).exists():
            i += 1
            slug = f"{base[:70]}-{i}"[:80]

        desc = (request.data.get('description_hint') or '').strip()
        sort_order = request.data.get('sort_order')
        try:
            sort_order = int(sort_order) if sort_order not in (None, '') else 0
        except (TypeError, ValueError):
            sort_order = 0
        cat = CommunityServiceCategory.objects.create(
            name=name,
            slug=slug,
            image=request.FILES.get('image'),
            description_hint=desc,
            sort_order=sort_order,
            is_active=True,
        )
        return Response(CommunityServiceCategorySerializer(cat, context={'request': request}).data, status=status.HTTP_201_CREATED)


class PrimaryAdminCommunityCategoryDeleteView(APIView):
    """حذف قسم خدمة مجتمعية — إن كان عليه نقاط، نُعطّله بدل الحذف."""

    permission_classes = [PrimaryAdminPermission]

    def delete(self, request, pk):
        cat = get_object_or_404(CommunityServiceCategory, pk=pk)
        if cat.points.exists():
            cat.is_active = False
            cat.save(update_fields=['is_active'])
            return Response({'message': 'deactivated'})
        cat.delete()
        return Response({'message': 'deleted'})

class CommunityPointListView(generics.ListAPIView):
    serializer_class = CommunityServicePointPublicSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = CommunityServicePoint.objects.filter(
            status=CommunityServicePoint.STATUS_APPROVED,
            is_hidden_by_admin=False,
            category__is_active=True,
        ).select_related('category')
        cid = self.request.query_params.get('category')
        if cid is not None and str(cid).strip() != '':
            try:
                qs = qs.filter(category_id=int(cid))
            except (TypeError, ValueError):
                pass
        return qs.order_by('category__sort_order', 'title')


class CommunityPointMyListView(generics.ListAPIView):
    serializer_class = CommunityServicePointMineSerializer
    permission_classes = [ShopperOrMerchantPermission]

    def get_queryset(self):
        return (
            CommunityServicePoint.objects.filter(submitted_by=self.request.user)
            .select_related('category')
            .order_by('-created_at')
        )


class CommunityPointSubmitView(generics.CreateAPIView):
    serializer_class = CommunityServicePointSubmitSerializer
    permission_classes = [ShopperOrMerchantPermission]
    parser_classes = [JSONParser, FormParser]

    def perform_create(self, serializer):
        point = serializer.save()
        try:
            from users.models import AdminNotificationEvent

            AdminNotificationEvent.objects.create(
                event_type=AdminNotificationEvent.TYPE_COMMUNITY_POINT,
                title="طلب خدمة مجتمعية جديد",
                body=f"{getattr(point, 'title', '—')}",
                created_by=self.request.user,
                related_app="stores",
                related_id=getattr(point, "id", None),
            )
        except Exception:
            pass


class AdminCommunityPointListCreateView(generics.ListCreateAPIView):
    permission_classes = [AdminRequiredPermission]
    parser_classes = [JSONParser, FormParser]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CommunityServicePointAdminCreateSerializer
        return CommunityServicePointAdminSerializer

    def get_queryset(self):
        qs = CommunityServicePoint.objects.select_related('category', 'submitted_by', 'reviewed_by')
        st = (self.request.query_params.get('status') or '').strip().lower()
        if st in ('pending', 'approved', 'rejected'):
            qs = qs.filter(status=st)
        return qs.order_by('-created_at')


class AdminCommunityPointModerateView(APIView):
    permission_classes = [AdminRequiredPermission]
    parser_classes = [JSONParser, FormParser]

    def patch(self, request, pk):
        point = get_object_or_404(CommunityServicePoint.objects.select_related('category'), pk=pk)
        action = (request.data.get('action') or '').strip().lower()
        if action == 'approve':
            point.status = CommunityServicePoint.STATUS_APPROVED
            point.reviewed_by = request.user
            point.reviewed_at = timezone.now()
            point.rejection_reason = ''
            point.save(
                update_fields=['status', 'reviewed_by', 'reviewed_at', 'rejection_reason', 'updated_at']
            )
            return Response(CommunityServicePointAdminSerializer(point, context={'request': request}).data)
        if action == 'reject':
            reason = (request.data.get('rejection_reason') or '').strip()
            if not reason:
                return Response(
                    {'error': 'أرسل سبب الرفض في rejection_reason.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            point.status = CommunityServicePoint.STATUS_REJECTED
            point.reviewed_by = request.user
            point.reviewed_at = timezone.now()
            point.rejection_reason = reason
            point.save(
                update_fields=['status', 'reviewed_by', 'reviewed_at', 'rejection_reason', 'updated_at']
            )
            return Response(CommunityServicePointAdminSerializer(point, context={'request': request}).data)
        if action in ('hide', 'unhide'):
            point.is_hidden_by_admin = action == 'hide'
            point.reviewed_by = request.user
            point.reviewed_at = timezone.now()
            point.save(update_fields=['is_hidden_by_admin', 'reviewed_by', 'reviewed_at', 'updated_at'])
            return Response(CommunityServicePointAdminSerializer(point, context={'request': request}).data)
        return Response(
            {'error': 'action يجب أن يكون approve أو reject أو hide أو unhide.'},
            status=status.HTTP_400_BAD_REQUEST,
        )


class AdminCommunityPointDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [AdminRequiredPermission]
    parser_classes = [JSONParser, FormParser]
    queryset = CommunityServicePoint.objects.select_related('category', 'submitted_by', 'reviewed_by')

    def get_serializer_class(self):
        if self.request.method in ('PATCH', 'PUT'):
            return CommunityServicePointAdminUpdateSerializer
        return CommunityServicePointAdminSerializer

    def perform_update(self, serializer):
        inst = serializer.save(reviewed_by=self.request.user, reviewed_at=timezone.now())
        # keep status consistent: edited points remain approved unless explicitly rejected elsewhere
        if inst.status != CommunityServicePoint.STATUS_APPROVED:
            inst.status = CommunityServicePoint.STATUS_APPROVED
            inst.rejection_reason = ''
            inst.save(update_fields=['status', 'rejection_reason', 'updated_at'])


class MerchantStoreProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = StoreProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        if getattr(self.request.user, 'user_type', None) != 'merchant':
            raise PermissionDenied("Unauthorized")
        store, _created = StoreProfile.objects.get_or_create(
            user=self.request.user,
            defaults={
                "store_name": getattr(self.request.user, "username", "متجر"),
                "description": "",
            },
        )
        ensure_subscription_for_store(store)
        return store

    def get_serializer_class(self):
        if self.request.method == 'GET':
            return StoreProfileDetailSerializer
        return StoreProfileSerializer

    def _normalize_categories_payload(self, data):
        """
        يقبل categories بعدة صيغ (multipart/json):
        - categories=1&categories=2
        - categories="[1,2]"
        - categories="1,2"
        """
        if not hasattr(data, 'copy'):
            return data

        payload = data.copy()
        raw_vals = payload.getlist('categories') if hasattr(payload, 'getlist') else [payload.get('categories')]
        if not raw_vals:
            return payload

        normalized = []
        for raw in raw_vals:
            if raw is None:
                continue
            items = []
            if isinstance(raw, (list, tuple)):
                items = list(raw)
            elif isinstance(raw, str):
                s = raw.strip()
                if not s:
                    continue
                if s.startswith('[') and s.endswith(']'):
                    try:
                        arr = json.loads(s)
                    except json.JSONDecodeError:
                        arr = [s]
                    items = arr if isinstance(arr, list) else [arr]
                elif ',' in s:
                    items = [p.strip() for p in s.split(',') if p.strip()]
                else:
                    items = [s]
            else:
                items = [raw]

            for it in items:
                try:
                    n = int(str(it).strip())
                except (TypeError, ValueError):
                    continue
                normalized.append(str(n))

        # إزالة التكرار مع الحفاظ على الترتيب
        deduped = list(dict.fromkeys(normalized))
        if hasattr(payload, 'setlist'):
            payload.setlist('categories', deduped)
        else:
            payload['categories'] = deduped
        return payload

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        data = self._normalize_categories_payload(request.data)
        serializer = self.get_serializer(instance, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)
