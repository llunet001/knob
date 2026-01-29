from flask import Flask, request, jsonify
from flask_cors import CORS
import boto3
import psutil
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

app = Flask(__name__)
CORS(app)
BUCKET = "image-bank"

s3 = boto3.client("s3", endpoint_url="http://localstack:4566")
process = psutil.Process()

def decrypt(key, data):
    """Decrypt data with AES using the provided key"""
    return unpad(AES.new(key, AES.MODE_ECB).decrypt(data), 16)

def encrypt(key, data):
    """Encrypt data with AES using the provided key"""
    return AES.new(key, AES.MODE_ECB).encrypt(pad(data, 16))

@app.route("/reencrypt", methods=["POST"])
def reencrypt():
    # Get parameters
    filename = request.form.get("filename", "")
    old_gk = request.form.get("old_gk", "").encode()  # Old Group Key
    new_gk = request.form.get("new_gk", "").encode()  # New Group Key
    
    if not filename:
        return jsonify({"error": "filename is required"}), 400
    if not old_gk or len(old_gk) != 16:
        return jsonify({"error": "old_gk must be 16 bytes"}), 400
    if not new_gk or len(new_gk) != 16:
        return jsonify({"error": "new_gk must be 16 bytes"}), 400
    
    # Retrieve encrypted file
    try:
        file_obj = s3.get_object(Bucket=BUCKET, Key=filename)
        encrypted_data = file_obj["Body"].read()
    except:
        return jsonify({"error": "File not found"}), 404
    
    # Decrypt with old GK
    decrypted_data = decrypt(old_gk, encrypted_data)
    
    # Re-encrypt with new GK
    reencrypted_data = encrypt(new_gk, decrypted_data)
    
    # Upload back to S3
    s3.put_object(Bucket=BUCKET, Key=filename, Body=reencrypted_data)
    
    return jsonify({
        "status": "re-encrypted",
        "filename": filename
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
    app.run(host="0.0.0.0", port=5003)
