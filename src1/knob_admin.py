import os
import json
import uuid
from tkinter import Tk, Label, Button, Entry, Listbox, END, filedialog, messagebox, Frame, Scrollbar
from tkinter import font as tkFont
from tkinter import ttk
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
import hashlib
import boto3

# ---------------- CONFIG ----------------
BUCKET = "data-bank"
BLOCK_SIZE = 1024 * 1024  # 1 MB
SUPER_BLOCK_COUNT = 2
ENDPOINT_URL = "http://localhost:4566"
AWS_KEY = "test"
AWS_SECRET = "test"
REGION = "us-east-1"
USERS_KEY = "users.json"

# ---------------- S3 CLIENT ----------------
s3 = boto3.client(
    "s3",
    endpoint_url=ENDPOINT_URL,
    aws_access_key_id=AWS_KEY,
    aws_secret_access_key=AWS_SECRET,
    region_name=REGION
)
try:
    s3.create_bucket(Bucket=BUCKET)
except s3.exceptions.BucketAlreadyOwnedByYou:
    pass

# ---------------- AONT FUNCTIONS ----------------
def aont_transform(blocks):
    """Simple XOR-based AONT: last block stores XOR of all blocks."""
    transformed = []
    xor_all = bytes(BLOCK_SIZE)
    for b in blocks:
        if len(b) < BLOCK_SIZE:
            b += b'\x00' * (BLOCK_SIZE - len(b))
        transformed.append(b)
        xor_all = bytes(a ^ b for a, b in zip(xor_all, b))
    # Append XOR as the last block
    transformed.append(xor_all)
    return transformed

def aont_recover(blocks):
    """Recover original blocks from transformed blocks (if all blocks present)."""
    xor_all = blocks[-1]
    recovered = []
    for b in blocks[:-1]:
        recovered.append(b)
        xor_all = bytes(a ^ b for a, b in zip(xor_all, b))
    return recovered

def encrypt_block(block, key):
    cipher = AES.new(key, AES.MODE_GCM)
    ciphertext, tag = cipher.encrypt_and_digest(block)
    return cipher.nonce + tag + ciphertext

def decrypt_block(enc_block, key):
    nonce = enc_block[:16]
    tag = enc_block[16:32]
    ciphertext = enc_block[32:]
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    return cipher.decrypt_and_verify(ciphertext, tag)

def split_file(file_path):
    with open(file_path, "rb") as f:
        while True:
            block = f.read(BLOCK_SIZE)
            if not block:
                break
            yield block

# ---------------- FILE MANAGEMENT ----------------
def upload_file(file_path):
    file_id = str(uuid.uuid4())
    metadata = {
        "blocks": [],
        "super_blocks": [],
        "user_access": [],
        "filename": os.path.basename(file_path)
    }

    # Generate per-file key
    data_key = get_random_bytes(32)

    # Split file into blocks
    blocks = list(split_file(file_path))
    transformed_blocks = aont_transform(blocks)

    # Pick super-blocks
    total_blocks = len(transformed_blocks)
    super_indexes = list(range(min(SUPER_BLOCK_COUNT, total_blocks)))

    for i, block in enumerate(transformed_blocks):
        enc = encrypt_block(block, data_key)
        key_name = f"files/{file_id}/block-{i:04d}"
        s3.put_object(Bucket=BUCKET, Key=key_name, Body=enc)
        metadata["blocks"].append(key_name)
        if i in super_indexes:
            metadata["super_blocks"].append(key_name)

    # Store key in memory only; not in metadata (Knob principle)
    metadata["file_key_ref"] = f"file_key/{file_id}"  # reference placeholder

    meta_key = f"metadata/{file_id}.json"
    s3.put_object(Bucket=BUCKET, Key=meta_key, Body=json.dumps(metadata))
    return file_id, os.path.basename(file_path), data_key, transformed_blocks

