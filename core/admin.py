from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import *

class MobileUserAdmin(UserAdmin):
    ordering = ("mobile",)
    list_display = ("mobile", "name", "email", "is_staff", "is_active")
    fieldsets = ((None, {"fields": ("mobile", "password")}), ("Profile", {"fields": ("name", "email")}), ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}))
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("mobile", "name", "password1", "password2")} ),)

admin.site.register(User, MobileUserAdmin)
for model in [Shop, Category, Product, ProductPriceHistory, Customer, SupplierPurchase, PurchaseItem, Sale, SaleItem, Payment, StockTransaction, AuditLog]:
    admin.site.register(model)
