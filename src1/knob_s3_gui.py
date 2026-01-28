import os
import json
import uuid
from tkinter import Tk, Label, Button, Entry, filedialog, Listbox, END, messagebox
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
import boto3

# ---------------- CONFIG ----------------
BUCKET = "data-bank"
BLOCK_SIZE = 1024 * 1024  # 1 MB blocks
SUPER_BLOCK_COUNT = 1
ENDPOINT_URL = "http://localhost:4566"  # LocalStack
AWS_KEY = "test"
AWS_SECRET = "test"
REGION = "us-east-1"

# ---------------- S3 CLIENT ----------------
s3 = boto3.client(
    "s3",
    endpoint_url=ENDPOINT_URL,
    aws_access_key_id=AWS_KEY,
    aws_secret_access_key=AWS_SECRET,
    region_name=REGION
)

# Ensure bucket exists
try:
    s3.create_bucket(Bucket=BUCKET)
except s3.exceptions.BucketAlreadyOwnedByYou:
    pass

# ---------------- ENCRYPTION UTILITIES ----------------
def encrypt_block(block_data, key):
    cipher = AES.new(key, AES.MODE_GCM)
    ciphertext, tag = cipher.encrypt_and_digest(block_data)
    return cipher.nonce + tag + ciphertext

def decrypt_block(enc_data, key):
    nonce = enc_data[:16]
    tag = enc_data[16:32]
    ciphertext = enc_data[32:]
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    return cipher.decrypt_and_verify(ciphertext, tag)

def split_file(file_path):
    with open(file_path, "rb") as f:
        while True:
            block = f.read(BLOCK_SIZE)
            if not block:
                break
            yield block

# ---------------- CORE FUNCTIONS ----------------
def upload_file(file_path):
    file_id = str(uuid.uuid4())
    metadata = {"blocks": [], "super_blocks": []}
    data_key = get_random_bytes(32)

    blocks = list(split_file(file_path))
    total_blocks = len(blocks)
    super_indexes = list(range(min(SUPER_BLOCK_COUNT, total_blocks)))

    for i, block in enumerate(blocks):
        enc = encrypt_block(block, data_key)
        key_name = f"files/{file_id}/block-{i:04d}"
        s3.put_object(Bucket=BUCKET, Key=key_name, Body=enc)
        metadata["blocks"].append(key_name)
        if i in super_indexes:
            metadata["super_blocks"].append(key_name)

    metadata["data_key"] = data_key.hex()
    meta_key = f"metadata/{file_id}.json"
    s3.put_object(Bucket=BUCKET, Key=meta_key, Body=json.dumps(metadata))
    return file_id

def revoke_file(file_id):
    meta_key = f"metadata/{file_id}.json"
    obj = s3.get_object(Bucket=BUCKET, Key=meta_key)
    metadata = json.loads(obj["Body"].read())

    old_key = bytes.fromhex(metadata["data_key"])
    new_key = get_random_bytes(32)
    metadata["data_key"] = new_key.hex()

    for sb_key in metadata["super_blocks"]:
        obj = s3.get_object(Bucket=BUCKET, Key=sb_key)
        plain = decrypt_block(obj["Body"].read(), old_key)
        enc = encrypt_block(plain, new_key)
        s3.put_object(Bucket=BUCKET, Key=sb_key, Body=enc)

    s3.put_object(Bucket=BUCKET, Key=meta_key, Body=json.dumps(metadata))

def get_bucket_size():
    resp = s3.list_objects_v2(Bucket=BUCKET)
    total = sum(obj["Size"] for obj in resp.get("Contents", []))
    return total

# ---------------- GUI ----------------
class KnobApp:
    def __init__(self, root):
        self.root = root
        root.title("Knob S3 Demo")

        # Folder selection
        self.label_folder = Label(root, text="Folder to upload:")
        self.label_folder.pack()
        self.entry_folder = Entry(root, width=50)
        self.entry_folder.pack()
        self.btn_browse = Button(root, text="Browse", command=self.browse_folder)
        self.btn_browse.pack()

        # Upload button
        self.btn_upload = Button(root, text="Upload Folder", command=self.upload_folder)
        self.btn_upload.pack()

        # Uploaded files list
        self.label_files = Label(root, text="Uploaded Files (IDs):")
        self.label_files.pack()
        self.listbox_files = Listbox(root, width=80)
        self.listbox_files.pack()

        # Revoke button
        self.btn_revoke = Button(root, text="Revoke Selected File", command=self.revoke_selected)
        self.btn_revoke.pack()

        # Bucket size
        self.btn_size = Button(root, text="Show Bucket Size", command=self.show_size)
        self.btn_size.pack()

        self.uploaded_ids = []
        
        # Load existing files from S3 on startup
        self.load_existing_files()

    def load_existing_files(self):
        """Load existing files from S3 bucket on startup"""
        try:
            # List all metadata files in the bucket
            resp = s3.list_objects_v2(Bucket=BUCKET, Prefix="metadata/")
            
            if "Contents" not in resp:
                return
            
            for obj in resp["Contents"]:
                key = obj["Key"]
                # Extract file_id from metadata key (format: metadata/{file_id}.json)
                if key.endswith(".json"):
                    file_id = key.replace("metadata/", "").replace(".json", "")
                    self.uploaded_ids.append(file_id)
                    self.listbox_files.insert(END, f"Existing file -> {file_id}")
        except Exception as e:
            print(f"Error loading existing files: {e}")

    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.entry_folder.delete(0, END)
            self.entry_folder.insert(0, folder)

    def upload_folder(self):
        folder = self.entry_folder.get()
        if not folder or not os.path.exists(folder):
            messagebox.showerror("Error", "Folder not found")
            return

        self.uploaded_ids = []
        self.listbox_files.delete(0, END)
        for root_dir, dirs, files in os.walk(folder):
            for filename in files:
                path = os.path.join(root_dir, filename)
                file_id = upload_file(path)
                self.uploaded_ids.append(file_id)
                self.listbox_files.insert(END, f"{filename} -> {file_id}")

        messagebox.showinfo("Upload Complete", f"Uploaded {len(self.uploaded_ids)} files")

    def revoke_selected(self):
        selection = self.listbox_files.curselection()
        if not selection:
            messagebox.showwarning("Select File", "No file selected")
            return
        index = selection[0]
        file_id = self.uploaded_ids[index]
        revoke_file(file_id)
        messagebox.showinfo("Revoked", f"Revoked access to file ID: {file_id}")

    def show_size(self):
        size_bytes = get_bucket_size()
        messagebox.showinfo("Bucket Size", f"{size_bytes} bytes ({size_bytes/1024**2:.2f} MB)")

# ---------------- RUN GUI ----------------
if __name__ == "__main__":
    root = Tk()
    app = KnobApp(root)
    root.mainloop()
