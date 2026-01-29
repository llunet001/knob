from flask import Flask, send_file, request, jsonify
from flask_cors import CORS
import boto3, io
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

app = Flask(__name__)
CORS(app)
BUCKET = "image-bank"

s3 = boto3.client("s3", endpoint_url="http://localstack:4566")

def decrypt(key, data):
    """Decrypt data with AES using the provided key"""
    return unpad(AES.new(key, AES.MODE_ECB).decrypt(data), 16)

@app.route("/read", methods=["POST"])
def read():
    # Get parameters
    filename = request.form.get("filename", "")
    GK = request.form.get("GK", "").encode()  # Group Key
    
    if not filename:
        return jsonify({"error": "filename is required"}), 400
    if not GK or len(GK) != 16:
        return jsonify({"error": "GK must be 16 bytes"}), 400
    
    # Retrieve encrypted file
    try:
        file_obj = s3.get_object(Bucket=BUCKET, Key=filename)
        encrypted_data = file_obj["Body"].read()
    except:
        return jsonify({"error": "File not found"}), 404
    
    # Decrypt entire file with GK
    data = decrypt(GK, encrypted_data)
    
    return send_file(io.BytesIO(data), mimetype="image/jpeg")

@app.route("/list", methods=["GET"])
def list_files():
    files = []
    continuation_token = None
    while True:
        if continuation_token:
            response = s3.list_objects_v2(Bucket=BUCKET, ContinuationToken=continuation_token)
        else:
            response = s3.list_objects_v2(Bucket=BUCKET)
        files.extend([obj['Key'] for obj in response.get('Contents', [])])
        if not response.get('IsTruncated'):
            break
        continuation_token = response.get('NextContinuationToken')
    return jsonify({"files": files, "_debug_total": len(files)})

@app.route("/admin/list_all", methods=["GET"])
def list_all():
    try:
        buckets = s3.list_buckets().get("Buckets", [])
        result = []
        for b in buckets:
            name = b["Name"]
            # List all objects with pagination
            objects = []
            continuation_token = None
            max_pages = 100  # Safety limit
            page = 0
            while page < max_pages:
                page += 1
                if continuation_token:
                    resp = s3.list_objects_v2(Bucket=name, ContinuationToken=continuation_token, MaxKeys=1000)
                else:
                    resp = s3.list_objects_v2(Bucket=name, MaxKeys=1000)
                contents = resp.get("Contents", [])
                objects.extend([o["Key"] for o in contents])
                # Check if there are more results
                if not resp.get('IsTruncated', False):
                    break
                continuation_token = resp.get('NextContinuationToken')
                if not continuation_token:
                    break
            result.append({"bucket": name, "objects": objects, "_page_count": page})
        return jsonify({"buckets": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002)
