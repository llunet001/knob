from flask import Flask, request, jsonify
from flask_cors import CORS
import boto3, json
import psutil
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

app = Flask(__name__)
CORS(app)
BUCKET = "image-bank"

s3 = boto3.client("s3", endpoint_url="http://localstack:4566")
process = psutil.Process()

def encrypt(key, data):
    """Encrypt data with AES using the provided key"""
    return AES.new(key, AES.MODE_ECB).encrypt(pad(data, 16))

@app.route("/write", methods=["POST"])
def write():
    # Get parameters
    data = request.files["file"].read()
    filename = request.files["file"].filename
    # Accept both 'gk' and 'GK' for compatibility
    gk_str = request.form.get("gk") or request.form.get("GK", "")
    GK = gk_str.encode()  # Group Key
    
    if not GK or len(GK) != 16:
        return jsonify({"error": "GK must be 16 bytes"}), 400
    
    # Encrypt entire file with GK
    encrypted_data = encrypt(GK, data)
    
    # Extract only the filename (strip folder paths like "Test/file.txt" -> "file.txt")
    basename = filename.split('/')[-1].split('\\')[-1]
    
    # Store encrypted file in S3
    try:
        s3.put_object(Bucket=BUCKET, Key=f"{basename}", Body=encrypted_data)
    except Exception as e:
        return jsonify({"error": f"Failed to store file in S3: {str(e)}"}), 500

    return jsonify({
        "status": "stored",
        "filename": filename,
        "key": basename
    })

@app.route("/admin/stats", methods=["GET"])
def admin_stats():
    try:
        # Use blocking interval for accurate CPU measurement
        cpu = process.cpu_percent(interval=0.1)
        mem = process.memory_info().rss
        return jsonify({"cpu_percent": cpu, "rss_bytes": mem})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
