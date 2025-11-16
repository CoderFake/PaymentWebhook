# Payment Webhook Server

Self-hosted payment gateway using VietQR and Casso webhook integration.

## Features

- Display VietQR payment QR codes
- Process Casso bank transaction webhooks  
- Handle payment splitting (monthly fund + donations)
- Signature-based security between services

## Quick Start

```bash
# Install dependencies
source .venv/bin/activate
pip install -r requirements.txt

# Setup environment
cp .env.example .env
# ⚠️ SECRET_KEY must match FundPayment!

# Run migrations
python manage.py migrate

# Start server
python manage.py runserver
```

## Environment Variables

Create `.env` file:

```bash
# Django Settings
SECRET_KEY=your-secret-key-here-must-match-fundpayment
DEBUG=False
ALLOWED_HOSTS=pay.hoangdieuit.io.vn,localhost

# Casso Integration
CASSO_WEBHOOK_SECRET=your-casso-webhook-secret

# Database (PostgreSQL for production)
DB_ENGINE=django.db.backends.postgresql
DB_NAME=payment_webhook_db
DB_USER=admin
DB_PASSWORD=your-password
DB_HOST=db
DB_PORT=5432

# Server
PORT=8000
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/?signature=...` | GET | Payment page with QR code |
| `/webhook/casso/` | POST | Casso webhook receiver |
| `/api/payment-status/<order_id>/` | GET | Check payment status (polling) |
| `/api/payment-info/<order_id>/` | GET | Get payment details |

## Casso Configuration

1. Login to https://casso.vn
2. Settings → Webhook → Add URL: `https://pay.hoangdieuit.io.vn/webhook/casso/`
3. Enable "New Transaction" event

## Payment Flow

```
FundPayment → [Encrypted Signature] → PaymentWebhook
    ↓                                       ↓
  User                              Display QR Code
    ↓                                       ↓
Bank Transfer                         Casso Webhook
    ↓                                       ↓
  Casso → [Transaction Data] → Update Payment Status
    ↓                                       ↓
Client Polling                         Redirect Back
    ↓                                       ↓
FundPayment ← [Success/Fail] ← PaymentWebhook
```

## Deployment

### Docker Compose (Recommended)

```bash
# Build and start (6 workers for 4GB RAM)
docker-compose up -d --build

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### Manual with Gunicorn

```bash
gunicorn PaymentWebhook.wsgi:application --bind 0.0.0.0:8000 --workers 6
```

## Notes

- Default payment expiry: 600 seconds (10 minutes)
- VietQR API: https://vietqr.io
- Polling interval: 3 seconds
- Supports amount mismatch detection (converts to donation)

