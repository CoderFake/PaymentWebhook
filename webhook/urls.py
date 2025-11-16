from django.urls import path
from . import views

app_name = 'webhook'

urlpatterns = [
    path('', views.payment_view, name='payment'),
    path('webhook/bank-transaction/', views.casso_webhook, name='casso_webhook'),
    path('api/payment-status/<str:order_id>/', views.check_payment_status, name='check_payment_status'),
    path('api/payment-info/<str:order_id>/', views.get_payment_info, name='get_payment_info'),
]

