from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.conf import settings
from datetime import datetime
from .models import PaymentSession
from .signature import SignatureManager
import logging
import json
import hmac
import hashlib

logger = logging.getLogger(__name__)


def handler404(request, exception=None):
    """
    Custom 404 handler
    """
    return render(request, 'webhook/404.html', {
        'error_message': 'Trang bạn đang tìm kiếm không tồn tại'
    }, status=404)


def verify_casso_signature_v2(payload_dict, signature_header, secret):
    """
    Verify Casso Webhook V2 signature
    Based on: https://github.com/CassoHQ/casso-webhook-v2-verify-signature
    
    Steps:
    1. Extract t (timestamp) and v1 (signature) from X-Casso-Signature header
    2. Sort webhook data by keys (A->Z)
    3. Convert sorted data to JSON string
    4. Create signed payload: timestamp + "." + json_string
    5. Generate HMAC-SHA512 signature with secret key
    6. Compare with v1 from header
    
    X-Casso-Signature format: t=1734924830020,v1=6cec920aa3352341d3710d4ce89de3c73481739bdf240c89a440fb988bfb113f...
    """
    if not signature_header:
        logger.error("No X-Casso-Signature header found")
        return False
    
    try:
        parts = {}
        for part in signature_header.split(','):
            key, value = part.split('=', 1)
            parts[key] = value
        
        timestamp = parts.get('t', '')
        received_signature = parts.get('v1', '')
        
        if not timestamp or not received_signature:
            logger.error("Missing timestamp or signature in header")
            return False
        
        logger.info(f"Timestamp: {timestamp}")
        logger.info(f"Received signature (v1): {received_signature[:50]}...")
        
        def sort_dict_by_keys(obj):
            """
            Recursively sort dictionary by keys (A->Z)
            """
            if isinstance(obj, dict):
                return {k: sort_dict_by_keys(obj[k]) for k in sorted(obj.keys())}
            elif isinstance(obj, list):
                return [sort_dict_by_keys(item) for item in obj]
            else:
                return obj
        
        sorted_data = sort_dict_by_keys(payload_dict)
        
        json_string = json.dumps(sorted_data, separators=(',', ':'), ensure_ascii=False)
        
        logger.info(f"Sorted JSON string: {json_string[:200]}...")
        
        signed_payload = f"{timestamp}.{json_string}"
        
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            signed_payload.encode('utf-8'),
            hashlib.sha512
        ).hexdigest()
        
        logger.info(f"Expected signature: {expected_signature[:50]}...")
        
        is_valid = hmac.compare_digest(expected_signature, received_signature)
        
        if is_valid:
            logger.info("Signature verified successfully!")
        else:
            logger.warning("Signature verification failed!")
            logger.warning(f"Expected: {expected_signature}")
            logger.warning(f"Received: {received_signature}")
        
        return is_valid
        
    except Exception as e:
        logger.error(f"Error verifying Webhook V2 signature: {str(e)}", exc_info=True)
        return False


