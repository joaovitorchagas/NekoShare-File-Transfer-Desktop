import os
import socket
import threading
import json
import time
import uuid
import shutil
import sys
from tkinter import PhotoImage
from pathlib import Path
from datetime import datetime
from queue import Queue, Empty
import webbrowser
import tkinter as tk
from flask import Flask, request, render_template_string, send_from_directory, jsonify, Response, send_file
from werkzeug.utils import secure_filename
import qrcode
from PIL import Image, ImageTk
import customtkinter as ctk
from tkinter import filedialog, messagebox

# ---------------- Config ----------------
DEFAULT_PORT = 8080
RECEIVED_DIR = Path.cwd() / "Received"
MAX_CONTENT_LENGTH = 4 * 1024 * 1024 * 1024  # 4 GB
# ----------------------------------------

# Flask app
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# State
state = {
    "port": DEFAULT_PORT,
    "dest_dir": RECEIVED_DIR,
    "running": False
}

# connected clients: ip -> {"queue": Queue(), "last_seen": ts}
clients_lock = threading.Lock()
clients = {}

# Ensure directories
RECEIVED_DIR.mkdir(parents=True, exist_ok=True)

# ---------------- Mobile HTML (with SSE & popup) ----------------
MOBILE_HTML = """
<!doctype html>
<html lang="id">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>NekoShare File (Mobile)</title>
<link rel="icon" type="image/png" href="assets/icon.png">
<script src="https://cdn.tailwindcss.com"></script>
<style>
@import url('https://fonts.googleapis.com/css2?family=Cherry+Bomb+One&family=Roboto:wght@400;700&display=swap');
/* Perubahan utama untuk membuat tampilan pas layar penuh */
body {
    background-color: #F8F0FF;
    color: #4A235A;
    font-family: 'Roboto', sans-serif;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    box-sizing: border-box;
    padding: 0;
    margin: 0;
}

/* Gaya baru untuk navbar */
.navbar {
    background-color: #FFC0CB;
    padding: 1rem;
    display: flex;
    justify-content: center;
    border-bottom: 2px dashed #FF69B4;
    box-shadow: 0 4px 10px rgba(255, 105, 180, 0.1);
}
.navbar a {
    color: #FF1493;
    font-weight: 700;
    text-decoration: none;
    transition: color 0.2s ease-in-out;
    padding: 0 1rem;
}
.navbar a:hover {
    color: #8B0000;
}

/* Gaya untuk menempatkan card di tengah-tengah ruang yang tersisa */
.content-wrapper {
    flex-grow: 1; /* Kontainer ini akan mengambil sisa ruang yang tersedia */
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 16px;
}

/* Gaya baru untuk footer */
.footer {
    background-color: #FFC0CB;
    padding: 1rem;
    text-align: center;
    font-size: 0.9rem;
    border-top: 2px dashed #FF69B4;
    box-shadow: 0 -4px 10px rgba(255, 105, 180, 0.1);
}

.card {
    background-color: #FFF0F5;
    border-radius: 24px;
    padding: 32px;
    box-shadow: 0 10px 40px rgba(255,105,180,0.2);
    max-width: 760px;
    width: 100%;
    border: 3px dashed #FF69B4;
    flex-shrink: 0;
}

h1 { font-family: 'Cherry Bomb One', cursive; color: #FF1493; text-shadow: 2px 2px #FFC0CB; }
.popup { position: fixed; inset: 0; display: flex; align-items: center; justify-content: center; background: rgba(255, 192, 203, 0.5); visibility: hidden; opacity: 0; transition: opacity 0.3s ease, visibility 0.3s ease; }
.popup.show { visibility: visible; opacity: 1; }
.popup-box { background-color: #FFFFFF; border-radius: 20px; padding: 24px; width: 92%; max-width: 420px; box-shadow: 0 8px 30px rgba(0,0,0,0.1); border: 2px solid #FFC0CB; animation: bounceIn 0.5s ease-out; }
@keyframes bounceIn { from, 20%, 40%, 60%, 80%, to { animation-timing-function: cubic-bezier(0.215, 0.61, 0.355, 1); } 0% { opacity: 0; transform: scale3d(0.3, 0.3, 0.3); } 20% { transform: scale3d(1.1, 1.1, 1.1); } 40% { transform: scale3d(0.9, 0.9, 0.9); } 60% { opacity: 1; transform: scale3d(1.03, 1.03, 1.03); } 80% { transform: scale3d(0.97, 0.97, 0.97); } to { opacity: 1; transform: scale3d(1, 1, 1); } }
.btn { padding: 14px 28px; border-radius: 16px; font-weight: 700; transition: all 0.2s ease-in-out; cursor: pointer; text-shadow: 1px 1px 2px rgba(0,0,0,0.1); border: none; }
.btn-primary { background-color: #FF69B4; color: #FFFFFF; box-shadow: 0 4px 15px rgba(255,105,180,0.5); }
.btn-primary:hover { background-color: #FF1493; transform: translateY(-2px); box-shadow: 0 6px 20px rgba(255,105,180,0.7); }
.file-input-wrapper { position: relative; overflow: hidden; display: block; width: 100%; }
.file-input-wrapper input[type="file"] { position: absolute; left: 0; top: 0; opacity: 0; cursor: pointer; }
.file-input-label { background-color: #FCE4EC; color: #880E4F; display: block; padding: 16px 20px; border-radius: 16px; border: 2px dashed #FFC0CB; text-align: left; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; cursor: pointer; font-size: 0.95rem; box-shadow: 0 2px 10px rgba(252,228,236,0.8); }
.file-input-label:hover { background-color: #F8BBD0; }
#progressBarContainer { display: none; width: 100%; background-color: #FFD1DC; border-radius: 12px; height: 16px; margin-top: 16px; overflow: hidden; border: 2px solid #FFC0CB; }
#progressBar { width: 0%; height: 100%; background-color: #FF69B4; transition: width 0.4s ease-in-out; }
#notification .popup-box { background-color: #FFF0F5; border: 2px solid #FFC0CB; box-shadow: 0 8px 30px rgba(255,105,180,0.2); }
.btn-accept { background-color: #90EE90; color: #FFFFFF; }
.btn-decline { background-color: #FFA07A; color: #FFFFFF; }
@media (max-width: 640px) { .btn-group { flex-direction: column; gap: 12px; } .btn-group .btn { width: 100%; } }
</style>
</head>
<body>

<nav class="navbar">
    <a href="https://github.com" target="_blank">Github</a>
    <a href="https://instagram.com" target="_blank">Instagram</a>
    <a href="https://facebook.com" target="_blank">Facebook</a>
</nav>

<div class="content-wrapper">
    <div class="card p-6 md:p-8">
      <h1 class="text-3xl md:text-4xl font-bold">NekoShare File 😻</h1>
      <p class="text-gray-600 mt-2 text-base md:text-lg">Pindai kode QR di PC untuk terhubung.</p>
      <div class="mt-8">
        <h2 class="text-xl md:text-2xl font-semibold text-gray-700">Unggah file ke PC</h2>
        <form id="uploadForm" class="mt-4">
          <div class="file-input-wrapper">
            <input id="fileInput" type="file" name="files" multiple required onchange="updateFileName(this)" />
            <label for="fileInput" class="file-input-label" id="fileInputLabel">Pilih file...</label>
          </div>
          <button id="uploadBtn" class="mt-4 btn btn-primary w-full md:w-auto" type="submit"><span id="buttonText">🚀 Unggah ke PC</span></button>
          <div id="progressBarContainer"><div id="progressBar"></div></div>
        </form>
      </div>
    </div>
</div>

<footer class="footer">
    <p>Developed by Rizko Imsar</p>
</footer>

<div id="offerPopup" class="popup">
  <div class="popup-box p-6 md:p-8 text-center">
    <h3 id="offerTitle" class="text-xl md:text-2xl font-bold text-gray-800">PC ingin mengirim file</h3>
    <p id="offerBody" class="text-gray-600 mt-2 text-sm md:text-base"></p>
    <div class="mt-6 flex gap-3 btn-group">
      <button id="acceptBtn" class="btn btn-accept text-white hover:bg-green-600 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-opacity-50">Terima</button>
      <button id="declineBtn" class="btn btn-decline text-white hover:bg-red-600 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-opacity-50">Tolak</button>
    </div>
  </div>
</div>
<div id="notification" class="popup">
  <div class="popup-box text-center">
    <h3 class="text-2xl font-bold text-gray-800">🎉 Unggah Selesai!</h3>
    <div class="mt-6"><button id="okBtn" class="btn btn-primary w-full">OK</button></div>
  </div>
</div>
<script>
const uploadForm = document.getElementById('uploadForm'), offerPopup = document.getElementById('offerPopup'), notificationPopup = document.getElementById('notification'), okBtn = document.getElementById('okBtn'), uploadBtn = document.getElementById('uploadBtn'), progressBarContainer = document.getElementById('progressBarContainer'), progressBar = document.getElementById('progressBar'), fileInputLabel = document.getElementById('fileInputLabel'), offerTitle = document.getElementById('offerTitle'), offerBody = document.getElementById('offerBody'), acceptBtn = document.getElementById('acceptBtn'), declineBtn = document.getElementById('declineBtn');
function updateFileName(input) {
  if (input.files && input.files.length > 0) {
    fileInputLabel.textContent = input.files.length === 1 ? input.files[0].name : `${input.files.length} file terpilih`;
    uploadBtn.disabled = false;
    uploadBtn.classList.remove('opacity-50', 'cursor-not-allowed');
  } else {
    fileInputLabel.textContent = "Pilih file...";
    uploadBtn.disabled = true;
    uploadBtn.classList.add('opacity-50', 'cursor-not-allowed');
  }
}
uploadForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const files = document.getElementById('fileInput').files;
  if (!files.length) return;
  progressBarContainer.style.display = 'block';
  uploadBtn.disabled = true;
  document.getElementById('buttonText').textContent = 'Mengunggah...';
  const fd = new FormData();
  for (let f of files) fd.append('files', f);
  const xhr = new XMLHttpRequest();
  xhr.open('POST', '/upload', true);
  xhr.upload.addEventListener('progress', (e) => {
    if (e.lengthComputable) progressBar.style.width = `${(e.loaded / e.total) * 100}%`;
  });
  xhr.onreadystatechange = function() {
    if (xhr.readyState === 4) {
      progressBarContainer.style.display = 'none';
      uploadBtn.disabled = false;
      document.getElementById('buttonText').textContent = '🚀 Unggah ke PC';
      if (xhr.status === 200) notificationPopup.classList.add('show');
      else { alert('Unggah gagal'); uploadForm.reset(); updateFileName(document.getElementById('fileInput')); }
    }
  };
  xhr.send(fd);
});
okBtn.addEventListener('click', () => {
  notificationPopup.classList.remove('show');
  window.location.reload();
});
const es = new EventSource('/events');
es.onmessage = function(ev){
  try {
    const data = JSON.parse(ev.data);
    if (data.type === 'offer') showOffer(data);
  } catch(e){ console.error(e); }
}
function showOffer(data){
  offerTitle.textContent = `PC ${data.pc_name} ingin mengirim file`;
  offerBody.innerHTML = `<strong>${data.orig_name}</strong> — ${data.size}<br/>IP: ${data.pc_ip}`;
  offerPopup.classList.add('show');
  acceptBtn.onclick = async () => {
    window.location.href = data.url;
    offerPopup.classList.remove('show');
  };
  declineBtn.onclick = async () => {
    offerPopup.classList.remove('show');
  };
}
</script>
</body>
</html>
"""

