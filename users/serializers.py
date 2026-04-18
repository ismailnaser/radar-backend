import uuid

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from stores.models import Category, StoreProfile
from stores.subscription_visibility import create_trial_subscription_for_store

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            'id',
            'username',
            'email',
            'phone_number',
            'user_type',
            'is_whatsapp_verified',
            'is_primary_admin',
            'is_active',
            'merchant_profile_complete',
        )


class AdminAccountListSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            'id',
            'username',
            'phone_number',
            'is_primary_admin',
            'is_active',
            'date_joined',
        )


class AdminAccountCreateSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    phone_number = serializers.CharField(max_length=20)
    password = serializers.CharField(write_only=True)
    tier = serializers.ChoiceField(choices=('secondary', 'primary'))

    def validate_username(self, value):
        v = (value or '').strip()
        if len(v) < 6:
            raise serializers.ValidationError('اسم المستخدم يجب أن يكون 6 أحرف على الأقل.')
        if User.objects.filter(username__iexact=v).exists():
            raise serializers.ValidationError('اسم المستخدم مستخدم مسبقاً.')
        return v

    def validate_phone_number(self, value):
        v = (value or '').strip()
        if User.objects.filter(phone_number=v).exists():
            raise serializers.ValidationError('رقم الهاتف مسجّل مسبقاً.')
        return v

    def validate_password(self, value):
        pw = value or ''
        try:
            validate_password(pw)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return pw


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    merchant_profile_complete = serializers.BooleanField(read_only=True)
    store_name = serializers.CharField(write_only=True, required=False, allow_blank=True, max_length=200)
    location_address = serializers.CharField(write_only=True, required=False, allow_blank=True, max_length=2000)
    store_latitude = serializers.FloatField(required=False, allow_null=True, write_only=True)
    store_longitude = serializers.FloatField(required=False, allow_null=True, write_only=True)
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        required=False,
        allow_null=True,
        write_only=True,
    )

    class Meta:
        model = User
        fields = (
            'username',
            'phone_number',
            'password',
            'user_type',
            'merchant_profile_complete',
            'store_name',
            'location_address',
            'store_latitude',
            'store_longitude',
            'category',
        )
        extra_kwargs = {
            'phone_number': {'required': False, 'allow_blank': True},
        }

    def validate_username(self, value):
        v = (value or '').strip()
        if not v:
            raise serializers.ValidationError('اسم المستخدم مطلوب.')
        if len(v) < 6:
            raise serializers.ValidationError('اسم المستخدم يجب أن يكون 6 أحرف على الأقل.')
        if User.objects.filter(username__iexact=v).exists():
            raise serializers.ValidationError('اسم المستخدم مستخدم مسبقاً.')
        return v

    def validate_password(self, value):
        pw = value or ''
        try:
            validate_password(pw)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return pw

    def validate(self, attrs):
        if attrs.get('user_type') == 'admin':
            raise serializers.ValidationError({'user_type': 'لا يمكن إنشاء حساب مدير عبر التسجيل العام'})
        if attrs.get('user_type') == 'merchant':
            lat = attrs.get('store_latitude')
            lng = attrs.get('store_longitude')
            if lat is not None or lng is not None:
                if lat is None or lng is None:
                    raise serializers.ValidationError({
                        'store_latitude': 'زود خط العرض والطول معاً، أو احذف تحديد الموقع من الخريطة.',
                    })
                try:
                    lat_f = float(lat)
                    lng_f = float(lng)
                except (TypeError, ValueError):
                    raise serializers.ValidationError({'store_latitude': 'إحداثيات غير صالحة.'})
                if not (-90 <= lat_f <= 90) or not (-180 <= lng_f <= 180):
                    raise serializers.ValidationError({'store_latitude': 'نطاق الإحداثيات غير صالح.'})
                if abs(lat_f) < 0.25 and abs(lng_f) < 0.25:
                    raise serializers.ValidationError({
                        'store_latitude': 'حدد موقعاً صالحاً على الخريطة (ليس قريباً من 0،0).',
                    })
                attrs['store_latitude'] = lat_f
                attrs['store_longitude'] = lng_f
        return attrs

    def create(self, validated_data):
        store_name = (validated_data.pop('store_name', None) or '').strip()
        location_address = (validated_data.pop('location_address', None) or '').strip()
        category = validated_data.pop('category', None)
        store_lat = validated_data.pop('store_latitude', None)
        store_lng = validated_data.pop('store_longitude', None)
        phone = (validated_data.pop('phone_number', None) or '').strip()
        if not phone:
            # رقم داخلي فريد — التسجيل العام بدون جوال
            phone = f"r{uuid.uuid4().hex[:18]}"
        user = User.objects.create_user(
            username=validated_data['username'],
            phone_number=phone,
            user_type=validated_data.get('user_type', 'shopper'),
            password=validated_data['password'],
        )
        if user.user_type == 'merchant':
            provisional_name = store_name or f'متجر {user.username}'
            store = StoreProfile.objects.create(
                user=user,
                store_name=provisional_name,
                category=category,
                description='',
                location_address=location_address,
                latitude=store_lat,
                longitude=store_lng,
            )
            create_trial_subscription_for_store(store)
            user.merchant_profile_complete = False
            user.save(update_fields=['merchant_profile_complete'])
        else:
            user.merchant_profile_complete = True
            user.save(update_fields=['merchant_profile_complete'])
        return user

