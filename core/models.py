from decimal import Decimal
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


class UserManager(BaseUserManager):
    def create_user(self, mobile, password=None, **extra):
        if not mobile:
            raise ValueError("Mobile is required")
        user = self.model(mobile=mobile, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, mobile, password=None, **extra):
        extra.update(is_staff=True, is_superuser=True)
        return self.create_user(mobile, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    name = models.CharField(max_length=150)
    mobile = models.CharField(max_length=15, unique=True, db_index=True)
    email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    objects = UserManager()
    USERNAME_FIELD = "mobile"
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.mobile


class TimeStamped(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        abstract = True


class Shop(TimeStamped):
    owner = models.OneToOneField(User, on_delete=models.CASCADE, related_name="shop")
    shop_name = models.CharField(max_length=200)
    shop_logo = models.ImageField(upload_to="shops/", blank=True, null=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    pincode = models.CharField(max_length=10, blank=True)
    gstin = models.CharField(max_length=15, blank=True)
    phone = models.CharField(max_length=15, blank=True)
    email = models.EmailField(blank=True)


class Category(TimeStamped):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="categories")
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["shop", "name"], name="unique_category_per_shop")]
        ordering = ["name"]


class Product(TimeStamped):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="products")
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    name = models.CharField(max_length=200)
    sku = models.CharField(max_length=80, db_index=True)
    barcode = models.CharField(max_length=80, blank=True, db_index=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="products/", blank=True, null=True)
    brand = models.CharField(max_length=100, blank=True)
    unit = models.CharField(max_length=30, default="piece")
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0"))])
    selling_price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0"))])
    gst_percentage = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))])
    opening_stock = models.DecimalField(max_digits=12, decimal_places=3, default=0, validators=[MinValueValidator(Decimal("0"))])
    current_stock = models.DecimalField(max_digits=12, decimal_places=3, default=0, validators=[MinValueValidator(Decimal("0"))])
    minimum_stock = models.DecimalField(max_digits=12, decimal_places=3, default=0, validators=[MinValueValidator(Decimal("0"))])
    is_active = models.BooleanField(default=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["shop", "sku"], name="unique_sku_per_shop")]
        indexes = [models.Index(fields=["shop", "name"]), models.Index(fields=["shop", "current_stock"])]


class ProductPriceHistory(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="price_history")
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2)
    selling_price = models.DecimalField(max_digits=12, decimal_places=2)
    gst_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    effective_from = models.DateTimeField()
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class Customer(TimeStamped):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="customers")
    name = models.CharField(max_length=150)
    mobile = models.CharField(max_length=15, db_index=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    gstin = models.CharField(max_length=15, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    class Meta:
        indexes = [models.Index(fields=["shop", "mobile"])]


class SupplierPurchase(TimeStamped):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="purchases")
    supplier_name = models.CharField(max_length=150)
    supplier_mobile = models.CharField(max_length=15, blank=True)
    invoice_number = models.CharField(max_length=80, blank=True)
    purchase_date = models.DateField()
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_status = models.CharField(max_length=15, default="UNPAID")
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    remaining_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)


class PurchaseItem(models.Model):
    purchase = models.ForeignKey(SupplierPurchase, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=12, decimal_places=3, validators=[MinValueValidator(Decimal("0.001"))])
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2)
    gst_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    gst_amount = models.DecimalField(max_digits=12, decimal_places=2)
    total = models.DecimalField(max_digits=12, decimal_places=2)


class Sale(TimeStamped):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="sales")
    invoice_number = models.CharField(max_length=30, db_index=True)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="sales", null=True, blank=True)
    sale_date = models.DateField()
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    taxable_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cgst = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sgst = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    igst = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    round_off = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    remaining_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_status = models.CharField(max_length=15, default="UNPAID", db_index=True)
    payment_method = models.CharField(max_length=20, default="CASH")
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["shop", "invoice_number"], name="unique_invoice_per_shop")]
        indexes = [models.Index(fields=["shop", "sale_date"]), models.Index(fields=["shop", "payment_status"])]


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    product_name_snapshot = models.CharField(max_length=200)
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    purchase_price_snapshot = models.DecimalField(max_digits=12, decimal_places=2)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gst_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    taxable_amount = models.DecimalField(max_digits=12, decimal_places=2)
    gst_amount = models.DecimalField(max_digits=12, decimal_places=2)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)


class Payment(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="payments")
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="payments", null=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    payment_method = models.CharField(max_length=20)
    payment_date = models.DateTimeField(auto_now_add=True)
    reference_number = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)


class StockTransaction(models.Model):
    TYPES = [(value, value) for value in ["OPENING", "PURCHASE", "SALE", "SALE_RETURN", "PURCHASE_RETURN", "ADJUSTMENT", "DAMAGE", "STOCK_CORRECTION"]]
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="stock_transactions")
    transaction_type = models.CharField(max_length=25, choices=TYPES)
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    previous_stock = models.DecimalField(max_digits=12, decimal_places=3)
    new_stock = models.DecimalField(max_digits=12, decimal_places=3)
    reference_type = models.CharField(max_length=50, blank=True)
    reference_id = models.PositiveBigIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class AuditLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=50)
    model_name = models.CharField(max_length=100)
    object_id = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