def get_all_files():
    resp = s3.list_objects_v2(Bucket=BUCKET, Prefix="metadata/")
    files = []
    for obj in resp.get("Contents", []):
        key = obj["Key"]
        file_id = key.replace("metadata/", "").replace(".json", "")
        metadata = json.loads(s3.get_object(Bucket=BUCKET, Key=key)["Body"].read())
        files.append((file_id, metadata.get("filename", file_id)))
    return files

def grant_access(file_id, user_id):
    meta_key = f"metadata/{file_id}.json"
    obj = s3.get_object(Bucket=BUCKET, Key=meta_key)
    metadata = json.loads(obj["Body"].read())
    if user_id not in metadata["user_access"]:
        metadata["user_access"].append(user_id)
    s3.put_object(Bucket=BUCKET, Key=meta_key, Body=json.dumps(metadata))

def revoke_access(file_id, user_id):
    meta_key = f"metadata/{file_id}.json"
    obj = s3.get_object(Bucket=BUCKET, Key=meta_key)
    metadata = json.loads(obj["Body"].read())

    if user_id in metadata["user_access"]:
        metadata["user_access"].remove(user_id)

    # Re-encrypt super-blocks
    old_key = get_random_bytes(32)  # In real Knob, generate new key
    for sb_key in metadata["super_blocks"]:
        enc_obj = s3.get_object(Bucket=BUCKET, Key=sb_key)
        plain = enc_obj["Body"].read()  # Already encrypted with old_key in memory
        new_enc = encrypt_block(plain, old_key)
        s3.put_object(Bucket=BUCKET, Key=sb_key, Body=new_enc)

    s3.put_object(Bucket=BUCKET, Key=meta_key, Body=json.dumps(metadata))

# ---------------- USER MANAGEMENT ----------------
def load_users():
    try:
        obj = s3.get_object(Bucket=BUCKET, Key=USERS_KEY)
        return json.loads(obj["Body"].read())
    except s3.exceptions.NoSuchKey:
        return []

def save_users(users):
    s3.put_object(Bucket=BUCKET, Key=USERS_KEY, Body=json.dumps(users))

def add_user(user_id):
    users = load_users()
    if user_id not in users:
        users.append(user_id)
        save_users(users)
        return True
    return False