class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    تسجيل الدخول: اسم المستخدم في Django حسّاس لحالة الأحرف، وكثير من المستخدمين
    يكتبون Osama بدل osama أو يلصقون مسافات — نربط الإدخال بالحساب ثم نمرّر اسم المستخدم المخزّن لـ JWT.
    يمكن أيضاً إدخال رقم الهاتف المسجّل بدل اسم المستخدم.
    """

    def validate(self, attrs):
        username_field = self.username_field
        raw = (attrs.get(username_field) or '').strip()
        if raw:
            user_match = User.objects.filter(username__iexact=raw).first()
            if not user_match:
                user_match = User.objects.filter(phone_number=raw).first()
            if user_match:
                attrs = {**attrs, username_field: user_match.get_username()}

        # تعطيل المصادقة (كلمة المرور) لحسابات التاجر عند تسجيل الدخول:
        # إذا كان المستخدم تاجرًا، نصدر JWT مباشرة بدون التحقق من كلمة المرور.
        # ملاحظة: ما زلنا نرفض الحسابات غير النشطة.
        resolved_user = None
        if raw:
            resolved_user = (
                User.objects.filter(username__iexact=raw).first()
                or User.objects.filter(phone_number=raw).first()
            )
        if resolved_user and getattr(resolved_user, "user_type", None) == "merchant":
            if not getattr(resolved_user, "is_active", True):
                raise serializers.ValidationError("الحساب معطّل.")
            refresh = self.get_token(resolved_user)
            data = {
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            }
            self.user = resolved_user
        else:
            data = super().validate(attrs)

        user_data = UserSerializer(self.user).data
        u = self.user
        is_app_admin = (
            getattr(u, 'user_type', None) == 'admin' or u.is_superuser or u.is_staff
        )
        if is_app_admin:
            user_data['user_type'] = 'admin'
        user_data['is_primary_admin'] = bool(
            is_app_admin and (getattr(u, 'is_primary_admin', False) or u.is_superuser)
        )
        data['user'] = user_data
        return data


class ChangeUsernameSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)

    def validate_username(self, value):
        v = (value or '').strip()
        if not v:
            raise serializers.ValidationError('اسم المستخدم مطلوب.')
        # امنع استخدام اسم مستخدم مستخدم مسبقاً (غير الحساب الحالي)
        user = self.context.get('request').user if self.context.get('request') else None
        qs = User.objects.filter(username__iexact=v)
        if user and getattr(user, 'id', None):
            qs = qs.exclude(id=user.id)
        if qs.exists():
            raise serializers.ValidationError('اسم المستخدم مستخدم مسبقاً.')
        return v


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, min_length=1)
    new_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            raise serializers.ValidationError('غير مصرح.')
        if not user.check_password(attrs.get('current_password', '')):
            raise serializers.ValidationError({'current_password': 'كلمة المرور الحالية غير صحيحة.'})
        if attrs.get('current_password') == attrs.get('new_password'):
            raise serializers.ValidationError({'new_password': 'كلمة المرور الجديدة يجب أن تختلف عن الحالية.'})
        try:
            validate_password(attrs.get('new_password') or '', user=user)
        except DjangoValidationError as e:
            raise serializers.ValidationError({'new_password': list(e.messages)})
        return attrs


class ChangeEmailSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        v = (value or '').strip().lower()
        if not v:
            raise serializers.ValidationError('البريد الإلكتروني مطلوب.')
        user = self.context.get('request').user if self.context.get('request') else None
        qs = User.objects.filter(email__iexact=v)
        if user and getattr(user, 'id', None):
            qs = qs.exclude(id=user.id)
        if qs.exists():
            raise serializers.ValidationError('هذا البريد الإلكتروني مستخدم مسبقاً.')
        return v
