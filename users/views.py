from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.db.models import Count, Q
from .serializers import (
    RegisterSerializer,
    MyTokenObtainPairSerializer,
    AdminAccountListSerializer,
    AdminAccountCreateSerializer,
    ChangeUsernameSerializer,
    ChangePasswordSerializer,
)
from rest_framework_simplejwt.views import TokenObtainPairView
from .utils import generate_otp, send_whatsapp_message
from django.utils import timezone
from datetime import timedelta
from stores.models import StoreProfile
from products.views import AdminRequiredPermission
from .models import AppOpenStat
from .models import SiteAnnouncement, AdminNotificationEvent, AdminWebPushSubscription

import json
import os
try:
    from pywebpush import webpush, WebPushException
except Exception:  # pragma: no cover
    webpush = None
    WebPushException = Exception

User = get_user_model()


def user_is_primary_admin(user):
    if not user or not user.is_authenticated:
        return False
    return bool(getattr(user, 'is_primary_admin', False) or user.is_superuser)


class PrimaryAdminPermission(permissions.BasePermission):
    message = 'هذا الإجراء متاح للمدير الأساسي فقط.'

    def has_permission(self, request, view):
        return user_is_primary_admin(request.user)


class ShopperNoticesView(APIView):
    """إشعارات لمرة واحدة (مثلاً بعد حذف مفضلة بانتهاء إعلان) — تُفرغ بعد الجلب."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if getattr(user, 'user_type', None) != 'shopper':
            return Response({'notices': []})
        notices = getattr(user, 'shopper_notices', None)
        if not isinstance(notices, list):
            notices = []
        user.shopper_notices = []
        user.save(update_fields=['shopper_notices'])
        return Response({'notices': notices})


class LoginView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (AllowAny,)
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        user.is_whatsapp_verified = True
        user.save()
        headers = self.get_success_headers(serializer.data)
        data = dict(serializer.data)
        if user.user_type == 'merchant':
            from stores.subscription_visibility import MERCHANT_SUBSCRIPTION_NOTICE_AR

            data['merchant_subscription_notice'] = MERCHANT_SUBSCRIPTION_NOTICE_AR
        return Response(data, status=status.HTTP_201_CREATED, headers=headers)

class VerifyWhatsAppView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        code = request.data.get('code')
        
        if not code:
            return Response({"error": "يرجى إدخال رمز التحقق"}, status=status.HTTP_400_BAD_REQUEST)
            
        if user.otp_code == code and user.otp_expiry > timezone.now():
            user.is_whatsapp_verified = True
            user.otp_code = None # Clear code
            user.save()
            return Response({"message": "تم التحقق بنجاح!"})
        else:
            return Response({"error": "رمز التحقق غير صحيح أو انتهت صلاحيته"}, status=status.HTTP_400_BAD_REQUEST)

class ResendOTPView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # تعطيل إرسال الواتساب مؤقتاً بناءً على طلب المستخدم
        return Response({"message": "خاصية الإرسال معطلة حالياً"})
        # user = request.user
        # otp = generate_otp()
        # user.otp_code = otp
        # user.otp_expiry = timezone.now() + timedelta(minutes=10)
        # user.save()
        # send_whatsapp_message(user.phone_number, otp)
        # return Response({"message": "تم إعادة إرسال الرمز بنجاح"})


class PrimaryAdminAccountListCreateView(APIView):
    """قائمة مدراء النظام وإنشاء مدير فرعي أو مدير أساسي جديد — للمدير الأساسي فقط."""

    permission_classes = [PrimaryAdminPermission]

    def get(self, request):
        qs = User.objects.filter(user_type='admin').order_by('-date_joined')
        return Response(AdminAccountListSerializer(qs, many=True).data)

    def post(self, request):
        ser = AdminAccountCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        tier = ser.validated_data['tier']
        is_primary = tier == 'primary'
        user = User.objects.create_user(
            username=ser.validated_data['username'],
            phone_number=ser.validated_data['phone_number'],
            password=ser.validated_data['password'],
            user_type='admin',
            is_primary_admin=is_primary,
            is_staff=True,
            is_whatsapp_verified=True,
        )
        return Response(
            AdminAccountListSerializer(user).data,
            status=status.HTTP_201_CREATED,
        )


class PrimaryAdminAccountToggleView(APIView):
    """تفعيل / تعطيل حساب مدير فرعي فقط (لا يؤثر على المدراء الأساسيين)."""

    permission_classes = [PrimaryAdminPermission]

    def patch(self, request, pk):
        target = get_object_or_404(User, pk=pk, user_type='admin')
        if target.id == request.user.id:
            return Response(
                {"error": "لا يمكنك تعطيل أو تفعيل حسابك الحالي من هنا."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if target.is_primary_admin:
            return Response(
                {"error": "لا يمكن تعديل حالة المدير الأساسي من هذه الشاشة."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        active = request.data.get('is_active')
        if active is None:
            return Response(
                {"error": "أرسل الحقل is_active (true/false)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        target.is_active = bool(active)
        target.save(update_fields=['is_active'])
        return Response(AdminAccountListSerializer(target).data)


class AppOpenPingView(APIView):
    """تسجيل فتح التطبيق (عام)."""

    permission_classes = [AllowAny]

    def post(self, request):
        today = timezone.now().date()
        stat, _created = AppOpenStat.objects.get_or_create(date=today, defaults={'open_count': 0})
        stat.open_count += 1
        stat.save(update_fields=['open_count'])
        return Response({'date': str(stat.date), 'open_count': stat.open_count})


class AdminMetricsView(APIView):
    """مؤشرات للوحة الإدارة: أعداد المستخدمين + فتحات اليوم."""

    permission_classes = [AdminRequiredPermission]

    def get(self, request):
        qs = User.objects.all()
        by_type = (
            qs.values('user_type')
            .annotate(total=Count('id'), active=Count('id', filter=Q(is_active=True)))
        )
        type_map = {row['user_type']: {'total': row['total'], 'active': row['active']} for row in by_type}

        shoppers = type_map.get('shopper', {'total': 0, 'active': 0})
        merchants = type_map.get('merchant', {'total': 0, 'active': 0})
        admins = type_map.get('admin', {'total': 0, 'active': 0})

        today = timezone.now().date()
        opens = AppOpenStat.objects.filter(date=today).first()
        opens_today = opens.open_count if opens else 0

        stores_total = StoreProfile.objects.count()
        stores_suspended = StoreProfile.objects.filter(is_suspended_by_admin=True).count()

        return Response(
            {
                'users': {
                    'shopper': shoppers,
                    'merchant': merchants,
                    'admin': admins,
                    'total': qs.count(),
                    'active_total': qs.filter(is_active=True).count(),
                },
                'app_opens': {
                    'today': str(today),
                    'opens_today': opens_today,
                },
                'stores': {
                    'total': stores_total,
                    'suspended': stores_suspended,
                },
            }
        )


class AdminUserSearchView(APIView):
    """بحث/قائمة مستخدمين (تاجر/متسوق) للمدير."""

    permission_classes = [AdminRequiredPermission]

    def get(self, request):
        q = (request.query_params.get('q') or '').strip()
        user_type = (request.query_params.get('user_type') or '').strip().lower()
        qs = User.objects.all().order_by('-date_joined')
        if user_type in ('shopper', 'merchant', 'admin'):
            qs = qs.filter(user_type=user_type)
        if q:
            qs = qs.filter(
                Q(username__icontains=q)
                | Q(phone_number__icontains=q)
            )
        out = []
        # حد بسيط لتفادي رد ضخم
        for u in qs[:200]:
            out.append(
                {
                    'id': u.id,
                    'username': u.username,
                    'phone_number': u.phone_number,
                    'user_type': u.user_type,
                    'is_active': bool(u.is_active),
                    'is_whatsapp_verified': bool(getattr(u, 'is_whatsapp_verified', False)),
                    'date_joined': u.date_joined,
                }
            )
        return Response({'results': out, 'count': len(out)})


class AdminUserToggleActiveView(APIView):
    """تعطيل/تفعيل مستخدم + (إن كان تاجر) تعليق/رفع تعليق المتجر."""

    permission_classes = [AdminRequiredPermission]

    def patch(self, request, pk):
        target = get_object_or_404(User, pk=pk)
        active = request.data.get('is_active')
        if active is None:
            return Response({'error': 'أرسل الحقل is_active (true/false).'}, status=status.HTTP_400_BAD_REQUEST)
        target.is_active = bool(active)
        target.save(update_fields=['is_active'])

        if getattr(target, 'user_type', None) == 'merchant':
            store = StoreProfile.objects.filter(user=target).first()
            if store:
                store.is_suspended_by_admin = not target.is_active
                store.save(update_fields=['is_suspended_by_admin'])

        return Response(
            {
                'id': target.id,
                'is_active': bool(target.is_active),
                'user_type': target.user_type,
            }
        )


class MeChangeUsernameView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        ser = ChangeUsernameSerializer(data=request.data, context={'request': request})
        ser.is_valid(raise_exception=True)
        request.user.username = ser.validated_data['username']
        request.user.save(update_fields=['username'])
        return Response({'username': request.user.username})


class MeChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = ChangePasswordSerializer(data=request.data, context={'request': request})
        ser.is_valid(raise_exception=True)
        request.user.set_password(ser.validated_data['new_password'])
        request.user.save(update_fields=['password'])
        return Response({'message': 'تم تغيير كلمة المرور بنجاح.'})


class PublicAnnouncementsView(APIView):
    """إعلانات عامة للواجهة (عام)."""

    permission_classes = [AllowAny]

    def get(self, request):
        qs = SiteAnnouncement.objects.filter(is_active=True).order_by("-created_at")
        out = []
        for a in qs[:3]:
            out.append(
                {
                    "id": a.id,
                    "message": a.message,
                    "created_at": a.created_at,
                }
            )
        return Response({"results": out})


class PrimaryAdminAnnouncementsView(APIView):
    """إدارة الإعلانات العامة — للمدير الأساسي."""

    permission_classes = [PrimaryAdminPermission]

    def get(self, request):
        qs = SiteAnnouncement.objects.all().order_by("-created_at")
        out = []
        for a in qs[:50]:
            out.append(
                {
                    "id": a.id,
                    "message": a.message,
                    "is_active": bool(a.is_active),
                    "created_at": a.created_at,
                }
            )
        return Response({"results": out})

    def post(self, request):
        msg = (request.data.get("message") or "").strip()
        if not msg:
            return Response({"error": "أدخل نص الإعلان."}, status=status.HTTP_400_BAD_REQUEST)
        # إعلان واحد نشط فقط: عطّل الباقي ثم أنشئ الجديد
        SiteAnnouncement.objects.filter(is_active=True).update(is_active=False)
        a = SiteAnnouncement.objects.create(message=msg, is_active=True, created_by=request.user)
        return Response(
            {"id": a.id, "message": a.message, "is_active": bool(a.is_active), "created_at": a.created_at},
            status=status.HTTP_201_CREATED,
        )


class PrimaryAdminAnnouncementDeleteView(APIView):
    permission_classes = [PrimaryAdminPermission]

    def delete(self, request, pk):
        a = get_object_or_404(SiteAnnouncement, pk=pk)
        a.is_active = False
        a.save(update_fields=["is_active"])
        return Response({"message": "deleted"})


class AdminNotificationEventsView(APIView):
    """إشعارات داخل التطبيق للمدراء — ترجع الأحداث الجديدة + عدادات الطلبات."""

    permission_classes = [AdminRequiredPermission]

    def get(self, request):
        since_id = request.query_params.get("since_id")
        try:
            since_id_n = int(since_id) if since_id not in (None, "", "null") else None
        except (TypeError, ValueError):
            since_id_n = None

        qs = AdminNotificationEvent.objects.all()
        if since_id_n is not None and since_id_n > 0:
            qs = qs.filter(id__gt=since_id_n)

        out = []
        for e in qs.order_by("id")[:50]:
            out.append(
                {
                    "id": e.id,
                    "event_type": e.event_type,
                    "event_type_label": e.get_event_type_display(),
                    "title": e.title,
                    "body": e.body,
                    "created_at": e.created_at,
                    "related_app": e.related_app,
                    "related_id": e.related_id,
                }
            )

        latest = AdminNotificationEvent.objects.order_by("-id").first()
        latest_id = latest.id if latest else 0

        return Response({"results": out, "latest_id": latest_id})


class AdminPushPublicKeyView(APIView):
    """يرجع VAPID public key للواجهة للاشتراك بـ Push."""

    permission_classes = [AllowAny]

    def get(self, request):
        key = (os.getenv("VAPID_PUBLIC_KEY") or "").strip()
        if not key:
            return Response({"error": "VAPID_PUBLIC_KEY غير مضبوط على الخادم."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({"publicKey": key})


class AdminPushSubscribeView(APIView):
    """تسجيل/تحديث اشتراك Push للمدير."""

    permission_classes = [AdminRequiredPermission]

    def post(self, request):
        sub = request.data.get("subscription") or request.data
        endpoint = (sub.get("endpoint") or "").strip() if isinstance(sub, dict) else ""
        keys = sub.get("keys") if isinstance(sub, dict) else None
        p256dh = (keys.get("p256dh") or "").strip() if isinstance(keys, dict) else ""
        auth = (keys.get("auth") or "").strip() if isinstance(keys, dict) else ""
        if not endpoint or not p256dh or not auth:
            return Response({"error": "بيانات الاشتراك غير مكتملة."}, status=status.HTTP_400_BAD_REQUEST)
        ua = (request.headers.get("User-Agent") or "")[:240]
        row, _created = AdminWebPushSubscription.objects.update_or_create(
            endpoint=endpoint,
            defaults={"user": request.user, "p256dh": p256dh, "auth": auth, "user_agent": ua},
        )
        return Response({"ok": True, "id": row.id})


class AdminPushUnsubscribeView(APIView):
    """حذف اشتراك Push (عند تعطيل الإشعارات أو تغيير الجهاز)."""

    permission_classes = [AdminRequiredPermission]

    def post(self, request):
        sub = request.data.get("subscription") or request.data
        endpoint = (sub.get("endpoint") or "").strip() if isinstance(sub, dict) else ""
        if not endpoint:
            return Response({"error": "endpoint مطلوب."}, status=status.HTTP_400_BAD_REQUEST)
        AdminWebPushSubscription.objects.filter(endpoint=endpoint).delete()
        return Response({"ok": True})


def _send_admin_web_push(title: str, body: str, url: str = "/admin"):
    """يرسل Push لكل اشتراكات المدراء. فشل جهاز لا يوقف الباقي."""

    if webpush is None:
        return

    public_key = (os.getenv("VAPID_PUBLIC_KEY") or "").strip()
    private_key = (os.getenv("VAPID_PRIVATE_KEY") or "").strip()
    subject = (os.getenv("VAPID_SUBJECT") or "mailto:admin@radar.local").strip()
    if not public_key or not private_key:
        return

    payload = {"title": title or "رادار — إشعار", "body": body or "", "url": url or "/admin"}
    vapid_claims = {"sub": subject}

    for s in AdminWebPushSubscription.objects.select_related("user").all()[:500]:
        try:
            webpush(
                subscription_info={"endpoint": s.endpoint, "keys": {"p256dh": s.p256dh, "auth": s.auth}},
                data=json.dumps(payload),
                vapid_private_key=private_key,
                vapid_claims=vapid_claims,
            )
        except WebPushException:
            # endpoint expired -> remove
            AdminWebPushSubscription.objects.filter(endpoint=s.endpoint).delete()
        except Exception:
            # ignore other failures
            continue
