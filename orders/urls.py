from django.urls import path
from .views import (
    CartListCreateView,
    CartDetailView,
    CartItemCreateView,
    CartItemDetailView,
    MerchantStatsView,
    SharedCartPublicView,
)

urlpatterns = [
    path('carts/', CartListCreateView.as_view(), name='cart_list'),
    path('carts/share/<uuid:share_token>/', SharedCartPublicView.as_view(), name='cart_shared_public'),
    path('carts/<int:pk>/', CartDetailView.as_view(), name='cart_detail'),
    path('cart-items/', CartItemCreateView.as_view(), name='cart_item_create'),
    path('cart-items/<int:pk>/', CartItemDetailView.as_view(), name='cart_item_detail'),
    path('merchant-stats/', MerchantStatsView.as_view(), name='merchant_stats'),
]
