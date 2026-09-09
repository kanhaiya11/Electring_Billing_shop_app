from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.utils import timezone
from .models import AuditLog, Payment, Sale, SaleItem, StockTransaction, SupplierPurchase, PurchaseItem

TWOPLACES = Decimal("0.01")

def money(value):
    return Decimal(value).quantize(TWOPLACES, rounding=ROUND_HALF_UP)

def calculate_line(product, quantity, discount=Decimal("0")):
    taxable = money(product.selling_price * quantity - discount)
    gst = money(taxable * product.gst_percentage / Decimal("100"))
    return taxable, gst, money(taxable + gst)

def change_stock(product, quantity, transaction_type, user, reference=None, notes=""):
    quantity = Decimal(quantity)
    previous = product.current_stock
    new_stock = previous + quantity
    if new_stock < 0:
        raise ValueError(f"Insufficient stock for {product.name}")
    product.current_stock = new_stock
    product.save(update_fields=["current_stock", "updated_at"])
    StockTransaction.objects.create(product=product, transaction_type=transaction_type, quantity=quantity, previous_stock=previous, new_stock=new_stock, reference_type=reference.__class__.__name__ if reference else "", reference_id=reference.pk if reference else None, notes=notes, created_by=user)

@transaction.atomic
def create_sale(*, shop, user, customer, items, discount=Decimal("0"), paid_amount=Decimal("0"), payment_method="CASH", notes=""):
    locked_products = {}
    subtotal = Decimal("0")
    gst_total = Decimal("0")
    line_data = []
    for item in items:
        product = shop.products.select_for_update().get(pk=item["product_id"], is_active=True)
        quantity = Decimal(str(item["quantity"]))
        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero")
        locked_products[product.pk] = product
        taxable, gst, total = calculate_line(product, quantity)
        subtotal += taxable
        gst_total += gst
        line_data.append((product, quantity, taxable, gst, total))
    discount = Decimal(discount)
    taxable_amount = money(subtotal - discount)
    if taxable_amount < 0:
        raise ValueError("Discount cannot exceed subtotal")
    gst_total = money(taxable_amount * (gst_total / subtotal)) if subtotal else Decimal("0")
    total = money(taxable_amount + gst_total)
    paid_amount = money(paid_amount)
    if paid_amount < 0 or paid_amount > total:
        raise ValueError("Paid amount must be between zero and invoice total")
    year = timezone.localdate().year
    sequence = Sale.objects.filter(shop=shop, sale_date__year=year).select_for_update().count() + 1
    sale = Sale.objects.create(shop=shop, created_by=user, customer=customer, sale_date=timezone.localdate(), invoice_number=f"INV-{year}-{sequence:06d}", subtotal=money(subtotal), discount=discount, taxable_amount=taxable_amount, gst_amount=gst_total, cgst=money(gst_total / 2), sgst=money(gst_total / 2), total_amount=total, paid_amount=paid_amount, remaining_amount=money(total - paid_amount), payment_status="PAID" if paid_amount == total else "PARTIAL" if paid_amount else "UNPAID", payment_method=payment_method, notes=notes)
    for product, quantity, taxable, gst, line_total in line_data:
        SaleItem.objects.create(sale=sale, product=product, product_name_snapshot=product.name, quantity=quantity, unit_price=product.selling_price, purchase_price_snapshot=product.purchase_price, gst_percentage=product.gst_percentage, taxable_amount=taxable, gst_amount=gst, total_amount=line_total)
        change_stock(product, -quantity, "SALE", user, sale)
    if paid_amount:
        Payment.objects.create(sale=sale, customer=customer, amount=paid_amount, payment_method=payment_method, created_by=user)
    AuditLog.objects.create(user=user, action="SALE_CREATED", model_name="Sale", object_id=sale.pk, description=sale.invoice_number)
    return sale

@transaction.atomic
def add_payment(*, sale, user, amount, payment_method, reference_number="", notes=""):
    amount = money(amount)
    if amount <= 0 or amount > sale.remaining_amount:
        raise ValueError("Payment must be positive and cannot exceed outstanding amount")
    payment = Payment.objects.create(sale=sale, customer=sale.customer, amount=amount, payment_method=payment_method, reference_number=reference_number, notes=notes, created_by=user)
    sale.paid_amount = money(sale.paid_amount + amount)
    sale.remaining_amount = money(sale.total_amount - sale.paid_amount)
    sale.payment_status = "PAID" if not sale.remaining_amount else "PARTIAL"
    sale.save(update_fields=["paid_amount", "remaining_amount", "payment_status", "updated_at"])
    AuditLog.objects.create(user=user, action="PAYMENT_ADDED", model_name="Payment", object_id=payment.pk, description=f"Payment for {sale.invoice_number}")
    return payment

@transaction.atomic
def create_purchase(*, shop, user, supplier_name, purchase_date, items, discount=Decimal("0"), paid_amount=Decimal("0"), **extra):
    subtotal = Decimal("0")
    gst_total = Decimal("0")
    purchase = SupplierPurchase.objects.create(shop=shop, created_by=user, supplier_name=supplier_name, purchase_date=purchase_date, discount=discount, **extra)
    for item in items:
        product = shop.products.select_for_update().get(pk=item["product_id"])
        quantity = Decimal(str(item["quantity"]))
        price = Decimal(str(item.get("purchase_price", product.purchase_price)))
        taxable = money(quantity * price)
        gst = money(taxable * product.gst_percentage / Decimal("100"))
        total = money(taxable + gst)
        PurchaseItem.objects.create(purchase=purchase, product=product, quantity=quantity, purchase_price=price, gst_percentage=product.gst_percentage, gst_amount=gst, total=total)
        change_stock(product, quantity, "PURCHASE", user, purchase)
        subtotal += taxable
        gst_total += gst
    purchase.subtotal = money(subtotal)
    purchase.gst_amount = money(gst_total)
    purchase.total_amount = money(subtotal - Decimal(discount) + gst_total)
    purchase.paid_amount = money(paid_amount)
    purchase.remaining_amount = money(purchase.total_amount - purchase.paid_amount)
    purchase.payment_status = "PAID" if not purchase.remaining_amount else "PARTIAL" if purchase.paid_amount else "UNPAID"
    purchase.save()
    AuditLog.objects.create(user=user, action="PURCHASE_CREATED", model_name="SupplierPurchase", object_id=purchase.pk)
    return purchase