# ---------------- Helper functions ----------------
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def gui_log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    try:
        log_box.insert("end", f"[{ts}] {msg}\n")
        log_box.see("end")
    except Exception:
        print(f"[{ts}] {msg}")

# ---------------- Flask endpoints ----------------
@app.route("/", methods=["GET"])
def mobile_index():
    ip = request.remote_addr
    with clients_lock:
        if ip not in clients:
            clients[ip] = {"queue": Queue(), "last_seen": time.time()}
        else:
            clients[ip]["last_seen"] = time.time()
    return render_template_string(MOBILE_HTML)

@app.route("/upload", methods=["POST"])
def mobile_upload():
    files = request.files.getlist("files")
    saved = []
    for f in files:
        filename = secure_filename(f.filename)
        target = Path(state["dest_dir"]) / filename
        base, ext = os.path.splitext(filename)
        counter = 1
        while target.exists():
            filename = f"{base}_{counter}{ext}"
            target = Path(state["dest_dir"]) / filename
            counter += 1
        target.parent.mkdir(parents=True, exist_ok=True)
        f.save(str(target))
        saved.append(filename)
        gui_log(f"📥 HP→PC: {filename}")
    return jsonify({"success": True, "files": saved})

@app.route("/download")
def download_file():
    filepath_str = request.args.get('path')
    if not filepath_str:
        return "File path missing", 400
    
    filepath = Path(filepath_str)
    
    if not filepath.exists() or not filepath.is_file():
        gui_log(f"❌ File tidak ditemukan: {filepath}")
        return "File not found", 404
        
    try:
        gui_log(f"✅ Mobile {request.remote_addr} menerima file {filepath.name}")
        return send_file(filepath, as_attachment=True, download_name=filepath.name)
    except Exception as e:
        gui_log(f"❌ Gagal mengirim file: {e}")
        return f"Error: {e}", 500