def payment_view(request):
    """
    View để hiển thị QR code thanh toán
    GET: Nhận signature, giải mã và hiển thị QR code
    """
    signature = request.GET.get('signature')
    
    if not signature:
        return render(request, 'webhook/error.html', {
            'error': 'Thiếu thông tin thanh toán. Vui lòng quay lại trang chủ và thử lại.',
            'error_code': 'MISSING_SIGNATURE'
        })
    
    try:
        data = SignatureManager.verify_signature(signature)
        
        order_id = data.get('order_id')
        session, created = PaymentSession.objects.get_or_create(
            order_id=order_id,
            defaults={
                'amount': data.get('amount'),
                'description': data.get('description'),
                'account_number': data.get('account_number'),
                'return_url': data.get('return_url'),
                'username': data.get('username'),
                'payment_type': data.get('type'),
                'per_month_price': data.get('per_month_price'),
                'expired_at': datetime.fromtimestamp(data.get('expired_at'))
            }
        )
        
        if session.is_expired():
            session.status = 'expired'
            session.save()
            
            expired_minutes = int((session.expired_at - session.created_at).total_seconds() / 60)
            
            return render(request, 'webhook/expired.html', {
                'order_id': order_id,
                'created_at': session.created_at,
                'expired_at': session.expired_at,
                'expired_minutes': expired_minutes,
                'return_url': session.return_url.split('?')[0] if session.return_url else None  # Chỉ lấy base URL
            })
        
        if session.status == 'paid':
            redirect_url = f"{session.return_url}?order_id={order_id}&status=success&type={session.payment_type}&amount={session.amount}"
            
            donate_order_id = str(int(order_id) + 1)
            try:
                donate_session = PaymentSession.objects.get(order_id=donate_order_id, status='paid')
                redirect_url += f"&donate_order_id={donate_order_id}&donate_amount={donate_session.amount}"
            except PaymentSession.DoesNotExist:
                pass
            
            return redirect(redirect_url)
        
        time_remaining = (session.expired_at - timezone.now()).total_seconds()
        if time_remaining < 0:
            time_remaining = 0
        
        context = {
            'order_id': order_id,
            'amount': session.amount,
            'description': session.description,
            'qr_url': session.get_qr_url(),
            'expired_at': session.expired_at.isoformat(),
            'created_at': session.created_at.isoformat(),
            'time_remaining': int(time_remaining),
            'account_number': session.account_number,
            'return_url': session.return_url
        }
        
        return render(request, 'webhook/payment.html', context)
        
    except ValueError as e:
        logger.error(f"Signature verification failed: {str(e)}")
        return render(request, 'webhook/error.html', {
            'error': 'Thông tin thanh toán không hợp lệ hoặc đã bị giả mạo. Vui lòng tạo đơn hàng mới.',
            'error_code': 'INVALID_SIGNATURE'
        })
    except Exception as e:
        logger.error(f"Error processing payment: {str(e)}")
        return render(request, 'webhook/error.html', {
            'error': 'Có lỗi xảy ra khi xử lý thanh toán. Vui lòng liên hệ quản trị viên nếu vấn đề tiếp diễn.',
            'error_code': 'INTERNAL_ERROR'
        })


