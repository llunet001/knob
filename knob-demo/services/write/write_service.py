from flask import Flask, request, jsonify
from flask_cors import CORS
import boto3, os, json
import psutil
from Crypto.Cipher import AES
from Crypto.Hash import SHA256
from Crypto.Util.Padding import pad

app = Flask(__name__)
CORS(app)
BUCKET = "image-bank"

s3 = boto3.client("s3", endpoint_url="http://localstack:4566")
process = psutil.Process()

def xor(a, b): return bytes(x ^ y for x, y in zip(a, b))
def h(d): return SHA256.new(d).digest()
def enc(k, d): return AES.new(k, AES.MODE_ECB).encrypt(pad(d, 16))
def enc_no_pad(k, d): return AES.new(k, AES.MODE_ECB).encrypt(d)  # For already-padded data


def get_default_super_indices():
    """Fetch default super indices from S3 config; fallback to [0]."""
    try:
        obj = s3.get_object(Bucket=BUCKET, Key="_config/super_indices.json")
        cfg = json.loads(obj["Body"].read())
        return cfg.get("super_indices", [0])
    except Exception:
        return [0]

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
    
    # Fetch default super block indices from S3 config (fallback to [0])
    super_indices = get_default_super_indices()
    
    # Split data into blocks (4KB each)
    BLOCK_SIZE = 4096
    blocks = [data[i:i+BLOCK_SIZE] for i in range(0, len(data), BLOCK_SIZE)]
    
    # Generate random File Key (FK)
    FK = os.urandom(32)  # 32 bytes for SHA256 compatibility
    
    # Encrypt each block with FK
    encrypted_blocks = []
    for block in blocks:
        c = enc(FK[:16], block)  # Use first 16 bytes of FK for AES
        encrypted_blocks.append(c)
    
    # Compute metaFK: h(c0) ⊕ h(c1) ⊕ ... ⊕ h(cn) ⊕ FK
    metaFK = FK
    for c in encrypted_blocks:
        metaFK = xor(metaFK, h(c))
    
    # Encrypt super blocks with GK (no additional padding - data already padded from FK encryption)
    for idx in super_indices:
        if 0 <= idx < len(encrypted_blocks):
            encrypted_blocks[idx] = enc_no_pad(GK, encrypted_blocks[idx])
    
    # Store each block separately in S3 with prefix
    # Extract only the filename (strip folder paths like "Test/file.txt" -> "file.txt")
    basename = filename.split('/')[-1].split('\\')[-1]
    prefix = basename.rsplit('.', 1)[0]  # Remove extension for prefix
    for i, block in enumerate(encrypted_blocks):
        s3.put_object(Bucket=BUCKET, Key=f"{prefix}/block_{i}", Body=block)
    
    # Store metaFK separately
    s3.put_object(Bucket=BUCKET, Key=f"{prefix}/metaFK", Body=metaFK)
    
    # Store metadata about the file
    s3.put_object(
        Bucket=BUCKET, 
        Key=f"{prefix}/metadata.json",
        Body=json.dumps({
            "filename": filename,
            "num_blocks": len(encrypted_blocks),
            "super_indices": super_indices
        })
    )
    
    return jsonify({
        "status": "stored",
        "filename": filename,
        "num_blocks": len(encrypted_blocks),
        "super_indices": super_indices
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