@app.route("/events")
def sse_events():
    client_ip = request.remote_addr
    def gen():
        q = None
        with clients_lock:
            if client_ip not in clients:
                clients[client_ip] = {"queue": Queue(), "last_seen": time.time()}
            q = clients[client_ip]["queue"]
            clients[client_ip]["last_seen"] = time.time()
        
        try:
            while True:
                try:
                    item = q.get(timeout=0.5)
                except Empty:
                    yield ": keepalive\n\n"
                    continue
                
                payload = json.dumps(item)
                yield f"data: {payload}\n\n"
        except GeneratorExit:
            pass
    return Response(gen(), mimetype='text/event-stream')

# ---------------- Offer creation (PC side) ----------------
def create_offer_for_target(target_ip: str, filepath: str):
    if not Path(filepath).exists():
        gui_log("❌ File tidak ditemukan.")
        return False
    
    orig_name = os.path.basename(filepath)
    size_bytes = os.stat(filepath).st_size
    size_mb = size_bytes / (1024 * 1024)
    size_str = f"{size_mb:.2f} MB" if size_mb > 1 else f"{size_bytes / 1024:.2f} KB"
    
    meta = {
        "type": "offer",
        "orig_name": orig_name,
        "size": size_str,
        "pc_ip": get_local_ip(),
        "pc_name": socket.gethostname(),
        "url": f"/download?path={filepath}"
    }

    with clients_lock:
        client = clients.get(target_ip)
        if client:
            client["queue"].put(meta)
            gui_log(f"📡 Offer dikirim ke {target_ip} untuk file {orig_name}")
            return True
        else:
            gui_log(f"⚠️ Target {target_ip} belum terhubung (buka halaman di HP terlebih dahulu).")
            return False

