import os
import io
import base64
import urllib.parse
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import qrcode
from PIL import Image

app = Flask(__name__)
# Enable CORS for all routes so frontend (Vite/React on port 3000, 5173, etc.) can communicate seamlessly
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Supported UPI Applications with their scheme formats & metadata
SUPPORTED_APPS = [
    {
        "id": "universal",
        "name": "Universal (All UPI Apps)",
        "description": "Works with Google Pay, PhonePe, Paytm, BHIM, Cred & 100+ banking apps",
        "badge": "Recommended",
        "scheme": "upi://pay"
    },
    {
        "id": "phonepe",
        "name": "PhonePe",
        "description": "Direct link optimized for PhonePe UPI",
        "badge": "Popular",
        "scheme": "phonepe://pay"
    },
    {
        "id": "google_pay",
        "name": "Google Pay (GPay)",
        "description": "Direct link optimized for Google Pay Tez",
        "badge": "Popular",
        "scheme": "gpay://upi/pay"
    },
    {
        "id": "paytm",
        "name": "Paytm",
        "description": "Direct link optimized for Paytm Wallet & UPI",
        "badge": "Popular",
        "scheme": "paytmmp://pay"
    },
    {
        "id": "fam_pay",
        "name": "FamPay",
        "description": "Direct link for FamPay UPI users",
        "badge": "Gen-Z",
        "scheme": "fampay://pay"
    },
    {
        "id": "bhim",
        "name": "BHIM UPI",
        "description": "NPCI Bharat Interface for Money",
        "badge": "Official",
        "scheme": "bhim://pay"
    },
    {
        "id": "cred",
        "name": "CRED UPI",
        "description": "Direct link for CRED Members",
        "badge": "Rewards",
        "scheme": "cred://pay"
    },
    {
        "id": "amazon_pay",
        "name": "Amazon Pay",
        "description": "Direct link for Amazon Pay UPI",
        "badge": "E-Commerce",
        "scheme": "amazonpay://pay"
    }
]

def build_upi_uri(upi_id: str, recipient_name: str, amount: str = None, message: str = None, app_scheme: str = "upi://pay") -> str:
    """
    Constructs a standard or app-specific UPI payment URL.
    Format: upi://pay?pa=UPI_ID&pn=NAME&am=AMOUNT&cu=INR&tn=MESSAGE&mc=1234
    """
    params = {
        'pa': upi_id.strip(),
        'pn': recipient_name.strip() if recipient_name else 'Merchant',
        'cu': 'INR'
    }
    
    if amount:
        try:
            val = float(str(amount).strip())
            if val > 0:
                params['am'] = f"{val:.2f}"
        except ValueError:
            pass
            
    if message and message.strip():
        params['tn'] = message.strip()

    # Build query string
    query_string = urllib.parse.urlencode(params)
    
    # Handle custom schemes
    if "?" in app_scheme:
        return f"{app_scheme}&{query_string}"
    return f"{app_scheme}?{query_string}"

def generate_qr_image_bytes(data_url: str, box_size: int = 10, border: int = 2) -> bytes:
    """
    Generates a high-quality QR code image using the python qrcode & PIL library.
    """
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(data_url)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="#0F172A", back_color="#FFFFFF")
    
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer.getvalue()

@app.route('/', methods=['GET'])
def root():
    """Root landing endpoint with API docs & service info."""
    return jsonify({
        "service": "Universal UPI QR Code Backend API",
        "version": "1.0.0",
        "status": "online",
        "endpoints": {
            "GET /api/health": "Health check & status",
            "GET /api/apps": "Get list of supported UPI payment apps",
            "POST /api/generate-qr": "Generate QR code data URL and UPI links (JSON POST)",
            "POST /api/verify-upi": "Validate and verify UPI ID format (JSON POST)",
            "GET /api/qr-image": "Direct QR image stream (GET with query parameters)"
        }
    })

@app.route('/api/health', methods=['GET'])
def health_check():
    """
    GET /api/health
    Returns service health and backend metadata.
    """
    return jsonify({
        "status": "ok",
        "service": "UPI QR Backend",
        "timestamp": os.getenv("CURRENT_TIME", "live"),
        "features": {
            "qr_generator": True,
            "multi_app_support": True,
            "validation": True
        },
        "total_supported_apps": len(SUPPORTED_APPS)
    })

@app.route('/api/apps', methods=['GET'])
def get_supported_apps():
    """
    GET /api/apps
    Returns list of supported payment apps with metadata.
    """
    return jsonify({
        "success": True,
        "apps": SUPPORTED_APPS
    })

