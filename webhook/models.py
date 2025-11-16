from django.db import models
from django.utils import timezone


class PaymentSession(models.Model):
    """
    Lưu trữ thông tin payment session để tracking
    """
    order_id = models.CharField(max_length=100, unique=True, db_index=True)
    amount = models.IntegerField()
    description = models.TextField()
    account_number = models.CharField(max_length=50)
    return_url = models.URLField()
    username = models.CharField(max_length=100, null=True, blank=True)
    payment_type = models.CharField(max_length=50)
    per_month_price = models.IntegerField(null=True, blank=True)
    
    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Chờ thanh toán'),
            ('paid', 'Đã thanh toán'),
            ('expired', 'Hết hạn'),
            ('cancelled', 'Đã hủy')
        ],
        default='pending'
    )
    
    # Casso webhook data
    casso_transaction_id = models.CharField(max_length=100, null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    expired_at = models.DateTimeField()
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Payment Session"
        verbose_name_plural = "Payment Sessions"
    
    def __str__(self):
        return f"{self.order_id} - {self.status}"
    
    def is_expired(self):
        return timezone.now() > self.expired_at
    
    def get_qr_url(self):
        """
        Generate VietQR URL
        https://img.vietqr.io/image/970416-{{account_number}}-compact2.png?amount={{amount}}&addInfo={{desc}}
        """
        return f"https://img.vietqr.io/image/970416-{self.account_number}-compact2.png?amount={self.amount}&addInfo={self.description}"