def get_asset_path(relative_path):
    try:
        # PyInstaller creates a temporary folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # Path for normal execution
        base_path = os.path.abspath(".")
    
    # Menyesuaikan path untuk file di dalam folder 'assets'
    return os.path.join(base_path, 'assets', relative_path)


# ---------------- GUI (desktop) ----------------
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("green") 

root = ctk.CTk()
root.title("NekoShare File (Desktop)")
root.geometry("880x720")
root.resizable(False, False)

# Tambahkan ikon ke aplikasi
try:
    icon_path_png = get_asset_path('icon.png')
    icon_img = Image.open(icon_path_png)
    icon_tk = ImageTk.PhotoImage(icon_img)
    root.iconphoto(False, icon_tk)

    if os.name == 'nt':
        icon_path_ico = get_asset_path('icon.ico')
        root.iconbitmap(icon_path_ico)

except Exception as e:
    print(f"Gagal memuat ikon: {e}")

menubar = tk.Menu(root)
file_menu = tk.Menu(menubar, tearoff=0)
file_menu.add_command(label="Exit", command=root.destroy)
menubar.add_cascade(label="File", menu=file_menu)

edit_menu = tk.Menu(menubar, tearoff=0)
edit_menu.add_command(label="Settings (coming soon)")
menubar.add_cascade(label="Edit", menu=edit_menu)

