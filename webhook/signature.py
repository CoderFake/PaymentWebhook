"""
Hệ thống mã hóa/giải mã signature với AES-128-CBC + HMAC-SHA256 (Fernet)
"""
import base64
import json
from datetime import datetime
from django.conf import settings
import logging
from cryptography.fernet import Fernet
import hashlib

logger = logging.getLogger(__name__)


class SignatureManager:
    """
    Quản lý mã hóa và giải mã signature cho payment với AES encryption
    """
    
    @staticmethod
    def _get_fernet_key():
        """
        Derive Fernet key from SECRET_KEY
        Fernet requires 32 url-safe base64-encoded bytes
        """
        key_hash = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
        return base64.urlsafe_b64encode(key_hash)
    
    @staticmethod
    def verify_signature(encoded_signature: str) -> dict:
        """
        Decrypt và verify signature từ FundPayment
        
        Args:
            encoded_signature: Chuỗi signature đã mã hóa
            
        Returns:
            Dictionary chứa data nếu valid
            
        Raises:
            ValueError: Nếu signature không hợp lệ, bị sửa đổi, hoặc đã hết hạn
        """
        try:
            encrypted = base64.urlsafe_b64decode(encoded_signature.encode('utf-8'))
            fernet = Fernet(SignatureManager._get_fernet_key())
            decrypted = fernet.decrypt(encrypted)  
            data = json.loads(decrypted.decode('utf-8'))
            
            expired_at = data.get('expired_at')
            if expired_at and datetime.now().timestamp() > expired_at:
                raise ValueError("Signature has expired")
            
            logger.info(f"Verified and decrypted signature for order: {data.get('order_id')}")
            return data
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {str(e)}")
            raise ValueError("Invalid signature format")
        except Exception as e:
            logger.error(f"Error verifying signature: {str(e)}")
            raise ValueError("Signature verification failed - data may be tampered")
    
    @staticmethod
    def create_signature(data: dict) -> str:
        """
        Encrypt và tạo signature (for testing purposes)
        
        Args:
            data: Dictionary chứa thông tin payment
                
        Returns:
            Chuỗi signature đã mã hóa
        """
        try:
            payload_json = json.dumps(data, sort_keys=True)
            fernet = Fernet(SignatureManager._get_fernet_key())
            encrypted = fernet.encrypt(payload_json.encode('utf-8'))
            encoded = base64.urlsafe_b64encode(encrypted).decode('utf-8')
            
            logger.info(f"Created encrypted signature for order: {data.get('order_id')}")
            return encoded
            
        except Exception as e:
            logger.error(f"Error creating signature: {str(e)}")
            raise

