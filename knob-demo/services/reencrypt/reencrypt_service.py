from flask import Flask, request, jsonify
from flask_cors import CORS
import boto3, json, sys
import psutil
from Crypto.Cipher import AES

app = Flask(__name__)
CORS(app)
BUCKET = "image-bank"

s3 = boto3.client("s3", endpoint_url="http://localstack:4566")
process = psutil.Process()

def dec_no_unpad(k, d): 
    """Decrypt without unpadding (for GK-encrypted blocks that are still FK-encrypted inside)"""
    return AES.new(k, AES.MODE_ECB).decrypt(d)

def enc_no_pad(k, d): 
    """Encrypt without padding (data already padded from FK encryption)"""
    return AES.new(k, AES.MODE_ECB).encrypt(d)

@app.route("/reencrypt", methods=["POST"])
def reencrypt():
    # Get parameters
    filename = request.form.get("filename", "")
    old_gk = request.form.get("old_gk", "").encode()  # Old Group Key
    new_gk = request.form.get("new_gk", "").encode()  # New Group Key
    super_indices_str = request.form.get("super_indices", "[]")
    
    # Parse super_indices from JSON array string
    try:
        super_indices = json.loads(super_indices_str)
    except:
        super_indices = [0]  # Fallback to default
    
    if not filename:
        return jsonify({"error": "filename is required"}), 400
    if not old_gk or len(old_gk) != 16:
        return jsonify({"error": "old_gk must be 16 bytes"}), 400
    if not new_gk or len(new_gk) != 16:
        return jsonify({"error": "new_gk must be 16 bytes"}), 400
    
    # Determine prefix from filename
    prefix = filename.rsplit('.', 1)[0]
    sys.stderr.write(f"[DEBUG /reencrypt] Processing prefix: {prefix}, super_indices: {super_indices}\n")
    sys.stderr.flush()

    # Load global metadata to validate block indices
    num_blocks = None
    try:
        metadata_obj = s3.get_object(Bucket=BUCKET, Key="_files_metadata.json")
        global_metadata = json.loads(metadata_obj["Body"].read())
        file_meta = global_metadata.get(prefix)
        if file_meta:
            num_blocks = file_meta.get("num_blocks")
    except Exception:
        num_blocks = None
    
    # Re-encrypt only the specified super block indices
    for idx in super_indices:
        try:
            idx = int(idx)
        except Exception:
            continue

        if num_blocks is not None:
            valid = 0 <= idx < num_blocks
        else:
            valid = 0 <= idx < 999999  # Fallback sanity check

        if valid:
            try:
                # Retrieve the super block
                block_obj = s3.get_object(Bucket=BUCKET, Key=f"{prefix}/block_{idx}")
                super_block = block_obj["Body"].read()
                
                # Decrypt with old GK (no unpad - still FK-encrypted inside)
                decrypted = dec_no_unpad(old_gk, super_block)
                
                # Re-encrypt with new GK (no pad - data already padded)
                reencrypted = enc_no_pad(new_gk, decrypted)
                
                # Upload back to S3
                s3.put_object(Bucket=BUCKET, Key=f"{prefix}/block_{idx}", Body=reencrypted)
            except Exception as e:
                return jsonify({"error": f"Failed to re-encrypt block {idx}: {str(e)}"}), 500

    return jsonify({
        "status": "reencrypted",
        "prefix": prefix,
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
    app.run(host="0.0.0.0", port=5003)