# ---------------- GUI ----------------
class AdminApp:
    def __init__(self, root):
        self.root = root
        root.title("Knob Admin - Secure File & Access Management")
        root.geometry("1200x900")
        root.resizable(True, True)
        
        # Color scheme (dark professional theme)
        self.bg_primary = "#1e1e2e"
        self.bg_secondary = "#282a36"
        self.accent_color = "#ff79c6"
        self.success_color = "#50fa7b"
        self.text_color = "#f8f8f2"
        self.button_hover = "#44475a"
        
        root.configure(bg=self.bg_primary)
        
        # Define fonts
        self.title_font = tkFont.Font(family="Helvetica", size=16, weight="bold")
        self.section_font = tkFont.Font(family="Helvetica", size=11, weight="bold")
        self.label_font = tkFont.Font(family="Helvetica", size=10)
        self.button_font = tkFont.Font(family="Helvetica", size=9, weight="bold")
        
        # ===== HEADER SECTION =====
        header_frame = Frame(root, bg=self.accent_color, height=80)
        header_frame.pack(fill="x", padx=0, pady=0)
        header_frame.pack_propagate(False)
        
        title_label = Label(header_frame, text="🔐 Knob Admin Control Panel", 
                           font=tkFont.Font(family="Helvetica", size=18, weight="bold"),
                           bg=self.accent_color, fg="#1e1e2e")
        title_label.pack(pady=15)
        
        # ===== MAIN CONTENT FRAME =====
        main_frame = Frame(root, bg=self.bg_primary)
        main_frame.pack(fill="both", expand=True, padx=15, pady=15)
        
        # ===== LEFT PANEL - FILE MANAGEMENT =====
        left_panel = Frame(main_frame, bg=self.bg_primary)
        left_panel.pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        # Upload section
        upload_section = Frame(left_panel, bg=self.bg_secondary, relief="flat", 
                              highlightthickness=2, highlightbackground=self.accent_color)
        upload_section.pack(fill="x", pady=(0, 15))
        
        Label(upload_section, text="📤 File Upload", font=self.section_font,
              bg=self.bg_secondary, fg=self.accent_color).pack(anchor="w", padx=12, pady=(10, 8))
        
        Label(upload_section, text="Select folder to upload:", font=self.label_font,
              bg=self.bg_secondary, fg=self.text_color).pack(anchor="w", padx=12, pady=(0, 5))
        
        self.entry_folder = Entry(upload_section, width=50, font=self.label_font,
                                 bg="#44475a", fg=self.text_color, insertbackground=self.accent_color,
                                 relief="flat", bd=0)
        self.entry_folder.pack(fill="x", padx=12, pady=(0, 10), ipady=6)
        
        btn_frame1 = Frame(upload_section, bg=self.bg_secondary)
        btn_frame1.pack(fill="x", padx=12, pady=(0, 12))
        
        browse_btn = self.create_styled_button(btn_frame1, "Browse Folder", self.browse_folder)
        browse_btn.pack(side="left", padx=(0, 5), fill="x", expand=True)
        
        upload_btn = self.create_styled_button(btn_frame1, "Upload", self.upload_folder, primary=True)
        upload_btn.pack(side="left", padx=(5, 0), fill="x", expand=True)
        
        # Files list section
        files_section = Frame(left_panel, bg=self.bg_secondary, relief="flat",
                             highlightthickness=2, highlightbackground=self.accent_color)
        files_section.pack(fill="both", expand=True)
        
        Label(files_section, text="📁 Current Files in Bucket", font=self.section_font,
              bg=self.bg_secondary, fg=self.accent_color).pack(anchor="w", padx=12, pady=(10, 8))
        
        listbox_frame = Frame(files_section, bg=self.bg_secondary)
        listbox_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        
        scrollbar1 = Scrollbar(listbox_frame, bg=self.button_hover, troughcolor=self.bg_secondary)
        scrollbar1.pack(side="right", fill="y")
        
        self.listbox_files = Listbox(listbox_frame, height=15, font=self.label_font,
                                    bg="#44475a", fg=self.text_color, selectbackground=self.accent_color,
                                    selectforeground="#1e1e2e", yscrollcommand=scrollbar1.set,
                                    relief="flat", bd=0, highlightthickness=0)
        self.listbox_files.pack(side="left", fill="both", expand=True)
        scrollbar1.config(command=self.listbox_files.yview)
        
        # ===== RIGHT PANEL - USER MANAGEMENT =====
        right_panel = Frame(main_frame, bg=self.bg_primary)
        right_panel.pack(side="right", fill="both", expand=True, padx=(10, 0))
        
        # Add User section
        add_user_section = Frame(right_panel, bg=self.bg_secondary, relief="flat",
                                highlightthickness=2, highlightbackground=self.success_color)
        add_user_section.pack(fill="x", pady=(0, 15))
        
        Label(add_user_section, text="👥 Add New User", font=self.section_font,
              bg=self.bg_secondary, fg=self.success_color).pack(anchor="w", padx=12, pady=(10, 8))
        
        Label(add_user_section, text="User ID:", font=self.label_font,
              bg=self.bg_secondary, fg=self.text_color).pack(anchor="w", padx=12, pady=(0, 5))
        
        self.entry_new_user = Entry(add_user_section, width=30, font=self.label_font,
                                   bg="#44475a", fg=self.text_color, insertbackground=self.success_color,
                                   relief="flat", bd=0)
        self.entry_new_user.pack(fill="x", padx=12, pady=(0, 10), ipady=6)
        
        add_user_btn = self.create_styled_button(add_user_section, "Add User", self.add_new_user, primary=True)
        add_user_btn.pack(fill="x", padx=12, pady=(0, 12))
        
        # Users list section
        users_section = Frame(right_panel, bg=self.bg_secondary, relief="flat",
                             highlightthickness=2, highlightbackground=self.success_color)
        users_section.pack(fill="both", expand=True, pady=(0, 15))
        
        Label(users_section, text="👤 Registered Users", font=self.section_font,
              bg=self.bg_secondary, fg=self.success_color).pack(anchor="w", padx=12, pady=(10, 8))
        
        user_listbox_frame = Frame(users_section, bg=self.bg_secondary)
        user_listbox_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        
        scrollbar2 = Scrollbar(user_listbox_frame, bg=self.button_hover, troughcolor=self.bg_secondary)
        scrollbar2.pack(side="right", fill="y")
        
        self.listbox_users = Listbox(user_listbox_frame, height=10, font=self.label_font,
                                    bg="#44475a", fg=self.text_color, selectbackground=self.success_color,
                                    selectforeground="#1e1e2e", yscrollcommand=scrollbar2.set,
                                    relief="flat", bd=0, highlightthickness=0)
        self.listbox_users.pack(side="left", fill="both", expand=True)
        scrollbar2.config(command=self.listbox_users.yview)
        
        # Access Control section
        access_section = Frame(right_panel, bg=self.bg_secondary, relief="flat",
                              highlightthickness=2, highlightbackground="#8be9fd")
        access_section.pack(fill="x")
        
        Label(access_section, text="🔐 Access Control", font=self.section_font,
              bg=self.bg_secondary, fg="#8be9fd").pack(anchor="w", padx=12, pady=(10, 8))
        
        Label(access_section, text="User ID:", font=self.label_font,
              bg=self.bg_secondary, fg=self.text_color).pack(anchor="w", padx=12, pady=(0, 5))
        
        self.entry_user = Entry(access_section, width=30, font=self.label_font,
                               bg="#44475a", fg=self.text_color, insertbackground="#8be9fd",
                               relief="flat", bd=0)
        self.entry_user.pack(fill="x", padx=12, pady=(0, 10), ipady=6)
        
        btn_frame2 = Frame(access_section, bg=self.bg_secondary)
        btn_frame2.pack(fill="x", padx=12, pady=(0, 12))
        
        grant_btn = self.create_styled_button(btn_frame2, "Grant Access", self.grant_selected, primary=True)
        grant_btn.pack(side="left", padx=(0, 5), fill="x", expand=True)
        
        revoke_btn = self.create_styled_button(btn_frame2, "Revoke Access", self.revoke_selected)
        revoke_btn.pack(side="left", padx=(5, 0), fill="x", expand=True)
        
        # ===== FOOTER SECTION =====
        footer_frame = Frame(root, bg=self.bg_secondary, height=50)
        footer_frame.pack(fill="x", padx=0, pady=0)
        footer_frame.pack_propagate(False)
        
        footer_label = Label(footer_frame, text="Knob - Secure File Management System | v1.0", 
                            font=tkFont.Font(family="Helvetica", size=9),
                            bg=self.bg_secondary, fg="#6272a4")
        footer_label.pack(pady=12)
        
        # Internal storage
        self.files = []
        self.load_existing_files()
        self.refresh_user_list()
    
    def create_styled_button(self, parent, text, command, primary=False):
        """Create a styled button with hover effects"""
        if primary:
            btn = Button(parent, text=text, command=command, font=self.button_font,
                        bg=self.accent_color if "Revoke" not in text else "#ff5555", 
                        fg="#1e1e2e", relief="flat", bd=0,
                        padx=15, pady=8, cursor="hand2", 
                        activebackground="#ffb3d9" if "Revoke" not in text else "#ff8888",
                        activeforeground="#1e1e2e")
        else:
            btn = Button(parent, text=text, command=command, font=self.button_font,
                        bg="#44475a", fg=self.accent_color, relief="flat", bd=1,
                        padx=15, pady=8, cursor="hand2", activebackground=self.button_hover,
                        activeforeground=self.accent_color, borderwidth=1)
        return btn
    
    def load_existing_files(self):
        """Load existing files from S3 bucket on startup"""
        try:
            self.refresh_file_list()
        except Exception as e:
            print(f"Error loading existing files: {e}")

    # ----------- GUI HANDLERS -----------
    def browse_folder(self):
        folder = filedialog.askdirectory(title="Select Folder to Upload")
        if folder:
            self.entry_folder.delete(0, END)
            self.entry_folder.insert(0, folder)

    def upload_folder(self):
        folder = self.entry_folder.get()
        if not folder or not os.path.exists(folder):
            messagebox.showerror("❌ Error", "Folder not found")
            return
        
        upload_count = 0
        for root_dir, dirs, files in os.walk(folder):
            for filename in files:
                path = os.path.join(root_dir, filename)
                try:
                    fid, fname, _, _ = upload_file(path)
                    upload_count += 1
                except Exception as e:
                    messagebox.showerror("❌ Upload Error", f"Failed to upload {filename}: {e}")
                    return
        
        messagebox.showinfo("✅ Success", f"Uploaded {upload_count} file(s) successfully!")
        self.entry_folder.delete(0, END)
        self.refresh_file_list()

    def refresh_file_list(self):
        self.listbox_files.delete(0, END)
        self.files = get_all_files()
        if not self.files:
            self.listbox_files.insert(END, "No files in bucket")
        else:
            for fid, fname in self.files:
                self.listbox_files.insert(END, f"📄 {fname} → {fid[:8]}...")

    def add_new_user(self):
        user_id = self.entry_new_user.get().strip()
        if not user_id:
            messagebox.showwarning("⚠️ Warning", "Please enter a user ID")
            return
        if add_user(user_id):
            messagebox.showinfo("✅ Success", f"User '{user_id}' added successfully!")
            self.entry_new_user.delete(0, END)
            self.refresh_user_list()
        else:
            messagebox.showwarning("⚠️ Warning", f"User '{user_id}' already exists")

    def list_users(self):
        self.refresh_user_list()

    def refresh_user_list(self):
        self.listbox_users.delete(0, END)
        users = load_users()
        if not users:
            self.listbox_users.insert(END, "No users registered")
        else:
            for u in sorted(users):
                self.listbox_users.insert(END, f"👤 {u}")

    def grant_selected(self):
        selection = self.listbox_files.curselection()
        user_id = self.entry_user.get().strip()
        if not selection or not user_id:
            messagebox.showwarning("⚠️ Warning", "Select a file and enter a user ID")
            return
        file_id, fname = self.files[selection[0]]
        try:
            grant_access(file_id, user_id)
            messagebox.showinfo("✅ Success", f"Granted '{user_id}' access to '{fname}'")
            self.entry_user.delete(0, END)
        except Exception as e:
            messagebox.showerror("❌ Error", f"Failed to grant access: {e}")

    def revoke_selected(self):
        selection = self.listbox_files.curselection()
        user_id = self.entry_user.get().strip()
        if not selection or not user_id:
            messagebox.showwarning("⚠️ Warning", "Select a file and enter a user ID")
            return
        file_id, fname = self.files[selection[0]]
        try:
            revoke_access(file_id, user_id)
            messagebox.showinfo("✅ Revoked", f"Revoked '{user_id}'s access to '{fname}'")
            self.entry_user.delete(0, END)
        except Exception as e:
            messagebox.showerror("❌ Error", f"Failed to revoke access: {e}")

# ---------------- RUN APP ----------------
if __name__ == "__main__":
    root = Tk()
    app = AdminApp(root)
    root.mainloop()
