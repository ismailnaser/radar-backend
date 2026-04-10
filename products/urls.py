from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    MerchantProductListCreateView, 
    MerchantProductUpdateDeleteView, 
    AdRequestView, 
    MerchantAdUpdateDeleteView,
    AdminSponsoredAdListView,
    AdminSponsoredAdDetailView,
    AdminSubscriptionRenewalListView,
    AdminAdSetStatusView,
    SubscriptionStatusView,
    MerchantSubscriptionRenewalRequestListCreateView,
    AdminSubscriptionRenewalRequestApproveView,
    AdminSubscriptionRenewalRequestRejectView,
    AdminPendingCountsView,
    PublicProductListView,
    PublicAdListView,
    FavoriteViewSet,
    StoreFavoriteViewSet,
    AdminFinanceTransfersView,
)

router = DefaultRouter()
router.register(r'favorites', FavoriteViewSet, basename='favorite')
router.register(r'store-favorites', StoreFavoriteViewSet, basename='storefavorite')

urlpatterns = [
    path('merchant/products/', MerchantProductListCreateView.as_view(), name='merchant_product_list'),
    path('merchant/products/<int:pk>/', MerchantProductUpdateDeleteView.as_view(), name='merchant_product_detail'),
    path('merchant/ads/', AdRequestView.as_view(), name='merchant_ad_request'),
    path('merchant/ads/<int:pk>/', MerchantAdUpdateDeleteView.as_view(), name='merchant_ad_detail'),
    path('admin/pending-counts/', AdminPendingCountsView.as_view(), name='admin_pending_counts'),
    path('admin/ads/', AdminSponsoredAdListView.as_view(), name='admin_ad_list'),
    path('admin/ads/<int:pk>/set-status/', AdminAdSetStatusView.as_view(), name='admin_ad_set_status'),
    path('admin/ads/<int:pk>/', AdminSponsoredAdDetailView.as_view(), name='admin_ad_detail'),
    path('merchant/subscription/', SubscriptionStatusView.as_view(), name='merchant_subscription_status'),
    path('merchant/subscription/renew/', MerchantSubscriptionRenewalRequestListCreateView.as_view(), name='merchant_subscription_renewal_requests'),
    path('admin/subscription/renew/', AdminSubscriptionRenewalListView.as_view(), name='admin_subscription_renew_list'),
    path('admin/subscription/renew/<int:pk>/approve/', AdminSubscriptionRenewalRequestApproveView.as_view(), name='admin_subscription_renew_approve'),
    path('admin/subscription/renew/<int:pk>/reject/', AdminSubscriptionRenewalRequestRejectView.as_view(), name='admin_subscription_renew_reject'),
    path('admin/finance/transfers/', AdminFinanceTransfersView.as_view(), name='admin_finance_transfers'),
    path('public/products/', PublicProductListView.as_view(), name='public_product_list'),
    path('public/ads/', PublicAdListView.as_view(), name='public_ad_list'),
    path('user/', include(router.urls)),
]