@csrf_exempt
@require_http_methods(["POST"])
def casso_webhook(request):
    """
    Webhook endpoint để nhận thông báo từ Casso khi có giao dịch mới
    Format Casso V2: {"error": 0, "data": {...transaction...}}
    """
    try:
        payload = json.loads(request.body)
        
        logger.info(f"Received Casso webhook: {payload}")
        
        casso_signature = request.headers.get('X-Casso-Signature', '')
        webhook_secret = getattr(settings, 'CASSO_WEBHOOK_SECRET', None)
        
        if webhook_secret:
            if not verify_casso_signature_v2(payload, casso_signature, webhook_secret):
                logger.warning("Invalid Casso Webhook V2 signature!")
                return JsonResponse({'status': 'error', 'message': 'Invalid signature'}, status=401)
            logger.info("Webhook V2 Signature verified successfully!")
        else:
            logger.warning("CASSO_WEBHOOK_SECRET not set - skipping signature verification (NOT SAFE FOR PRODUCTION!)")
        
        error_code = payload.get('error', -1)
        if error_code != 0:
            logger.error(f"Casso webhook error code: {error_code}")
            return JsonResponse({'status': 'error', 'message': 'Casso error', 'code': error_code}, status=400)
        
        data = payload.get('data', {})
        if not data:
            logger.warning("No transaction data in Casso webhook")
            return JsonResponse({'status': 'error', 'message': 'No transaction data'}, status=400)
        
        transaction_id = data.get('id')
        description = data.get('description', '')
        amount = data.get('amount')
        
        words = description.split()
        order_id = None
        
        for word in words:
            if word.isdigit() and len(word) >= 10:  
                order_id = word
                break
        
        if not order_id:
            logger.warning(f"Could not extract order_id from description: {description}")
            return JsonResponse({'status': 'error', 'message': 'Invalid description'}, status=400)
        
        try:
            session = PaymentSession.objects.get(order_id=order_id)
            
            if session.status == 'paid' and session.casso_transaction_id == str(transaction_id):
                logger.info(f"Payment {order_id} already processed (idempotent)")
                return JsonResponse({'status': 'success', 'order_id': order_id, 'message': 'Already processed'})
            
            if session.status == 'paid':
                logger.error(f"Payment {order_id} already paid with different transaction_id!")
                return JsonResponse({'status': 'error', 'message': 'Already paid'}, status=400)
            
            amount_mismatch = False
            split_payment = False
            
            if session.amount != amount:
                logger.warning(f"Amount mismatch for order {order_id}: expected {session.amount}, got {amount}")
                amount_mismatch = True
                
                if session.payment_type == 'monthly_fund' and amount > session.amount:
                    surplus = amount - session.amount
                    
                    logger.info(f"Amount surplus detected for order {order_id}: surplus={surplus}")
                    
                    if surplus > 0:
                        donate_order_id = str(int(order_id) + 1)
                        
                        PaymentSession.objects.create(
                            order_id=donate_order_id,
                            amount=surplus,
                            description=f"Xung quỹ từ {session.description}",
                            account_number=session.account_number,
                            return_url=session.return_url,
                            username=session.username,
                            payment_type='donate',
                            per_month_price=session.per_month_price,
                            status='paid',
                            casso_transaction_id=f"{transaction_id}_split",
                            paid_at=timezone.now(),
                            expired_at=session.expired_at
                        )
                        
                        logger.info(f"Created donate session {donate_order_id} for surplus {surplus}")
                        split_payment = True
                        
                else:
                    if session.payment_type == 'monthly_fund':
                        logger.info(f"Converting payment {order_id} to donate due to amount mismatch (expected={session.amount}, got={amount})")
                        session.payment_type = 'donate'
                        session.amount = amount
            
            session.status = 'paid'
            session.casso_transaction_id = str(transaction_id)
            session.paid_at = timezone.now()
            session.save()
            
            logger.info(f"Payment confirmed for order {order_id}" + 
                       (" (split to monthly_fund + donate)" if split_payment else
                        " (converted to donate)" if amount_mismatch and session.payment_type == 'donate' else ""))
            
            return JsonResponse({
                'status': 'success', 
                'order_id': order_id,
                'amount_mismatch': amount_mismatch,
                'split_payment': split_payment,
                'converted_to_donate': amount_mismatch and session.payment_type == 'donate' and not split_payment
            })
            
        except PaymentSession.DoesNotExist:
            logger.warning(f"Payment session not found for order {order_id}")
            return JsonResponse({
                'status': 'error', 
                'message': 'Không tìm thấy phiên thanh toán',
                'order_id': order_id
            }, status=404)
            
    except json.JSONDecodeError:
        logger.error("Invalid JSON in webhook request")
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@require_http_methods(["GET"])
def get_payment_info(request, order_id):
    """
    API endpoint để get thông tin payment session (thay thế PayOS API)
    Dùng cho backend FundPayment để verify payment
    """
    try:
        session = PaymentSession.objects.get(order_id=order_id)
        
        response_data = {
            'order_id': order_id,
            'amount': session.amount,
            'description': session.description,
            'status': session.status,
            'payment_type': session.payment_type,
            'username': session.username,
            'created_at': session.created_at.isoformat(),
            'expired_at': session.expired_at.isoformat(),
            'paid_at': session.paid_at.isoformat() if session.paid_at else None,
        }
        
        if session.status == 'paid':
            donate_order_id = str(int(order_id) + 1)
            try:
                donate_session = PaymentSession.objects.get(order_id=donate_order_id, status='paid')
                response_data['donate_split'] = {
                    'order_id': donate_order_id,
                    'amount': donate_session.amount
                }
            except PaymentSession.DoesNotExist:
                pass
        
        return JsonResponse(response_data)
        
    except PaymentSession.DoesNotExist:
        return JsonResponse({
            'error': 'Payment session not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Error getting payment info: {str(e)}")
        return JsonResponse({
            'error': str(e)
        }, status=500)


@require_http_methods(["GET"])
def check_payment_status(request, order_id):
    """
    API endpoint để check status của payment
    Dùng cho polling từ client
    """
    try:
        session = PaymentSession.objects.get(order_id=order_id)
        
        response_data = {
            'order_id': order_id,
            'status': session.status,
            'amount': session.amount,
        }
        
        if session.status == 'paid':
            redirect_url = f"{session.return_url}?order_id={order_id}&status=success&type={session.payment_type}&amount={session.amount}"
            
            donate_order_id = str(int(order_id) + 1)
            try:
                donate_session = PaymentSession.objects.get(order_id=donate_order_id, status='paid')
                redirect_url += f"&donate_order_id={donate_order_id}&donate_amount={donate_session.amount}"
                logger.info(f"Found donate split session: {donate_order_id}, amount: {donate_session.amount}")
            except PaymentSession.DoesNotExist:
                pass
            
            response_data['return_url'] = redirect_url
        elif session.is_expired() and session.status == 'pending':
            session.status = 'expired'
            session.save()
            response_data['status'] = 'expired'
            response_data['return_url'] = f"{session.return_url}?order_id={order_id}&status=cancelled"
        
        return JsonResponse(response_data)
        
    except PaymentSession.DoesNotExist:
        return JsonResponse({
            'error': 'Payment session not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Error checking payment status: {str(e)}")
        return JsonResponse({
            'error': str(e)
        }, status=500)

