from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from orders.models import Cart, CartItem, VisitorStat
from products.models import Favorite, Product, SponsoredAd, StoreFavorite, Subscription
from stores.models import (
    Category,
    CommunityServiceCategory,
    CommunityServicePoint,
    Service,
    StoreProfile,
    StoreRating,
)


User = get_user_model()

STORE_NAMES_AR = [
    "سوق المدينة",
    "مخبز الياسمين",
    "عطارة البركة",
    "مكتبة الفارس",
    "صيدلية الشفاء",
    "ألبان الريف",
    "حلويات السلطان",
    "خضار وثمار",
    "ملحمة الكرم",
    "عطور الندى",
    "بيت القهوة",
    "وردة الشام",
    "أدوات المنزل",
    "ركن الهدايا",
    "مفروشات الهناء",
    "الإلكترونيات الحديثة",
    "سوبر ماركت النخيل",
    "أقمشة النور",
    "ألعاب الأطفال",
    "المنظفات الذهبية",
    "بقالة الحارة",
    "محل الدراجات",
    "مستلزمات المدارس",
    "محمصة البن",
    "الملابس العائلية",
    "إكسسوارات الجوال",
    "معرض الأحذية",
    "الأدوات الصحية",
    "سوق الخيرات",
    "متجر التوفير",
]

PRODUCT_NAMES_AR = [
    "خبز طازج",
    "قهوة عربية",
    "شاي أخضر",
    "عسل طبيعي",
    "جبنة بلدية",
    "لبنة",
    "زيت زيتون",
    "تمر مجدول",
    "سكر",
    "أرز",
    "معكرونة",
    "بهارات مشكلة",
    "صابون سائل",
    "مناديل ورقية",
    "شامبو",
    "مزيل عرق",
    "كريم مرطب",
    "فرشاة أسنان",
    "لعبة تركيب",
    "دفتر 100 ورقة",
    "قلم حبر",
    "شاحن سريع",
    "سماعة بلوتوث",
    "حافظة هاتف",
    "مصباح LED",
    "حذاء رياضي",
    "قميص قطني",
    "جاكيت شتوي",
    "بطانية",
    "طقم فناجين",
]

AD_TITLES_PRODUCT_AR = [
    "خصم اليوم",
    "عرض الأسبوع",
    "تخفيضات محدودة",
    "وصل حديثاً",
    "عرض التوفير",
    "أفضل سعر",
]

AD_TITLES_STANDALONE_AR = [
    "افتتاح فرع جديد",
    "شحن مجاني",
    "خدمة توصيل سريعة",
    "عروض نهاية الأسبوع",
    "كوبونات خصم",
    "هدية مع كل طلب",
]


@dataclass(frozen=True)
class DemoUsers:
    admin: User
    shopper: User