view_menu = tk.Menu(menubar, tearoff=0)
view_menu.add_command(label="Refresh Logs", command=lambda: log_box.delete("1.0", "end") if 'log_box' in globals() else None)
menubar.add_cascade(label="View", menu=view_menu)

about_menu = tk.Menu(menubar, tearoff=0)
about_menu.add_command(label="About", command=lambda: show_about_page())
menubar.add_cascade(label="Help", menu=about_menu)

root.config(menu=menubar)

container = ctk.CTkFrame(root, fg_color="#F4BAD3")
container.pack(fill="both", expand=True, padx=12, pady=12)

log_box = None

def clear_container():
    for w in container.winfo_children():
        w.destroy()

# ---------- Home Page ----------
def show_home_page():
    clear_container()
    frame = ctk.CTkFrame(container, corner_radius=12, fg_color="#F4C9DC")
    frame.pack(fill="both", expand=True, padx=10, pady=10)
    header = ctk.CTkLabel(frame, text="NekoShare File", font=("Comic Sans MS", 28, "bold"), text_color="#88005B", anchor="w")
    header.pack(pady=(8,22))
    row_top = ctk.CTkFrame(frame, fg_color="transparent")
    row_top.pack(fill="x", padx=12, pady=6)
    port_label = ctk.CTkLabel(row_top, text="Port:", width=60, anchor="w", text_color="#333333")
    port_label.pack(side="left", padx=(12))
    port_var = ctk.StringVar(value=str(DEFAULT_PORT))
    port_entry = ctk.CTkEntry(row_top, textvariable=port_var, width=120, fg_color="#F8F8F8", border_color="#B0B0B0", text_color="#333333")
    port_entry.pack(side="left", padx=(0.5))
    folder_label = ctk.CTkLabel(row_top, text="Save To:", width=110, anchor="w", text_color="#333333")
    folder_label.pack(side="left", padx=(12))
    folder_var = ctk.StringVar(value=str(RECEIVED_DIR))
    folder_entry = ctk.CTkEntry(row_top, textvariable=folder_var, width=380, fg_color="#F8F8F8", border_color="#B0B0B0", text_color="#333333")
    folder_entry.pack(side="left", padx=(0.5))
    def choose_folder_action():
        d = filedialog.askdirectory(initialdir=str(RECEIVED_DIR))
        if d:
            folder_var.set(d)
            state["dest_dir"] = Path(d)
    btn_choose = ctk.CTkButton(row_top, text="Browse", width=110, command=choose_folder_action, fg_color="#FF69B4", hover_color="#C71585")
    btn_choose.pack(side="left", padx=(6,0))
    row_btns = ctk.CTkFrame(frame, fg_color="transparent")
    row_btns.pack(pady=10)
    def run_flask_thread(host, port):
        app.run(host=host, port=port, debug=False, threaded=True, use_reloader=False)
    def start_server_action():
        if state["running"]:
            messagebox.showinfo("Information", "The server is already running. Please stop it first.")
            return
        try:
            state["port"] = int(port_var.get())
        except ValueError:
            messagebox.showerror("Error", "Port tidak valid.")
            return
        state["dest_dir"] = Path(folder_var.get())
        host = get_local_ip()
        t = threading.Thread(target=run_flask_thread, args=(host, state["port"]), daemon=True)
        t.start()
        state["running"] = True
        update_qr_action()
        gui_log(f"Server berjalan di http://{host}:{state['port']}")
    def stop_server_action():
        state["running"] = False
        try:
            qr_label.configure(image="", text="(QR dihentikan)")
        except NameError:
            pass
        gui_log("Server dihentikan.")
    btn_start = ctk.CTkButton(row_btns, text="Start Server", fg_color="#AE32CD", hover_color="#228B22", width=160, command=start_server_action)
    btn_start.pack(side="left", padx=8)
    btn_stop = ctk.CTkButton(row_btns, text="Stop Server", fg_color="#DD4C4C", hover_color="#B22222", width=160, command=stop_server_action)
    btn_stop.pack(side="left", padx=8)
    btn_send_page = ctk.CTkButton(row_btns, text="📤 Send To Mobile", fg_color="#FF69B4", hover_color="#C71585", width=160, command=show_send_page)
    btn_send_page.pack(padx=8)
    qr_frame = ctk.CTkFrame(frame, fg_color="transparent")
    qr_frame.pack(pady=10)
    global qr_label
    qr_label = ctk.CTkLabel(qr_frame, text="(QR akan muncul setelah Start)", width=440, text_color="#333333")
    qr_label.pack()
    def update_qr_action():
        ip = get_local_ip()
        url = f"http://{ip}:{state['port']}/"
        qr = qrcode.QRCode(border=1); qr.add_data(url); qr.make(fit=True)
        img = qr.make_image(fill_color="#FF69B4", back_color="white").resize((220,220))
        photo = ImageTk.PhotoImage(img)
        qr_label.configure(image=photo, text="")
        qr_label.image = photo
        gui_log(f"Scan QR: {url}")
    global log_box
    log_box = ctk.CTkTextbox(frame, height=220, corner_radius=8, fg_color="#F8F8F8", text_color="#333333")
    log_box.pack(fill="both", expand=True, padx=12, pady=(10,4))

