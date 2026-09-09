from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView, TokenBlacklistView
from .views import *

router = DefaultRouter()
router.register("categories", CategoryViewSet, basename="category")
router.register("products", ProductViewSet, basename="product")
router.register("customers", CustomerViewSet, basename="customer")
router.register("sales", SaleViewSet, basename="sale")
urlpatterns = [
    path("auth/register/", RegisterView.as_view()), path("auth/login/", LoginView.as_view()), path("auth/me/", MeView.as_view()), path("auth/token/refresh/", TokenRefreshView.as_view()), path("auth/logout/", TokenBlacklistView.as_view()),
    path("shop/", ShopView.as_view()), path("sales/create/", SaleCreateView.as_view()), path("payments/", PaymentCreateView.as_view()), path("purchases/", PurchaseCreateView.as_view()), path("dashboard/", dashboard), path("reports/sales/", sales_report), path("", include(router.urls)),
]
