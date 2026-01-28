from flask import Flask, send_file, request, jsonify
from flask_cors import CORS
import boto3, io, json, sys
from Crypto.Cipher import AES
from Crypto.Hash import SHA256
from Crypto.Util.Padding import unpad

app = Flask(__name__)
CORS(app)
BUCKET = "image-bank"

s3 = boto3.client("s3", endpoint_url="http://localstack:4566")

def xor(a, b): return bytes(x ^ y for x, y in zip(a, b))
def h(d): return SHA256.new(d).digest()
def dec(k, d): return unpad(AES.new(k, AES.MODE_ECB).decrypt(d), 16)
def dec_no_unpad(k, d): return AES.new(k, AES.MODE_ECB).decrypt(d)

@app.route("/read", methods=["POST"])
def read():
    # Get parameters
    filename = request.form.get("filename", "")
    GK = request.form.get("GK", "").encode()  # Group Key
    
    if not filename:
        return jsonify({"error": "filename is required"}), 400
    if not GK or len(GK) != 16:
        return jsonify({"error": "GK must be 16 bytes"}), 400
    
    # Determine prefix from filename
    prefix = filename.rsplit('.', 1)[0]
    
    # Retrieve metadata
    try:
        metadata_obj = s3.get_object(Bucket=BUCKET, Key=f"{prefix}/metadata.json")
        metadata = json.loads(metadata_obj["Body"].read())
        num_blocks = metadata["num_blocks"]
        super_indices = metadata.get("super_indices", [0])
    except:
        return jsonify({"error": "File not found or invalid metadata"}), 404
    
    # Retrieve all encrypted blocks
    encrypted_blocks = []
    for i in range(num_blocks):
        block_obj = s3.get_object(Bucket=BUCKET, Key=f"{prefix}/block_{i}")
        encrypted_blocks.append(block_obj["Body"].read())
    
    # Retrieve metaFK
    metaFK_obj = s3.get_object(Bucket=BUCKET, Key=f"{prefix}/metaFK")
    metaFK = metaFK_obj["Body"].read()
    
    # Decrypt super blocks with GK first (no unpad - they're still FK-encrypted inside)
    for idx in super_indices:
        if 0 <= idx < len(encrypted_blocks):
            encrypted_blocks[idx] = dec_no_unpad(GK, encrypted_blocks[idx])
    
    # Recover FK: FK = metaFK ⊕ h(c0) ⊕ h(c1) ⊕ ... ⊕ h(cn)
    FK = metaFK
    for c in encrypted_blocks:
        FK = xor(FK, h(c))
    
    # Decrypt all blocks with FK
    decrypted_blocks = []
    for c in encrypted_blocks:
        plaintext = dec(FK[:16], c)  # Use first 16 bytes of FK for AES
        decrypted_blocks.append(plaintext)
    
    # Combine all blocks into original file
    data = b"".join(decrypted_blocks)
    
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
