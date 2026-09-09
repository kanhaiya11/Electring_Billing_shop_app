from django.contrib.auth import authenticate
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from .models import *

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "name", "mobile", "email"]

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    class Meta:
        model = User
        fields = ["name", "mobile", "email", "password"]
    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        Shop.objects.create(owner=user, shop_name=f"{user.name}'s Shop", phone=user.mobile, email=user.email)
        return user

class LoginSerializer(serializers.Serializer):
    mobile = serializers.CharField()
    password = serializers.CharField(write_only=True)
    def validate(self, attrs):
        user = authenticate(mobile=attrs["mobile"], password=attrs["password"])
        if not user:
            raise serializers.ValidationError("Invalid mobile or password")
        refresh = RefreshToken.for_user(user)
        return {"user": UserSerializer(user).data, "tokens": {"refresh": str(refresh), "access": str(refresh.access_token)}}

class ShopSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shop
        exclude = ["owner"]

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        exclude = ["shop"]

class ProductSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(required=False, allow_null=True)
    class Meta:
        model = Product
        exclude = ["shop"]

class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        exclude = ["shop"]

class SaleItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = SaleItem
        fields = ["product", "product_name_snapshot", "quantity", "unit_price", "purchase_price_snapshot", "discount", "gst_percentage", "taxable_amount", "gst_amount", "total_amount"]

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ["id", "sale", "customer", "amount", "payment_method", "payment_date", "reference_number", "notes"]
        read_only_fields = ["id", "customer", "payment_date"]

class SaleSerializer(serializers.ModelSerializer):
    items = SaleItemSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)
    shop = ShopSerializer(read_only=True)
    class Meta:
        model = Sale
        fields = "__all__"
        read_only_fields = ["shop", "created_by"]
