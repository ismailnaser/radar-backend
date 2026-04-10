from django import forms
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import AdminUserCreationForm
from django.utils.translation import gettext_lazy as _

User = get_user_model()

if admin.site.is_registered(User):
    admin.site.unregister(User)


class CustomAdminUserCreationForm(AdminUserCreationForm):
    phone_number = forms.CharField(label=_('رقم الهاتف'), max_length=20)

    class Meta(AdminUserCreationForm.Meta):
        model = User

    def save(self, commit=True):
        user = super().save(commit=False)
        user.phone_number = self.cleaned_data['phone_number']
        if commit:
            user.save()
            if hasattr(self, 'save_m2m'):
                self.save_m2m()
        return user


@admin.register(User)
class CustomUserAdmin(DjangoUserAdmin):
    """
    تعديل كلمة مرور أي مستخدم دون المعرفة السابقة:
    من قائمة المستخدمين → افتح المستخدم → في حقل «كلمة المرور» اضغط الرابط
    «هذا النموذج» / «تغيير كلمة المرور» للانتقال إلى صفحة تعيين كلمة جديدة فقط (بدون الحقل القديم).
    """

    add_form = CustomAdminUserCreationForm
    list_display = (
        'username',
        'phone_number',
        'email',
        'user_type',
        'is_primary_admin',
        'is_staff',
        'is_active',
    )
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'user_type', 'is_primary_admin', 'is_whatsapp_verified')
    search_fields = ('username', 'phone_number', 'first_name', 'last_name', 'email')
    ordering = ('username',)

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('معلومات شخصية'), {'fields': ('first_name', 'last_name', 'email', 'phone_number')}),
        (
            _('نوع الحساب والتحقق'),
            {'fields': ('user_type', 'is_primary_admin', 'is_whatsapp_verified', 'otp_code', 'otp_expiry')},
        ),
        (_('صلاحيات'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        (_('تواريخ مهمة'), {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (
            None,
            {
                'classes': ('wide',),
                'fields': ('username', 'phone_number', 'usable_password', 'password1', 'password2'),
            },
        ),
    )
