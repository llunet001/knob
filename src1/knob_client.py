import os
import json
from tkinter import Tk, Label, Button, Entry, Listbox, END, messagebox, filedialog
from Crypto.Cipher import AES
import boto3

# ---------------- CONFIG ----------------
BUCKET = "data-bank"
BLOCK_SIZE = 1024 * 1024  # Must match admin
ENDPOINT_URL = "http://localhost:4566"
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

# ---------------- AONT FUNCTIONS ----------------
def aont_recover(blocks):
    """Recover original blocks from transformed blocks (if all blocks present)."""
    xor_all = blocks[-1]
    recovered = []
    for b in blocks[:-1]:
        recovered.append(b)
        xor_all = bytes(a ^ b for a, b in zip(xor_all, b))
    return recovered

def decrypt_block(enc_block, key):
    nonce = enc_block[:16]
    tag = enc_block[16:32]
    ciphertext = enc_block[32:]
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    return cipher.decrypt_and_verify(ciphertext, tag)

# ---------------- FILE ACCESS ----------------
def get_all_files():
    resp = s3.list_objects_v2(Bucket=BUCKET, Prefix="metadata/")
    files = []
    for obj in resp.get("Contents", []):
        key = obj["Key"]
        file_id = key.replace("metadata/", "").replace(".json", "")
        metadata = json.loads(s3.get_object(Bucket=BUCKET, Key=key)["Body"].read())
        files.append((file_id, metadata.get("filename", file_id)))
    return files

def download_file(file_id, save_folder, user_id):
    meta_key = f"metadata/{file_id}.json"
    metadata = json.loads(s3.get_object(Bucket=BUCKET, Key=meta_key)["Body"].read())

    if user_id not in metadata.get("user_access", []):
        messagebox.showerror("Access Denied", f"User {user_id} does not have access to this file")
        return

    blocks = []
    for blk_key in metadata["blocks"]:
        obj = s3.get_object(Bucket=BUCKET, Key=blk_key)
        enc_data = obj["Body"].read()
        # For demo, we simulate the file_key (normally retrieved from super-blocks in real Knob)
        file_key = b'\x00' * 32  # placeholder key; real demo should get from super-block
        try:
            dec = decrypt_block(enc_data, file_key)
        except Exception as e:
            messagebox.showerror("Decryption Failed", f"Cannot decrypt {blk_key}: {e}")
            return
        blocks.append(dec)

    recovered_blocks = aont_recover(blocks)
    save_path = os.path.join(save_folder, metadata["filename"])
    with open(save_path, "wb") as f:
        for b in recovered_blocks:
            f.write(b)
    messagebox.showinfo("Success", f"Downloaded file to {save_path}")

# ---------------- GUI ----------------
class ClientApp:
    def __init__(self, root):
        self.root = root
        root.title("Knob Client App")

        Label(root, text="User ID:").pack()
        self.entry_user = Entry(root, width=20)
        self.entry_user.pack()

        Label(root, text="Available Files:").pack()
        self.listbox_files = Listbox(root, width=80)
        self.listbox_files.pack()

        Button(root, text="Refresh Files", command=self.refresh_files).pack()
        Button(root, text="Download Selected File", command=self.download_selected).pack()

        self.files = []
        self.refresh_files()

    def refresh_files(self):
        self.listbox_files.delete(0, END)
        self.files = get_all_files()
        for fid, fname in self.files:
            self.listbox_files.insert(END, f"{fname} -> {fid}")

    def download_selected(self):
        selection = self.listbox_files.curselection()
        user_id = self.entry_user.get().strip()
        if not selection or not user_id:
            messagebox.showwarning("Warning", "Select a file and enter user ID")
            return
        file_id, _ = self.files[selection[0]]
        folder = filedialog.askdirectory()
        if folder:
            download_file(file_id, folder, user_id)

# ---------------- RUN APP ----------------
if __name__ == "__main__":
    root = Tk()
    app = ClientApp(root)
    root.mainloop()