class Command(BaseCommand):
    help = "Seed demo data for all main sections (users/stores/products/orders)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete previously created demo data (by demo usernames/store names) before seeding.",
        )
        parser.add_argument("--stores", type=int, default=30)
        parser.add_argument("--products", type=int, default=30)
        parser.add_argument("--ads-product", type=int, default=30)
        parser.add_argument("--ads-standalone", type=int, default=30)

    @transaction.atomic
    def handle(self, *args, **options):
        reset: bool = bool(options["reset"])
        stores_count: int = int(options["stores"])
        products_count: int = int(options["products"])
        ads_product_count: int = int(options["ads_product"])
        ads_standalone_count: int = int(options["ads_standalone"])

        if reset:
            self._reset_demo_data()

        demo_users = self._ensure_users()
        categories = self._ensure_store_categories()
        stores = self._ensure_stores(stores_count, categories)
        products = self._ensure_products_across_stores(stores, total=products_count)
        self._ensure_store_ratings(stores, demo_users.shopper)
        self._ensure_favorites(demo_users.shopper, stores, products)
        self._ensure_sponsored_ads_across_stores(
            stores,
            products,
            total_product_ads=ads_product_count,
            total_standalone_ads=ads_standalone_count,
        )
        self._ensure_subscriptions(stores)
        self._ensure_legacy_services()
        self._ensure_community_services(demo_users.shopper, demo_users.admin)
        self._ensure_cart(demo_users.shopper, products)
        self._ensure_visitor_stats(stores)

        self.stdout.write(self.style.SUCCESS("Demo data seeded successfully."))
        self.stdout.write("Accounts created/ensured:")
        self.stdout.write("  admin    username=ismail       password=123456      phone=+970590000001")
        self.stdout.write("  shopper  username=demo_shopper  password=demo12345  phone=+970590000003")
        self.stdout.write(f"Stores ensured: {len(stores)} | Products ensured: {len(products)}")

    def _reset_demo_data(self) -> None:
        # Only remove objects we can confidently identify as demo.
        demo_usernames = (
            ["ismail", "demo_admin", "demo_shopper", "demo_merchant"]
            + [f"demo_merchant_{i:02d}" for i in range(1, 51)]
        )

        # Store-related
        StoreRating.objects.filter(shopper__username__in=demo_usernames).delete()
        Favorite.objects.filter(user__username__in=demo_usernames).delete()
        StoreFavorite.objects.filter(user__username__in=demo_usernames).delete()
        CartItem.objects.filter(cart__user__username__in=demo_usernames).delete()
        Cart.objects.filter(user__username__in=demo_usernames).delete()

        # Community services
        CommunityServicePoint.objects.filter(submitted_by__username__in=demo_usernames).delete()
        Service.objects.filter(name__startswith="خدمة تجريبية").delete()

        # Products/ads/subscription/store
        SponsoredAd.objects.filter(store__user__username__in=demo_usernames).delete()
        Product.objects.filter(store__user__username__in=demo_usernames).delete()
        Subscription.objects.filter(store__user__username__in=demo_usernames).delete()
        VisitorStat.objects.filter(store__user__username__in=demo_usernames).delete()
        StoreProfile.objects.filter(user__username__in=demo_usernames).delete()

        # Categories
        Category.objects.filter(name__startswith="قسم تجريبي").delete()
        # Legacy demo objects from older seeders
        Category.objects.filter(name__in=["Demo Category"]).delete()
        StoreProfile.objects.filter(store_name__in=["Demo Store"]).delete()
        CommunityServiceCategory.objects.filter(slug__in=["demo-water", "demo-institution"]).delete()

        # Users last
        User.objects.filter(username__in=demo_usernames).delete()

    def _ensure_users(self) -> DemoUsers:
        admin = self._get_or_create_user(
            username="ismail",
            phone_number="+970590000001",
            user_type="admin",
            password="123456",
            is_staff=True,
            is_superuser=True,
            is_primary_admin=True,
        )
        # حساب قديم من نسخ سابقة من السيدر
        User.objects.filter(username="demo_admin").delete()
        shopper = self._get_or_create_user(
            username="demo_shopper",
            phone_number="+970590000003",
            user_type="shopper",
            password="demo12345",
        )
        return DemoUsers(admin=admin, shopper=shopper)

    def _get_or_create_user(
        self,
        *,
        username: str,
        phone_number: str,
        user_type: str,
        password: str = "demo12345",
        **extra_fields,
    ):
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "phone_number": phone_number,
                "user_type": user_type,
                **extra_fields,
            },
        )
        changed = False
        if user.phone_number != phone_number:
            user.phone_number = phone_number
            changed = True
        if getattr(user, "user_type", None) != user_type:
            user.user_type = user_type
            changed = True
        for k, v in extra_fields.items():
            if hasattr(user, k) and getattr(user, k) != v:
                setattr(user, k, v)
                changed = True

        if created or not user.check_password(password):
            user.set_password(password)
            changed = True

        if changed:
            user.save()
        return user

    def _ensure_store_categories(self) -> list[Category]:
        # Keep a small list of categories to spread stores across them.
        names = [
            "قسم تجريبي - أغذية",
            "قسم تجريبي - منازل",
            "قسم تجريبي - عناية",
            "قسم تجريبي - مدارس",
            "قسم تجريبي - إلكترونيات",
        ]
        out: list[Category] = []
        for n in names:
            c, _ = Category.objects.get_or_create(name=n)
            out.append(c)
        return out

    def _ensure_stores(self, count: int, categories: list[Category]) -> list[StoreProfile]:
        stores: list[StoreProfile] = []
        base_lat = 31.50
        base_lng = 34.46
        for i in range(1, count + 1):
            username = f"demo_merchant_{i:02d}"
            # Keep demo merchant phone numbers unique and بعيد عن أرقام admin/shopper
            phone = f"+970591{i:06d}"  # +970591000001 ...
            merchant = self._get_or_create_user(
                username=username,
                phone_number=phone,
                user_type="merchant",
                password="demo12345",
            )

            name = STORE_NAMES_AR[(i - 1) % len(STORE_NAMES_AR)]
            # keep name unique-ish if list repeats
            store_name = name if i <= len(STORE_NAMES_AR) else f"{name} {i}"
            cat = categories[(i - 1) % len(categories)]
            store, _ = StoreProfile.objects.get_or_create(
                user=merchant,
                defaults={
                    "store_name": store_name,
                    "description": "متجر تجريبي ببيانات مفهومة للتجربة.",
                    "category": cat,
                    "latitude": base_lat + (i * 0.002),
                    "longitude": base_lng + (i * 0.002),
                    "location_address": f"غزة - حي تجريبي رقم {i}",
                    "contact_whatsapp": phone.replace("+", "").replace(" ", ""),
                    "store_features": ["توصيل", "دفع عند الاستلام", "خصومات أسبوعية"],
                    "business_hours_note": "يومياً 9:00 - 17:00",
                    "business_hours_weekly": {
                        "0": [{"start": "09:00", "end": "17:00"}],
                        "1": [{"start": "09:00", "end": "17:00"}],
                        "2": [{"start": "09:00", "end": "17:00"}],
                        "3": [{"start": "09:00", "end": "17:00"}],
                        "4": [{"start": "09:00", "end": "17:00"}],
                        "5": [],
                        "6": [],
                    },
                },
            )
            if store.category_id != cat.id:
                store.category = cat
                store.save(update_fields=["category"])
            stores.append(store)
        return stores

    def _ensure_products_across_stores(self, stores: list[StoreProfile], *, total: int) -> list[Product]:
        if total <= 0 or not stores:
            return []
        products: list[Product] = []
        # Round-robin across stores so the map/home shows multiple stores with items.
        for i in range(1, total + 1):
            store = stores[(i - 1) % len(stores)]
            base_name = PRODUCT_NAMES_AR[(i - 1) % len(PRODUCT_NAMES_AR)]
            name = base_name if i <= len(PRODUCT_NAMES_AR) else f"{base_name} ({i})"
            p, _ = Product.objects.get_or_create(
                store=store,
                name=name,
                defaults={
                    "price": Decimal("5.00") + Decimal(i),
                    "description": "منتج تجريبي ببيانات واضحة.",
                    "product_features": ["جودة ممتازة", "متوفر دائماً"],
                },
            )
            products.append(p)
        return products

    def _ensure_store_ratings(self, stores: list[StoreProfile], shopper: User) -> None:
        for idx, s in enumerate(stores, start=1):
            stars = 3 + (idx % 3)  # 3..5
            StoreRating.objects.update_or_create(
                store=s,
                shopper=shopper,
                defaults={"stars": stars},
            )

    def _ensure_favorites(self, shopper: User, stores: list[StoreProfile], products: Iterable[Product]) -> None:
        for s in stores[:5]:
            StoreFavorite.objects.get_or_create(user=shopper, store=s)
        for p in list(products)[:10]:
            Favorite.objects.get_or_create(user=shopper, product=p)

    def _ensure_sponsored_ads_across_stores(
        self,
        stores: list[StoreProfile],
        products: list[Product],
        *,
        total_product_ads: int,
        total_standalone_ads: int,
    ) -> None:
        now = timezone.now()

        # Product-linked ads
        for i in range(1, max(0, total_product_ads) + 1):
            if not products:
                break
            store = stores[(i - 1) % len(stores)]
            prod = products[(i - 1) % len(products)]
            base_title = AD_TITLES_PRODUCT_AR[(i - 1) % len(AD_TITLES_PRODUCT_AR)]
            title = f"{base_title} - {prod.name}"
            SponsoredAd.objects.get_or_create(
                store=store,
                title=title,
                defaults={
                    "product": prod,
                    "description": "إعلان ممول مرتبط بمنتج للتجربة.",
                    "product_price": prod.price,
                    "status": "active",
                    "approved_at": now,
                },
            )

        # Standalone ads (نشطة ومعتمدة لتظهر كإعلانات ممولة في الواجهة)
        for i in range(1, max(0, total_standalone_ads) + 1):
            store = stores[(i - 1) % len(stores)]
            base_title = AD_TITLES_STANDALONE_AR[(i - 1) % len(AD_TITLES_STANDALONE_AR)]
            title = f"{base_title} ({i})"
            SponsoredAd.objects.get_or_create(
                store=store,
                title=title,
                defaults={
                    "description": "إعلان ممول مستقل ببيانات مفهومة للتجربة.",
                    "product_price": Decimal("15.00") + Decimal(i),
                    "status": "active",
                    "approved_at": now,
                },
            )

    def _ensure_subscriptions(self, stores: list[StoreProfile]) -> None:
        for s in stores:
            Subscription.objects.get_or_create(
                store=s,
                defaults={
                    "end_date": timezone.now() + timezone.timedelta(days=30),
                    "is_active": True,
                },
            )

    def _ensure_legacy_services(self) -> None:
        """خدمات الجدول القديم Service (مسار /api/stores/services/ أو ما شابه)."""
        samples = [
            ("خدمة تجريبية — توصيل طوارئ", "توصيل سريع داخل المدينة (بيانات وهمية للعرض).", 31.50, 34.46),
            ("خدمة تجريبية — صيانة منزلية", "صيانة سباكة وكهرباء (بيانات وهمية للعرض).", 31.51, 34.47),
            ("خدمة تجريبية — نقل أثاث", "نقل وتركيب (بيانات وهمية للعرض).", 31.49, 34.45),
        ]
        for name, desc, lat, lng in samples:
            Service.objects.get_or_create(
                name=name,
                defaults={"description": desc, "latitude": lat, "longitude": lng},
            )

    def _ensure_community_services(self, submitter: User, reviewer: User) -> None:
        water_cat, _ = CommunityServiceCategory.objects.get_or_create(
            slug="demo-water",
            defaults={
                "name": "نقاط توزيع المياه (تجريبي)",
                "description_hint": "أضف نقطة توزيع مياه مع توضيح صلاحية الشرب.",
                "sort_order": 1,
                "is_active": True,
            },
        )
        inst_cat, _ = CommunityServiceCategory.objects.get_or_create(
            slug="demo-institution",
            defaults={
                "name": "مؤسسات مجتمعية (تجريبي)",
                "description_hint": "أضف مؤسسة محلية/عالمية/خيرية.",
                "sort_order": 2,
                "is_active": True,
            },
        )

        # نقاط معتمدة وقيد المراجعة (عناوين عربية)
        CommunityServicePoint.objects.get_or_create(
            category=water_cat,
            title="نقطة مياه الشفاء (تجريبي)",
            defaults={
                "detail_description": "نقطة توزيع مياه تجريبية مع صلاحية شرب معلنة.",
                "latitude": 31.51,
                "longitude": 34.47,
                "address_text": "غزة - حي الرمال - نقطة تجريبية",
                "water_is_potable": True,
                "status": CommunityServicePoint.STATUS_APPROVED,
                "is_hidden_by_admin": False,
                "submitted_by": submitter,
                "reviewed_by": reviewer,
                "reviewed_at": timezone.now(),
            },
        )

        CommunityServicePoint.objects.get_or_create(
            category=inst_cat,
            title="جمعية خيرية الأمل (تجريبي)",
            defaults={
                "detail_description": "مؤسسة مجتمعية تجريبية لاختبار الخريطة والوصف.",
                "latitude": 31.49,
                "longitude": 34.45,
                "address_text": "غزة - مؤسسة تجريبية",
                "institution_scope": CommunityServicePoint.INSTITUTION_CHARITY,
                "status": CommunityServicePoint.STATUS_APPROVED,
                "is_hidden_by_admin": False,
                "submitted_by": submitter,
                "reviewed_by": reviewer,
                "reviewed_at": timezone.now(),
            },
        )

        CommunityServicePoint.objects.get_or_create(
            category=inst_cat,
            title="طلب مراجعة — مركز شباب (تجريبي)",
            defaults={
                "detail_description": "نقطة قيد الموافقة لاختبار حالة الانتظار.",
                "latitude": 31.505,
                "longitude": 34.455,
                "address_text": "غزة - مركز شباب تجريبي",
                "institution_scope": CommunityServicePoint.INSTITUTION_LOCAL,
                "status": CommunityServicePoint.STATUS_PENDING,
                "is_hidden_by_admin": False,
                "submitted_by": submitter,
            },
        )

    def _ensure_cart(self, shopper: User, products: list[Product]) -> None:
        cart, _ = Cart.objects.get_or_create(user=shopper, name="سلة تجريبية")
        CartItem.objects.filter(cart=cart).delete()
        for p in products[:4]:
            CartItem.objects.create(cart=cart, product=p, quantity=1)

    def _ensure_visitor_stats(self, stores: list[StoreProfile]) -> None:
        today = timezone.localdate()
        for idx, s in enumerate(stores, start=1):
            VisitorStat.objects.update_or_create(
                store=s,
                date=today,
                defaults={"visitor_count": 10 + idx},
            )
