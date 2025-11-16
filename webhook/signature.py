"""
Hệ thống mã hóa/giải mã signature (copy từ FundPayment)
"""
import base64
import json
import hmac
import hashlib
from datetime import datetime
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class SignatureManager:
    """
    Quản lý mã hóa và giải mã signature cho payment
    """
    
    @staticmethod
    def verify_signature(encoded_signature: str) -> dict:
        """
        Giải mã và verify signature
        
        Args:
            encoded_signature: Chuỗi signature đã mã hóa base64
            
        Returns:
            Dictionary chứa data nếu valid
            
        Raises:
            ValueError: Nếu signature không hợp lệ hoặc đã hết hạn
        """
        try:
            decoded = base64.urlsafe_b64decode(encoded_signature.encode('utf-8'))
            payload = json.loads(decoded.decode('utf-8'))
            
            data = payload.get('data')
            signature = payload.get('signature')
            
            if not data or not signature:
                raise ValueError("Invalid signature format")
            
            json_data = json.dumps(data, sort_keys=True)
            secret_key = settings.SECRET_KEY.encode('utf-8')
            expected_signature = hmac.new(
                secret_key,
                json_data.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            if not hmac.compare_digest(signature, expected_signature):
                raise ValueError("Signature verification failed")
            
            expired_at = data.get('expired_at')
            if expired_at and datetime.now().timestamp() > expired_at:
                raise ValueError("Signature has expired")
            
            logger.info(f"Verified signature for order: {data.get('order_id')}")
            return data
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {str(e)}")
            raise ValueError("Invalid signature format")
        except Exception as e:
            logger.error(f"Error verifying signature: {str(e)}")
            raise ValueError(str(e))