# ---------- Send page ----------
def show_send_page():
    clear_container()
    frame = ctk.CTkFrame(container, corner_radius=12, fg_color="#F4C9DC")
    frame.pack(fill="both", expand=True, padx=10, pady=10)
    ctk.CTkLabel(frame, text="Send To Mobile", font=("Segoe UI", 22, "bold"), text_color="#333333").pack(pady=(8,10))
    ctk.CTkLabel(frame, text="Select file and select device from list (real-time).", text_color="#606060").pack()
    row = ctk.CTkFrame(frame, fg_color="transparent")
    row.pack(pady=10)
    ctk.CTkLabel(row, text="Choose file:", width=90, anchor="w", text_color="#333333").pack(side="left", padx=6)
    file_var = ctk.StringVar(value="")
    file_entry = ctk.CTkEntry(row, textvariable=file_var, width=420, fg_color="#F8F8F8", border_color="#B0B0B0", text_color="#333333")
    file_entry.pack(side="left", padx=6)
    def choose_file_action():
        f = filedialog.askopenfilename()
        if f:
            file_var.set(f)
    ctk.CTkButton(row, text="Browse", width=100, command=choose_file_action, fg_color="#FF69B4", hover_color="#C71585").pack(side="left", padx=6)
    ctk.CTkLabel(frame, text="Perangkat Ditemukan:", anchor="w", text_color="#333333").pack(pady=(6,0), padx=8)
    list_widget = tk.Listbox(frame, height=14, activestyle="none", font=("Segoe UI", 12),
                             bg="#F8F8F8", fg="#333333", selectbackground="#D6E4FF", selectforeground="#000000",
                             highlightthickness=0, borderwidth=0)
    list_widget.pack(fill="x", padx=12, pady=6)
    row2 = ctk.CTkFrame(frame, fg_color="transparent")
    row2.pack(pady=8)
    btn_find = ctk.CTkButton(row2, text="🔍 Found Device", fg_color="#1E90FF", hover_color="#0000CD", command=lambda: find_devices_action(list_widget))
    btn_find.pack(side="left", padx=6)
    btn_send = ctk.CTkButton(row2, text="🚀 Send", fg_color="#FF69B4", hover_color="#C71585", command=lambda: send_to_selected(file_var, list_widget))
    btn_send.pack(side="left", padx=6)
    ctk.CTkButton(row2, text="⬅ Back", command=show_home_page, fg_color="#909090", hover_color="#707070").pack(side="left", padx=6)
    ctk.CTkLabel(frame, text="(Select one of the device rows and then click Send.)", text_color="#606060").pack(pady=(6,0))
    ctk.CTkLabel(frame, text="(Pilih salah satu baris perangkat lalu klik Kirim)", text_color="#606060").pack(pady=6)
    global log_box
    if log_box:
        log_box.pack(fill="both", expand=True, padx=12, pady=(10,4))
    def on_list_click(event):
        try:
            index = list_widget.curselection()[0]
            selected_item = list_widget.get(index)
        except IndexError:
            pass
    list_widget.bind("<<ListboxSelect>>", on_list_click)

