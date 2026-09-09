from decimal import Decimal
from django.db import models
from django.db.models import Q, Sum, Count
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status, viewsets, generics, mixins
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from .models import *
from .permissions import IsShopUser
from .serializers import *
from .services import create_sale, add_payment, change_stock, create_purchase

class ApiMixin:
    def ok(self, data, message="Success", status_code=status.HTTP_200_OK):
        return Response({"success": True, "message": message, "data": data}, status=status_code)

class RegisterView(ApiMixin, generics.CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer
    def create(self, request, *args, **kwargs):
        user = self.get_serializer(data=request.data); user.is_valid(raise_exception=True); instance = user.save()
        refresh = RefreshToken.for_user(instance)
        return self.ok({"user": UserSerializer(instance).data, "tokens": {"refresh": str(refresh), "access": str(refresh.access_token)}}, "Registration successful", 201)

class LoginView(ApiMixin, generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = LoginSerializer
    def post(self, request):
        serializer = self.get_serializer(data=request.data); serializer.is_valid(raise_exception=True); return self.ok(serializer.validated_data, "Login successful")

class MeView(ApiMixin, generics.RetrieveAPIView):
    serializer_class = UserSerializer
    def get(self, request): return self.ok(self.get_serializer(request.user).data)

class ShopView(ApiMixin, generics.RetrieveUpdateAPIView):
    serializer_class = ShopSerializer
    def get_object(self): return self.request.user.shop
    def retrieve(self, request, *args, **kwargs): return self.ok(self.get_serializer(self.get_object()).data)

class OwnedViewSet(ApiMixin, viewsets.ModelViewSet):
    permission_classes = [IsShopUser]
    owner_field = "shop"
    def perform_create(self, serializer): serializer.save(shop=self.request.user.shop)
    def get_queryset(self): return self.model.objects.filter(shop=self.request.user.shop)
    def list(self, request, *args, **kwargs): return self.ok(super().list(request, *args, **kwargs).data)

class CategoryViewSet(OwnedViewSet):
    model = Category; serializer_class = CategorySerializer; search_fields = ["name", "description"]; ordering_fields = ["name", "created_at"]
class ProductViewSet(OwnedViewSet):
    model = Product; serializer_class = ProductSerializer; search_fields = ["name", "sku", "barcode", "brand"]; ordering_fields = ["name", "selling_price", "created_at"]
    filterset_fields = ["category", "brand", "is_active"]
    @action(detail=False, url_path="low-stock")
    def low_stock(self, request): return self.ok(ProductSerializer(self.get_queryset().filter(current_stock__lte=models.F("minimum_stock")), many=True, context={"request": request}).data)
    @action(detail=False, url_path=r"barcode/(?P<barcode>[^/.]+)")
    def barcode(self, request, barcode=None): return self.ok(ProductSerializer(self.get_queryset().get(barcode=barcode), context={"request": request}).data)
class CustomerViewSet(OwnedViewSet):
    model = Customer; serializer_class = CustomerSerializer; search_fields = ["name", "mobile", "email"]; ordering_fields = ["name", "created_at"]
    @action(detail=False)
    def outstanding(self, request):
        rows = self.get_queryset().annotate(total_billed=Sum("sales__total_amount"), total_paid=Sum("sales__paid_amount"), total_remaining=Sum("sales__remaining_amount")).filter(total_remaining__gt=0)
        return self.ok([{**CustomerSerializer(row).data, "total_billed": row.total_billed or 0, "total_paid": row.total_paid or 0, "total_remaining": row.total_remaining or 0} for row in rows])
    @action(detail=True)
    def outstanding_detail(self, request, pk=None):
        customer = self.get_object(); sales = customer.sales.all(); return self.ok({"customer": CustomerSerializer(customer).data, "total_sales": sales.aggregate(v=Sum("total_amount"))["v"] or 0, "total_paid": sales.aggregate(v=Sum("paid_amount"))["v"] or 0, "total_remaining": sales.aggregate(v=Sum("remaining_amount"))["v"] or 0, "invoices": SaleSerializer(sales, many=True).data})
class SaleViewSet(ApiMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsShopUser]; serializer_class = SaleSerializer; search_fields = ["invoice_number", "customer__name", "customer__mobile"]; ordering_fields = ["sale_date", "created_at", "total_amount"]; filterset_fields = ["payment_status", "payment_method", "customer"]
    def get_queryset(self): return Sale.objects.filter(shop=self.request.user.shop).select_related("customer", "shop").prefetch_related("items", "payments")

    def create(self, request, *args, **kwargs):
        customer = Customer.objects.filter(pk=request.data.get("customer_id"), shop=request.user.shop).first() if request.data.get("customer_id") else None
        try:
            sale = create_sale(shop=request.user.shop, user=request.user, customer=customer, items=request.data.get("items", []), discount=request.data.get("discount", 0), paid_amount=request.data.get("paid_amount", 0), payment_method=request.data.get("payment_method", "CASH"), notes=request.data.get("notes", ""))
        except (ValueError, Product.DoesNotExist) as exc:
            return Response({"success": False, "message": str(exc), "errors": {}}, status=400)
        return self.ok(SaleSerializer(sale).data, "Sale created", 201)

    @action(detail=True, methods=["get"], url_path="invoice")
    def invoice(self, request, pk=None):
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from io import BytesIO
        sale = self.get_object(); buffer = BytesIO(); pdf = canvas.Canvas(buffer, pagesize=A4)
        pdf.setTitle(sale.invoice_number); pdf.drawString(40, 800, sale.shop.shop_name); pdf.drawString(40, 780, f"Invoice: {sale.invoice_number}")
        y = 740
        for item in sale.items.all():
            pdf.drawString(40, y, f"{item.product_name_snapshot} x {item.quantity} @ {item.unit_price} = {item.total_amount}"); y -= 18
        pdf.drawString(40, y - 10, f"Subtotal: {sale.subtotal}  GST: {sale.gst_amount}  Total: {sale.total_amount}")
        pdf.drawString(40, y - 28, f"Paid: {sale.paid_amount}  Remaining: {sale.remaining_amount}  Status: {sale.payment_status}"); pdf.save(); buffer.seek(0)
        return HttpResponse(buffer.getvalue(), content_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{sale.invoice_number}.pdf"'})

class PurchaseCreateView(ApiMixin, generics.CreateAPIView):
    serializer_class = SaleSerializer
    def create(self, request, *args, **kwargs):
        try:
            purchase = create_purchase(shop=request.user.shop, user=request.user, supplier_name=request.data["supplier_name"], purchase_date=request.data.get("purchase_date", timezone.localdate()), items=request.data.get("items", []), discount=request.data.get("discount", 0), paid_amount=request.data.get("paid_amount", 0), supplier_mobile=request.data.get("supplier_mobile", ""), invoice_number=request.data.get("invoice_number", ""), notes=request.data.get("notes", ""))
        except (ValueError, KeyError, Product.DoesNotExist) as exc:
            return Response({"success": False, "message": str(exc), "errors": {}}, status=400)
        return self.ok({"id": purchase.pk, "total_amount": purchase.total_amount, "remaining_amount": purchase.remaining_amount}, "Purchase created", 201)

class PaymentCreateView(ApiMixin, generics.CreateAPIView):
    serializer_class = PaymentSerializer
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data); serializer.is_valid(raise_exception=True)
        sale = Sale.objects.get(pk=serializer.validated_data["sale"].pk, shop=request.user.shop)
        try: payment = add_payment(sale=sale, user=request.user, **{key: serializer.validated_data[key] for key in ["amount", "payment_method", "reference_number", "notes"]})
        except ValueError as exc: return Response({"success": False, "message": str(exc), "errors": {}}, status=400)
        return self.ok(PaymentSerializer(payment).data, "Payment added", 201)

class SaleCreateView(ApiMixin, generics.CreateAPIView):
    serializer_class = SaleSerializer
    def create(self, request, *args, **kwargs):
        customer = Customer.objects.filter(pk=request.data.get("customer_id"), shop=request.user.shop).first() if request.data.get("customer_id") else None
        try: sale = create_sale(shop=request.user.shop, user=request.user, customer=customer, items=request.data.get("items", []), discount=request.data.get("discount", 0), paid_amount=request.data.get("paid_amount", 0), payment_method=request.data.get("payment_method", "CASH"), notes=request.data.get("notes", ""))
        except (ValueError, Product.DoesNotExist) as exc: return Response({"success": False, "message": str(exc), "errors": {}}, status=400)
        return self.ok(SaleSerializer(sale).data, "Sale created", 201)

@api_view(["GET"])
def dashboard(request):
    today = timezone.localdate(); sales = Sale.objects.filter(shop=request.user.shop); today_sales = sales.filter(sale_date=today)
    return Response({"success": True, "message": "Dashboard", "data": {"today": {"sales": today_sales.aggregate(v=Sum("total_amount"))["v"] or 0, "payments_received": today_sales.aggregate(v=Sum("paid_amount"))["v"] or 0}, "inventory": {"total_products": Product.objects.filter(shop=request.user.shop, is_active=True).count(), "low_stock_products": Product.objects.filter(shop=request.user.shop, current_stock__lte=models.F("minimum_stock")).count()}, "customers": {"total": Customer.objects.filter(shop=request.user.shop).count(), "outstanding_amount": sales.aggregate(v=Sum("remaining_amount"))["v"] or 0}}})

@api_view(["GET"])
def sales_report(request):
    sales = Sale.objects.filter(shop=request.user.shop)
    return Response({"success": True, "message": "Sales report", "data": {"invoice_count": sales.count(), "total_sales": sales.aggregate(v=Sum("total_amount"))["v"] or 0, "total_gst": sales.aggregate(v=Sum("gst_amount"))["v"] or 0, "total_discount": sales.aggregate(v=Sum("discount"))["v"] or 0, "total_paid": sales.aggregate(v=Sum("paid_amount"))["v"] or 0, "total_outstanding": sales.aggregate(v=Sum("remaining_amount"))["v"] or 0}})
