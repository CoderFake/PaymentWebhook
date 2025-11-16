from django.contrib import admin
from .models import PaymentSession


@admin.register(PaymentSession)
class PaymentSessionAdmin(admin.ModelAdmin):
    list_display = ['order_id', 'username', 'amount', 'status', 'created_at', 'expired_at']
    list_filter = ['status', 'created_at']
    search_fields = ['order_id', 'username', 'description']
    readonly_fields = ['created_at', 'paid_at']