def find_devices_action(list_widget):
    list_widget.delete(0, tk.END)
    with clients_lock:
        active_clients = [ip for ip, meta in clients.items() if (time.time() - meta["last_seen"]) < 60]
    if not active_clients:
        gui_log("ℹ Tidak ada perangkat terhubung. Pastikan HP kamu membuka halaman ini.")
        list_widget.insert(tk.END, "Tidak ada perangkat terhubung. Pastikan HP anda membuka browser..")
        list_widget.insert(tk.END, "No devices are connected. Make sure your phone has a browser open..")
        return
    for ip in active_clients:
        name = clients[ip].get("name", "Mobile")
        list_widget.insert(tk.END, f"{name} - {ip}")
    gui_log(f"🔍 Ditemukan {len(active_clients)} perangkat.")

def send_to_selected(file_var, list_widget):
    selection = list_widget.curselection()
    if not selection:
        messagebox.showerror("Error", "Pilih perangkat dari daftar.")
        return
    index = selection[0]
    selected_item = list_widget.get(index)
    target_ip = selected_item.split(" - ")[-1].strip()
    filepath = file_var.get().strip()
    if not filepath or not Path(filepath).exists():
        messagebox.showerror("Error", "Harus pilih file terlebih dahulu.")
        return
    ok = create_offer_for_target(target_ip, filepath)
    if ok:
        gui_log(f"📤 Offer dibuat untuk {target_ip}")
    else:
        gui_log("❌ Gagal buat offer (target tidak terhubung atau error).")

# About page
def show_about_page():
    clear_container()
    frame = ctk.CTkFrame(container, corner_radius=12, fg_color="#F4C9DC")
    frame.pack(fill="both", expand=True, padx=10, pady=10)
    ctk.CTkLabel(frame, text="About NekoShare File", font=("Comic Sans MS", 26, "bold"), text_color="#88005B").pack(pady=10)
    ctk.CTkLabel(frame, text="Developed By Rizko Imsar", font=("Segoe UI", 16), text_color="#88005B").pack(pady=4)
    def open_github(): webbrowser.open("https://github.com/rizko77")
    def open_instagram(): webbrowser.open("https://instagram.com/rizkoimsar_")
    ctk.CTkButton(frame, text="Github", command=open_github, fg_color="#6F2525", hover_color="#483D8B").pack(pady=10)
    ctk.CTkButton(frame, text="Instagram", command=open_instagram, fg_color="#CB6EA6", hover_color="#483D8B").pack(pady=10)
    ctk.CTkButton(frame, text="⬅ Back", command=show_home_page, fg_color="#909090", hover_color="#707070").pack(pady=10)

show_home_page()
gui_log("Aplikasi siap. Tekan Start Server untuk mulai dan scan QR dengan Smartphone.")

root.mainloop()