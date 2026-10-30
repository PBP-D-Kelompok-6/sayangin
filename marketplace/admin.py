from django.contrib import admin

from .models import CartItem, Order, OrderItem, Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'seller', 'price', 'category', 'condition', 'city', 'is_sold')
    list_filter = ('category', 'condition', 'is_sold')
    search_fields = ('name',)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('code', 'buyer', 'seller', 'status', 'created_at')
    list_filter = ('status',)
    inlines = [OrderItemInline]


admin.site.register(CartItem)
