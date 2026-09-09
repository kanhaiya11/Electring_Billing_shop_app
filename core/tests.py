from decimal import Decimal
from django.test import TestCase
from .models import *
from .services import create_sale, add_payment

class BillingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(mobile="9876543210", password="password123", name="Owner")
        self.shop = self.user.shop if hasattr(self.user, "shop") else Shop.objects.create(owner=self.user, shop_name="Test Shop")
        self.category = Category.objects.create(shop=self.shop, name="Wires")
        self.product = Product.objects.create(shop=self.shop, category=self.category, name="Wire", sku="W-1", purchase_price=80, selling_price=100, gst_percentage=18, current_stock=10)
        self.customer = Customer.objects.create(shop=self.shop, name="Rahul", mobile="9999999999")
    def test_sale_reduces_stock_and_partial_payment_can_be_added(self):
        sale = create_sale(shop=self.shop, user=self.user, customer=self.customer, items=[{"product_id": self.product.pk, "quantity": 2}], paid_amount=50)
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, Decimal("8"))
        self.assertEqual(sale.payment_status, "PARTIAL")
        add_payment(sale=sale, user=self.user, amount=sale.remaining_amount, payment_method="CASH")
        sale.refresh_from_db()
        self.assertEqual(sale.payment_status, "PAID")