@app.route('/api/verify-upi', methods=['POST'])
def verify_upi():
    """
    POST /api/verify-upi
    Validates the UPI ID format and performs verification checks.
    Request Body: { "upiId": "name@bank" }
    """
    data = request.get_json(silent=True) or {}
    upi_id = data.get("upiId", "").strip()

    if not upi_id:
        return jsonify({
            "valid": False,
            "message": "UPI ID is required"
        }), 400

    # Basic regex validation
    if "@" not in upi_id:
        return jsonify({
            "valid": False,
            "message": "UPI ID must contain '@' handle (e.g., username@okhdfcbank)"
        }), 422

    parts = upi_id.split("@")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        return jsonify({
            "valid": False,
            "message": "Invalid UPI handle format. Ensure both username and bank handle are specified."
        }), 422

    handle = parts[1].lower()
    known_handles = [
        "okaxis", "okhdfcbank", "okicici", "oksbi", "paytm", "ibl", "ybl",
        "axl", "upi", "apl", "fampay", "barodampay", "federal", "airtel"
    ]
    
    is_known = handle in known_handles
    
    return jsonify({
        "valid": True,
        "upiId": upi_id,
        "username": parts[0],
        "handle": parts[1],
        "isRecognizedHandle": is_known,
        "message": "UPI ID format is valid and ready for payment generation."
    })

@app.route('/api/generate-qr', methods=['POST'])
def generate_qr():
    """
    POST /api/generate-qr
    Generates QR code for payment.
    Request Body:
    {
      "upiId": "user@upi",
      "recipientName": "Name",
      "amount": "100.00", // optional
      "message": "Note", // optional
      "app": "universal" // optional app filter
    }
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "error": "Invalid JSON body provided."}), 400

    upi_id = data.get("upiId", "").strip()
    recipient_name = data.get("recipientName", "").strip()
    amount = data.get("amount", "")
    message = data.get("message", "")
    selected_app_id = data.get("app", "universal").lower()

    if not upi_id:
        return jsonify({"success": False, "error": "UPI ID is required."}), 400
    if not recipient_name:
        return jsonify({"success": False, "error": "Recipient name is required."}), 400

    # Find chosen app scheme
    selected_app = next((a for a in SUPPORTED_APPS if a["id"] == selected_app_id), SUPPORTED_APPS[0])
    
    # Universal standard URI
    universal_uri = build_upi_uri(upi_id, recipient_name, amount, message, "upi://pay")
    
    # Selected app URI
    app_uri = build_upi_uri(upi_id, recipient_name, amount, message, selected_app["scheme"])

    # Generate all app specific URLs (like the original payment_QR.py)
    app_urls = {
        "universal": universal_uri,
        "phonepe": build_upi_uri(upi_id, recipient_name, amount, message, "phonepe://pay"),
        "paytm": build_upi_uri(upi_id, recipient_name, amount, message, "paytmmp://pay"),
        "google_pay": build_upi_uri(upi_id, recipient_name, amount, message, "gpay://upi/pay"),
        "fam_pay": build_upi_uri(upi_id, recipient_name, amount, message, "fampay://pay"),
        "bhim": build_upi_uri(upi_id, recipient_name, amount, message, "bhim://pay"),
        "cred": build_upi_uri(upi_id, recipient_name, amount, message, "cred://pay"),
        "amazon_pay": build_upi_uri(upi_id, recipient_name, amount, message, "amazonpay://pay"),
    }

    # Generate QR Code image bytes for the requested URL (defaults to universal for maximum scanner compatibility)
    target_uri = universal_uri if selected_app_id == "universal" else app_uri
    qr_bytes = generate_qr_image_bytes(target_uri, box_size=10, border=2)
    qr_base64 = base64.b64encode(qr_bytes).decode('utf-8')
    qr_data_url = f"data:image/png;base64,{qr_base64}"

    return jsonify({
        "success": True,
        "qrCodeDataUrl": qr_data_url,
        "targetUri": target_uri,
        "universalUri": universal_uri,
        "selectedApp": selected_app,
        "appUrls": app_urls,
        "paymentDetails": {
            "upiId": upi_id,
            "recipientName": recipient_name,
            "amount": amount if amount else None,
            "message": message if message else None,
            "currency": "INR"
        }
    })

@app.route('/api/qr-image', methods=['GET'])
def get_qr_image_stream():
    """
    GET /api/qr-image?upiId=...&name=...&amount=...&message=...&app=...
    Streams back a raw PNG QR code directly for embedding in HTML or downloading.
    """
    upi_id = request.args.get('upiId', '').strip()
    name = request.args.get('name', 'Merchant').strip()
    amount = request.args.get('amount', None)
    message = request.args.get('message', None)
    app_id = request.args.get('app', 'universal').lower()
    download = request.args.get('download', 'false').lower() == 'true'

    if not upi_id:
        return jsonify({"error": "Missing 'upiId' query parameter"}), 400

    selected_app = next((a for a in SUPPORTED_APPS if a["id"] == app_id), SUPPORTED_APPS[0])
    target_uri = build_upi_uri(upi_id, name, amount, message, selected_app["scheme"])
    
    qr_bytes = generate_qr_image_bytes(target_uri, box_size=12, border=3)
    
    return send_file(
        io.BytesIO(qr_bytes),
        mimetype='image/png',
        as_attachment=download,
        download_name=f'upi_qr_{app_id}.png'
    )

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print("==================================================")
    print(">> Universal UPI QR Backend Server")
    print(f">> Running at: http://127.0.0.1:{port}")
    print(f">> Health Endpoint: http://127.0.0.1:{port}/api/health")
    print(f">> Apps Endpoint:   http://127.0.0.1:{port}/api/apps")
    print("==================================================")
    app.run(host='0.0.0.0', port=port, debug=False)
