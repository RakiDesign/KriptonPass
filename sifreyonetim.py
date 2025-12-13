import ctypes
import customtkinter as ctk
from tkinter import messagebox, filedialog, simpledialog
import sqlite3
import hashlib
import os
import secrets
import string
import pyperclip
import requests
import json
import time
import csv
import pyotp
import qrcode
import tempfile
import sys
from PIL import Image, ImageTk 
from cryptography.fernet import Fernet
from io import BytesIO

try:
    # Windows 8.1 ve üzeri için DPI farkındalığını aç (Netlik Ayarı)
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    # Eski Windows sürümleri için alternatif
    ctypes.windll.user32.SetProcessDPIAware()

def resource_path(relative_path):
    """ Exe içindeki dosya yolunu bulmak için yardımcı fonksiyon """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path) 

# --- AYARLAR VE RENK PALETİ ---
COLOR_BG = ("#F3F4F6", "#0F172A")       
COLOR_SIDEBAR = ("#E2E8F0", "#1E293B")  
COLOR_CARD = ("#FFFFFF", "#334155")     
COLOR_ACCENT = ("#3B8ED0", "#3B8ED0")   
COLOR_DANGER = ("#EF4444", "#EF4444")   
COLOR_SUCCESS = ("#10B981", "#10B981")  
COLOR_TEXT_MAIN = ("#1E293B", "#F8FAFC") 
COLOR_TEXT_SUB = ("#64748B", "#94A3B8")  

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

AUTO_LOCK_SURESI = 300 

# ==========================================
# BACKEND (MANTIK)
# ==========================================
class BackendManager:
    def __init__(self):
        self.db_file = "kripton_data.db"
        self.key_file = "kripton_key.key"
        self.hash_file = "kripton_master.hash"
        self.panic_file = "kripton_panic.hash"
        self.lock_file = "kripton_lock.json"
        self.tfa_file = "kripton_2fa.secret"
        self.settings_file = "kripton_settings.json"
        self.valid_signatures = [b"###KRIPTON###", b"###SIBER###", b"###SIBERKASA###"]
        self.anahtar_yukle_veya_olustur()
        self.db_baslat()

    def anahtar_yukle_veya_olustur(self):
        if os.path.exists(self.key_file):
            with open(self.key_file, "rb") as f: self.anahtar = f.read()
        else:
            self.anahtar = Fernet.generate_key()
            with open(self.key_file, "wb") as f: f.write(self.anahtar)
        self.fernet = Fernet(self.anahtar)

    def db_baslat(self):
        self.conn = sqlite3.connect(self.db_file, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.cursor.execute("CREATE TABLE IF NOT EXISTS hesaplar (id INTEGER PRIMARY KEY AUTOINCREMENT, platform TEXT, kullanıcı_adi TEXT, sifreli_sifre BLOB)")
        self.cursor.execute("CREATE TABLE IF NOT EXISTS notlar (id INTEGER PRIMARY KEY AUTOINCREMENT, baslik TEXT, icerik BLOB)")
        self.conn.commit()

    def tema_ayari_getir(self):
        if os.path.exists(self.settings_file):
            try: return json.load(open(self.settings_file)).get("tema", "Dark")
            except: return "Dark"
        return "Dark"
    def tema_ayari_kaydet(self, t): json.dump({"tema": t}, open(self.settings_file, "w"))

    def kurulum_var_mi(self): return os.path.exists(self.hash_file)

    def brute_force_kontrol(self, islem="kontrol"):
        MAX_HAK = 5; BEKLEME = 600
        if not os.path.exists(self.lock_file): json.dump({"fail": 0, "time": 0}, open(self.lock_file, "w"))
        data = json.load(open(self.lock_file)); now = time.time()
        if islem == "kontrol":
            if now - data["time"] > BEKLEME: data["fail"]=0; json.dump(data, open(self.lock_file, "w")); return True, MAX_HAK
            if data["fail"] >= MAX_HAK: return False, f"{(BEKLEME-(now-data['time']))//60:.0f} dakika"
            return True, (MAX_HAK - data["fail"])
        elif islem == "hata": data["fail"]+=1; data["time"]=now; json.dump(data, open(self.lock_file, "w")); return MAX_HAK-data["fail"]
        elif islem == "basarili": data["fail"]=0; json.dump(data, open(self.lock_file, "w")); return MAX_HAK

    def panik_kontrol(self, girilen):
        if os.path.exists(self.panic_file):
            if hashlib.sha256(girilen.encode()).hexdigest() == open(self.panic_file, "r").read(): return True
        return False
    def panik_aktif_mi(self): return os.path.exists(self.panic_file)
    def panik_calistir(self):
        try: self.conn.close()
        except: pass
        for f in [self.db_file, self.key_file, self.tfa_file]: 
            if os.path.exists(f): os.remove(f)
        self.anahtar_yukle_veya_olustur(); self.db_baslat(); return True
    def panik_sifresi_ayarla(self, sifre): open(self.panic_file, "w").write(hashlib.sha256(sifre.encode()).hexdigest())

    def master_kontrol(self, girilen):
        if not self.kurulum_var_mi(): return "YOK"
        if self.panik_kontrol(girilen): self.panik_calistir(); return "PANIK" 
        durum, veri = self.brute_force_kontrol("kontrol")
        if not durum: return f"KİLİTLİ: {veri} bekle"
        if hashlib.sha256(girilen.encode()).hexdigest() == open(self.hash_file, "r").read():
            self.brute_force_kontrol("basarili"); return True
        else: return f"HATA! Kalan Hak: {self.brute_force_kontrol('hata')}"
    def master_olustur(self, yeni): open(self.hash_file, "w").write(hashlib.sha256(yeni.encode()).hexdigest())

    def api_sizinti_kontrol(self, password):
        sha1 = hashlib.sha1(password.encode('utf-8')).hexdigest().upper()
        try:
            headers = {'User-Agent': 'KriptonPass-App'}
            res = requests.get(f"https://api.pwnedpasswords.com/range/{sha1[:5]}", headers=headers, timeout=10)
            if res.status_code==200:
                for line in res.text.splitlines():
                    if line.split(':')[0] == sha1[5:]: return int(line.split(':')[1])
            return 0
        except: return -1
    
    def yerel_zorluk_analizi(self, sifre):
        p=0; l=len(sifre)
        if l>=8: p+=1
        if l>=12: p+=1
        if any(c.isdigit() for c in sifre): p+=1
        if any(c.isupper() for c in sifre): p+=1
        if any(c in string.punctuation for c in sifre): p+=1 
        if p<=1: return "ÇOK ZAYIF", COLOR_DANGER, "risky"
        elif p==2: return "ZAYIF", "#E67E22", "risky"
        elif p==3: return "ORTA", "#F1C40F", "medium"
        elif p==4: return "GÜÇLÜ", COLOR_SUCCESS, "safe"
        else: return "MÜKEMMEL", COLOR_SUCCESS, "safe"

    def not_ekle(self, baslik, icerik):
        enc = self.fernet.encrypt(icerik.encode())
        self.cursor.execute("INSERT INTO notlar (baslik, icerik) VALUES (?,?)", (baslik, enc)); self.conn.commit()
    def notlari_getir(self): self.cursor.execute("SELECT * FROM notlar"); return self.cursor.fetchall()
    def not_sil(self, id_no): self.cursor.execute("DELETE FROM notlar WHERE id=?", (id_no,)); self.conn.commit()
    
    def sifre_ekle(self, plat, user, password):
        enc = self.fernet.encrypt(password.encode())
        self.cursor.execute("INSERT INTO hesaplar (platform, kullanıcı_adi, sifreli_sifre) VALUES (?,?,?)", (plat, user, enc)); self.conn.commit()
    def sifreleri_getir(self, sadece_riskli=False):
        self.cursor.execute("SELECT * FROM hesaplar"); tum = self.cursor.fetchall()
        if not sadece_riskli: return tum
        riskli = []
        for v in tum:
            try:
                if self.yerel_zorluk_analizi(self.sifre_coz(v[3]))[2] == "risky": riskli.append(v)
            except: pass
        return riskli
    def sifre_coz(self, enc_data): return self.fernet.decrypt(enc_data).decode()
    def sifre_guncelle(self, id_no, yeni_sifre):
        enc = self.fernet.encrypt(yeni_sifre.encode())
        self.cursor.execute("UPDATE hesaplar SET sifreli_sifre=? WHERE id=?", (enc, id_no)); self.conn.commit()
    def sifre_sil(self, id_no): self.cursor.execute("DELETE FROM hesaplar WHERE id=?", (id_no,)); self.conn.commit()

    def tfa_kurulum_baslat(self): s = pyotp.random_base32(); return s, pyotp.totp.TOTP(s).provisioning_uri(name="KriptonPass", issuer_name="Guvenlik")
    def tfa_kaydet(self, s): open(self.tfa_file, "wb").write(self.fernet.encrypt(s.encode()))
    def tfa_kontrol_et(self, kod):
        if not os.path.exists(self.tfa_file): return True
        try: return pyotp.TOTP(self.fernet.decrypt(open(self.tfa_file, "rb").read()).decode()).verify(kod)
        except: return False
    def tfa_aktif_mi(self): return os.path.exists(self.tfa_file)
    def tfa_kaldir(self): 
        if os.path.exists(self.tfa_file): os.remove(self.tfa_file)
    
    def genel_guvenlik_ozeti(self):
        veriler = self.sifreleri_getir(); toplam = len(veriler)
        if toplam == 0: return {"toplam": 0, "zayif": 0, "orta": 0, "guclu": 0, "puan": 0}
        zayif=0; orta=0; guclu=0; tpuan=0
        for v in veriler:
            try:
                _, _, tip = self.yerel_zorluk_analizi(self.sifre_coz(v[3]))
                if tip == "risky": zayif+=1; tpuan+=20
                elif tip == "medium": orta+=1; tpuan+=60
                elif tip == "safe": guclu+=1; tpuan+=100
            except: pass
        return {"toplam": toplam, "zayif": zayif, "orta": orta, "guclu": guclu, "puan": int(tpuan/toplam)}
    
    def yedek_al(self, path):
        # Şifreli hash verilerini yedekler, açık hali yedeklenmez.
        d = [{"p": x[1], "u": x[2], "e": x[3].hex()} for x in self.sifreleri_getir()]
        json.dump(d, open(path, "w"), indent=4)
        
    def yedek_yukle(self, path):
        d = json.load(open(path, "r")); c=0
        for x in d:
             self.cursor.execute("INSERT INTO hesaplar (platform, kullanıcı_adi, sifreli_sifre) VALUES (?,?,?)", (x["p"], x["u"], bytes.fromhex(x["e"]))); c+=1
        self.conn.commit(); return c
        
    def chrome_csv_import(self, path):
        c=0
        try:
            with open(path, "r", encoding="utf-8") as f:
                r = csv.reader(f); next(r)
                for row in r:
                    if len(row)>=4 and row[0] and row[2] and row[3]: self.sifre_ekle(row[0], row[2], row[3]); c+=1
        except: return -1
        return c

    def steg_gizle(self, img_path):
        sep = b"###KRIPTON###"; d = open(self.db_file, "rb").read()
        i = open(img_path, "rb").read(); n = os.path.dirname(img_path)+"/KRIPTON_"+os.path.basename(img_path)
        open(n, "wb").write(i+sep+d); return n
    def steg_cikar(self, img_path, out_path):
        sep = b"###KRIPTON###"; d = open(img_path, "rb").read()
        if sep in d: open(out_path, "wb").write(d.split(sep)[1]); return True
        return False
    def steg_ice_aktar(self, img_path):
        sep = b"###KRIPTON###"
        try:
            with open(img_path, "rb") as f: d = f.read()
            if sep not in d: return -2 
            db_bytes = d.split(sep)[1]
            fd, tmp = tempfile.mkstemp(); os.fdopen(fd, 'wb').write(db_bytes)
            c_tmp = sqlite3.connect(tmp); rows = c_tmp.cursor().execute("SELECT * FROM hesaplar").fetchall()
            c_tmp.close(); os.remove(tmp); c=0
            for r in rows: self.cursor.execute("INSERT INTO hesaplar (platform, kullanıcı_adi, sifreli_sifre) VALUES (?,?,?)", (r[1], r[2], r[3])); c+=1
            self.conn.commit(); return c
        except: return -1

# ==========================================
# FRONTEND
# ==========================================
class KriptonPassApp(ctk.CTk):
    def __init__(self):
        ctk.set_widget_scaling(1.0)
        ctk.set_window_scaling(1.0)
        super().__init__()
        self.backend = BackendManager()
        self.last_interaction = time.time()
        
        try:
            my_appid = 'kriptonpass.app.v1.0' 
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(my_appid)
        except: pass

        self.title("KriptonPass v1.0")
        self.geometry("1200x800") 
        self.after(0, lambda: self.state('zoomed'))

        self.logo_large = None
        self.logo_sidebar = None
        
        try:
            png_path = resource_path("logokriptonpass-Photoroom.png") 
            logo_pil = Image.open(png_path)
            w_orig, h_orig = logo_pil.size
            aspect_ratio = w_orig / h_orig

            target_w_sidebar = 300 
            target_h_sidebar = int(target_w_sidebar / aspect_ratio)
            self.logo_sidebar = ctk.CTkImage(light_image=logo_pil, dark_image=logo_pil, size=(target_w_sidebar, target_h_sidebar))
            
            h_large = 300
            w_large = int(h_large * aspect_ratio)
            self.logo_large = ctk.CTkImage(light_image=logo_pil, dark_image=logo_pil, size=(w_large, h_large))
            self.iconphoto(False, ImageTk.PhotoImage(logo_pil))
        except Exception as e:
            print(f"PNG Logo Hatası: {e}")

        try:
            ico_path = resource_path("logo.ico")
            self.iconbitmap(ico_path)
        except Exception as e:
            print(f"ICO Simge Hatası: {e}")

        saved = self.backend.tema_ayari_getir()
        ctk.set_appearance_mode(saved)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.bind("<Motion>", self.reset_timer)
        self.bind("<Key>", self.reset_timer)
        
        self.show_login_frame()
        self.check_idle_loop()

    def reset_timer(self, event=None): self.last_interaction = time.time()
    def check_idle_loop(self):
        if hasattr(self, 'nav_frame') and self.nav_frame.winfo_exists():
            if time.time() - self.last_interaction > AUTO_LOCK_SURESI:
                self.show_login_frame()
        self.after(1000, self.check_idle_loop)

    def notify(self, msg, color=COLOR_SUCCESS):
        bg_color = color
        if isinstance(color, tuple):
            bg_color = color[1] if ctk.get_appearance_mode() == "Dark" else color[0]
        n = ctk.CTkLabel(self, text=msg, fg_color=bg_color, text_color="white", corner_radius=10, height=40, font=("Arial", 14, "bold"))
        n.place(relx=0.5, rely=0.05, anchor="center"); self.after(3000, n.destroy)

    def open_virtual_keyboard_window(self, target_entry):
        vk = ctk.CTkToplevel(self); vk.title("Güvenli Klavye"); vk.geometry("900x450"); vk.attributes('-topmost', True)
        self.shift_on = False 
        keys_lower = [['1','2','3','4','5','6','7','8','9','0'],['q','w','e','r','t','y','u','i','o','p'],['a','s','d','f','g','h','j','k','l'],['z','x','c','v','b','n','m'],['!','@','#','$','%','^','&','*','(',')','_','+','-','=']]
        keys_upper = [['1','2','3','4','5','6','7','8','9','0'],['Q','W','E','R','T','Y','U','I','O','P'],['A','S','D','F','G','H','J','K','L'],['Z','X','C','V','B','N','M'],['!','@','#','$','%','^','&','*','(',')','_','+','-','=']]
        frame_keys = ctk.CTkFrame(vk, fg_color=COLOR_BG); frame_keys.pack(pady=20, padx=20, fill="both", expand=True)
        self.btn_refs = []
        def update_keys():
            keys = keys_upper if self.shift_on else keys_lower
            for i, row in enumerate(keys):
                for j, val in enumerate(row): self.btn_refs[i][j].configure(text=val, command=lambda x=val: press(x))
        def press(k): target_entry.insert("end", k)
        def toggle_shift(): self.shift_on = not self.shift_on; update_keys(); btn_shift.configure(fg_color=COLOR_ACCENT if self.shift_on else COLOR_CARD)
        def back(): cur = target_entry.get(); target_entry.delete(len(cur)-1, "end")
        for r_idx, row_keys in enumerate(keys_lower):
            row_frame = ctk.CTkFrame(frame_keys, fg_color="transparent"); row_frame.pack(pady=5)
            row_btns = []
            for k in row_keys:
                b = ctk.CTkButton(row_frame, text=k, width=50, height=50, corner_radius=10, fg_color=COLOR_CARD, text_color=COLOR_TEXT_MAIN, command=lambda x=k: press(x)); b.pack(side="left", padx=3); row_btns.append(b)
            self.btn_refs.append(row_btns)
        action_frame = ctk.CTkFrame(vk, fg_color="transparent"); action_frame.pack(pady=10)
        btn_shift = ctk.CTkButton(action_frame, text="SHIFT ⬆️", width=120, height=40, fg_color=COLOR_CARD, text_color=COLOR_TEXT_MAIN, command=toggle_shift); btn_shift.pack(side="left", padx=10)
        ctk.CTkButton(action_frame, text="⌫ Sil", width=120, height=40, fg_color=COLOR_DANGER, text_color="white", command=back).pack(side="left", padx=10)

    def ask_password_secure(self, title="Güvenlik Onayı"):
        dialog = ctk.CTkToplevel(self); dialog.geometry("450x280"); dialog.title(title); dialog.attributes('-topmost', True)
        dialog.update_idletasks()
        x = (self.winfo_screenwidth()-450)//2; y = (self.winfo_screenheight()-280)//2; dialog.geometry(f"+{x}+{y}")
        bg = ctk.CTkFrame(dialog, fg_color=COLOR_BG); bg.pack(fill="both", expand=True)
        ctk.CTkLabel(bg, text="🔒 " + title, font=("Montserrat", 18, "bold"), text_color=COLOR_TEXT_MAIN).pack(pady=(25, 10))
        ctk.CTkLabel(bg, text="İşlem için ana parolanızı girin", font=("Arial", 12), text_color=COLOR_TEXT_SUB).pack(pady=(0, 20))
        frame_ent = ctk.CTkFrame(bg, fg_color="transparent"); frame_ent.pack()
        ent = ctk.CTkEntry(frame_ent, show="*", width=240, height=40, corner_radius=10, fg_color=COLOR_CARD, text_color=COLOR_TEXT_MAIN); ent.pack(side="left", padx=5); ent.focus()
        ctk.CTkButton(frame_ent, text="⌨️", width=50, height=40, fg_color=COLOR_CARD, text_color=COLOR_TEXT_MAIN, hover_color=COLOR_ACCENT, command=lambda: self.open_virtual_keyboard_window(ent)).pack(side="left")
        result = {"valid": False}
        def confirm():
            if self.backend.master_kontrol(ent.get()) is True: result["valid"] = True; dialog.destroy()
            else: self.notify("Hatalı Parola!", COLOR_DANGER); ent.delete(0, 'end')
        ctk.CTkButton(bg, text="ONAYLA", width=300, height=45, fg_color=COLOR_SUCCESS, font=("Arial", 14, "bold"), command=confirm).pack(pady=25)
        dialog.wait_window(); return result["valid"]

    # --- LOGIN ---
    def show_login_frame(self):
        for w in self.winfo_children(): w.destroy()
        main_container = ctk.CTkFrame(self, fg_color=COLOR_BG); main_container.pack(fill="both", expand=True)
        main_container.grid_columnconfigure(0, weight=4); main_container.grid_columnconfigure(1, weight=6); main_container.grid_rowconfigure(0, weight=1)

        left_panel = ctk.CTkFrame(main_container, corner_radius=0, fg_color=COLOR_SIDEBAR[1]); left_panel.grid(row=0, column=0, sticky="nsew")
        left_content = ctk.CTkFrame(left_panel, fg_color="transparent"); left_content.place(relx=0.5, rely=0.5, anchor="center")
        if self.logo_large: ctk.CTkLabel(left_content, image=self.logo_large, text="").pack(pady=(0, 20))
        ctk.CTkLabel(left_content, text="KRIPTONPASS", font=("Montserrat", 36, "bold"), text_color="white").pack()
        ctk.CTkLabel(left_content, text="Gelişmiş Şifre Yönetim Uygulaması", font=("Arial", 14), text_color=COLOR_TEXT_SUB[1]).pack(pady=10)

        right_panel = ctk.CTkFrame(main_container, corner_radius=0, fg_color=COLOR_BG); right_panel.grid(row=0, column=1, sticky="nsew")
        form_frame = ctk.CTkFrame(right_panel, fg_color="transparent"); form_frame.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.6)
        
        is_setup = not self.backend.kurulum_var_mi()
        welcome_text = "Hoş Geldiniz" if not is_setup else "Kurulum"
        ctk.CTkLabel(form_frame, text=welcome_text, font=("Arial", 32, "bold"), text_color=COLOR_TEXT_MAIN, anchor="w").pack(fill="x", pady=(0, 5))
        ctk.CTkLabel(form_frame, text="Devam etmek için giriş yapın.", font=("Arial", 14), text_color=COLOR_TEXT_SUB, anchor="w").pack(fill="x", pady=(0, 30))

        self.lbl_status = ctk.CTkLabel(form_frame, text="", font=("Arial", 14), height=20, anchor="w"); self.lbl_status.pack(fill="x", pady=(0, 5))
        ctk.CTkLabel(form_frame, text="Ana Parola", font=("Arial", 12, "bold"), anchor="w", text_color=COLOR_TEXT_SUB).pack(fill="x", pady=(0, 5))
        
        self.entry_pass = ctk.CTkEntry(form_frame, show="*", height=50, font=("Arial", 16), corner_radius=10, border_width=2, fg_color=COLOR_CARD, border_color=COLOR_CARD, text_color=COLOR_TEXT_MAIN)
        self.entry_pass.pack(fill="x", pady=(0, 20)); self.entry_pass.bind('<Return>', lambda e: self.giris_yap())
        
        self.btn_login = ctk.CTkButton(form_frame, text="GİRİŞ YAP" if not is_setup else "OLUŞTUR", height=50, font=("Arial", 15, "bold"), corner_radius=10, fg_color=COLOR_ACCENT, command=self.giris_yap)
        self.btn_login.pack(fill="x", pady=(0, 15))
        
        ctk.CTkButton(form_frame, text="⌨️ Sanal Klavye", fg_color="transparent", text_color=COLOR_TEXT_SUB, hover_color=COLOR_CARD, command=lambda: self.open_virtual_keyboard_window(self.entry_pass)).pack()
        ctk.CTkLabel(right_panel, text="v1.0 Stable", font=("Arial", 10), text_color=COLOR_TEXT_SUB).place(relx=0.5, rely=0.95, anchor="center")

        kontrol = self.backend.brute_force_kontrol("kontrol")
        if not kontrol[0]: self.baslat_kilit_sayaci(kontrol[1])

    def giris_yap(self):
        p = self.entry_pass.get(); 
        if not p: return
        res = self.backend.master_kontrol(p)
        if res == "YOK": self.backend.master_olustur(p); self.show_main_app()
        elif res == "PANIK": self.show_main_app(); self.notify("⚠️ SİSTEM SIFIRLANDI", "orange")
        elif isinstance(res, str): 
            if "KİLİTLİ" in res:
                try: self.baslat_kilit_sayaci(int(res.split(":")[1]))
                except: pass
            else: self.lbl_status.configure(text=res, text_color=COLOR_DANGER); self.entry_pass.delete(0, 'end')
        elif res is True:
            if self.backend.tfa_aktif_mi(): self.step_2fa()
            else: self.show_main_app()

    def baslat_kilit_sayaci(self, saniye):
        self.entry_pass.delete(0, 'end'); self.entry_pass.configure(state="disabled", placeholder_text="KİLİTLENDİ")
        self.btn_login.configure(state="disabled"); self.sayac_dongusu(saniye)
    def sayac_dongusu(self, saniye):
        if saniye > 0:
            dk, sn = divmod(saniye, 60)
            self.lbl_status.configure(text=f"⛔ KİLİTLİ: {dk:02d}:{sn:02d}", text_color=COLOR_DANGER, font=("bold", 20))
            self.after(1000, lambda: self.sayac_dongusu(saniye - 1))
        else:
            self.lbl_status.configure(text="", text_color=COLOR_TEXT_SUB)
            self.entry_pass.configure(state="normal", placeholder_text="Ana Parola"); self.btn_login.configure(state="normal")

    def step_2fa(self):
        self.entry_pass.destroy()
        self.lbl_status.configure(text="📲 2FA Doğrulama Kodu", text_color=COLOR_ACCENT)
        self.entry_2fa = ctk.CTkEntry(self.lbl_status.master, placeholder_text="000 000", height=50, font=("Arial", 16), justify="center", corner_radius=10, fg_color=COLOR_CARD, text_color=COLOR_TEXT_MAIN)
        self.entry_2fa.pack(fill="x", pady=(0, 20), after=self.lbl_status); self.entry_2fa.focus(); self.entry_2fa.bind('<Return>', lambda e: self.verify_2fa())
        self.btn_login.configure(text="DOĞRULA", command=self.verify_2fa)
    def verify_2fa(self):
        if self.backend.tfa_kontrol_et(self.entry_2fa.get()): self.show_main_app()
        else: self.lbl_status.configure(text="❌ Kod Yanlış", text_color=COLOR_DANGER); self.entry_2fa.delete(0,'end')

    # --- MAIN APP ---
    def show_main_app(self):
        for w in self.winfo_children(): w.destroy()
        
        self.nav_frame = ctk.CTkFrame(self, width=330, corner_radius=0, fg_color=COLOR_SIDEBAR)
        self.nav_frame.grid(row=0, column=0, sticky="nsew"); self.nav_frame.grid_rowconfigure(6, weight=1)
        
        brand_box = ctk.CTkFrame(self.nav_frame, fg_color="transparent")
        brand_box.grid(row=0, column=0, padx=20, pady=(40, 20), sticky="ew")
        
        if self.logo_sidebar:
            logo_lbl = ctk.CTkLabel(brand_box, image=self.logo_sidebar, text="")
            logo_lbl.pack(pady=(0, 10))

        ctk.CTkLabel(brand_box, text="KriptonPass", font=("Montserrat", 28, "bold"), text_color=COLOR_TEXT_MAIN).pack()
        
        self.btns = {}
        menu_items = [("Ana Sayfa", self.go_home), ("Şifrelerim", lambda: self.go_list(False)), 
                      ("Gizli Notlar", self.go_notes), ("Yeni Ekle", self.go_add), ("Araçlar", self.go_tools)]
        
        for i, (n, cmd) in enumerate(menu_items, 1):
            b = ctk.CTkButton(self.nav_frame, text=n, fg_color="transparent", text_color=COLOR_TEXT_SUB,
                              hover_color=COLOR_BG, anchor="w", height=50, font=("Arial", 16, "bold"), command=cmd, corner_radius=10)
            b.grid(row=i, column=0, sticky="ew", padx=15, pady=5); self.btns[n] = b
            
        ctk.CTkButton(self.nav_frame, text="Çıkış Yap", fg_color=COLOR_DANGER, height=40, font=("Arial", 14, "bold"), text_color="white",
                      command=self.show_login_frame).grid(row=7, column=0, padx=25, pady=30, sticky="s")

        self.content = ctk.CTkFrame(self, corner_radius=0, fg_color=COLOR_BG)
        self.content.grid(row=0, column=1, sticky="nsew")
        self.go_home()

    def highlight(self, name):
        for k, b in self.btns.items(): 
            if k == name: b.configure(fg_color=COLOR_ACCENT, text_color="white")
            else: b.configure(fg_color="transparent", text_color=COLOR_TEXT_SUB)

    # --- DASHBOARD ---
    def go_home(self):
        self.highlight("Ana Sayfa")
        for w in self.content.winfo_children(): w.destroy()
        ozet = self.backend.genel_guvenlik_ozeti()
        
        banner = ctk.CTkFrame(self.content, fg_color=COLOR_ACCENT, corner_radius=20)
        banner.pack(pady=(40, 30), padx=40, fill="x")
        ctk.CTkLabel(banner, text="Güvenlik Merkezi", font=("Montserrat", 28, "bold"), text_color="white").pack(pady=(25,5), padx=30, anchor="w")
        ctk.CTkLabel(banner, text="Kasanızın anlık güvenlik durumu ve analizleri.", font=("Arial", 14), text_color="#E0F2FE").pack(pady=(0,25), padx=30, anchor="w")

        stats = ctk.CTkFrame(self.content, fg_color="transparent"); stats.pack(pady=0, padx=40, fill="x")
        
        def create_stat_card(parent, title, value, color, cmd=None):
            fr = ctk.CTkFrame(parent, fg_color=COLOR_CARD, corner_radius=20)
            fr.pack(side="left", fill="both", expand=True, padx=10)
            ctk.CTkLabel(fr, text=title, font=("Arial", 12, "bold"), text_color=COLOR_TEXT_SUB).pack(pady=(20,5), padx=20, anchor="w")
            ctk.CTkLabel(fr, text=str(value), font=("Montserrat", 36, "bold"), text_color=color).pack(pady=(0,10), padx=20, anchor="w")
            if cmd: 
                ctk.CTkButton(fr, text="İncele →", height=30, fg_color="transparent", text_color=COLOR_TEXT_MAIN, anchor="w", hover=False, command=cmd).pack(pady=(0,20), padx=20, anchor="w")
        
        create_stat_card(stats, "TOPLAM HESAP", ozet["toplam"], COLOR_TEXT_MAIN)
        create_stat_card(stats, "RİSKLİ ŞİFRE", ozet["zayif"], COLOR_DANGER, cmd=lambda: self.go_list(True) if ozet["zayif"]>0 else None)
        create_stat_card(stats, "GÜVENLİK PUANI", f"%{ozet['puan']}", COLOR_SUCCESS if ozet['puan']>70 else "#F1C40F")

        dist = ctk.CTkFrame(self.content, corner_radius=20, fg_color=COLOR_CARD); dist.pack(pady=30, padx=40, fill="x")
        ctk.CTkLabel(dist, text="Şifre Güç Dağılımı", font=("bold", 18), text_color=COLOR_TEXT_MAIN).pack(pady=20, padx=30, anchor="w")
        bar = ctk.CTkFrame(dist, fg_color="transparent"); bar.pack(pady=(0,20), padx=30, fill="x")
        def dbar(l, v, c):
            f = ctk.CTkFrame(bar, fg_color="transparent"); f.pack(fill="x", pady=8)
            ctk.CTkLabel(f, text=l, width=80, anchor="w", font=("Arial", 14, "bold"), text_color=COLOR_TEXT_MAIN).pack(side="left")
            p = ctk.CTkProgressBar(f, height=20, progress_color=c, corner_radius=10); p.pack(side="left", fill="x", expand=True, padx=15)
            p.set(v/ozet["toplam"] if ozet["toplam"]>0 else 0)
            ctk.CTkLabel(f, text=f"{v}", width=40, font=("Arial", 14, "bold"), text_color=COLOR_TEXT_MAIN).pack(side="right")
        dbar("Güçlü", ozet["guclu"], COLOR_SUCCESS); dbar("Orta", ozet["orta"], "#F1C40F"); dbar("Zayıf", ozet["zayif"], COLOR_DANGER)

    # --- LISTE ---
    def go_list(self, riskli_mod=False):
        self.highlight("Şifrelerim")
        for w in self.content.winfo_children(): w.destroy()
        
        head = ctk.CTkFrame(self.content, fg_color="transparent"); head.pack(fill="x", padx=40, pady=40)
        t = "⚠️ Riskli Şifreler" if riskli_mod else "Tüm Şifreler"
        ctk.CTkLabel(head, text=t, font=("Montserrat", 28, "bold"), text_color=COLOR_TEXT_MAIN).pack(side="left")
        ctk.CTkButton(head, text="+ YENİ EKLE", width=120, height=40, fg_color=COLOR_SUCCESS, font=("bold", 14), text_color="white", command=self.go_add).pack(side="right")
        if riskli_mod: ctk.CTkButton(self.content, text="← Tümünü Göster", fg_color="transparent", border_width=1, text_color=COLOR_TEXT_MAIN, command=lambda: self.go_list(False)).pack(pady=(0,20), padx=40, anchor="w")

        scroll = ctk.CTkScrollableFrame(self.content, fg_color="transparent"); scroll.pack(pady=0, padx=30, fill="both", expand=True)
        veriler = self.backend.sifreleri_getir(sadece_riskli=riskli_mod)
        if not veriler: ctk.CTkLabel(scroll, text="Liste boş.", text_color="gray").pack(pady=50)
        
        for d in veriler:
            row = ctk.CTkFrame(scroll, fg_color=COLOR_CARD, corner_radius=15); row.pack(fill="x", pady=5, padx=10)
            ctk.CTkLabel(row, text=d[1], font=("Arial", 16, "bold"), text_color=COLOR_TEXT_MAIN).pack(side="left", padx=20, pady=15)
            ctk.CTkLabel(row, text=d[2], font=("Arial", 14), text_color=COLOR_TEXT_SUB).pack(side="left")
            lbl = ctk.CTkLabel(row, text="••••••••", font=("Mono", 20), text_color=COLOR_TEXT_SUB); lbl.pack(side="left", padx=40)
            
            ctk.CTkButton(row, text="🗑️", width=50, height=40, fg_color=COLOR_DANGER, text_color="white", command=lambda b=row, i=d[0]: self.del_confirm(b, i)).pack(side="right", padx=5)
            ctk.CTkButton(row, text="✏️", width=50, height=40, fg_color="#F59E0B", text_color="white", command=lambda i=d[0]: self.edit_win(i)).pack(side="right", padx=5)
            ctk.CTkButton(row, text="📋", width=50, height=40, fg_color=COLOR_ACCENT, text_color="white", command=lambda e=d[3], b=row: self.copy_anim(e, b)).pack(side="right", padx=5)
            ctk.CTkButton(row, text="👁️", width=50, height=40, fg_color="#64748B", text_color="white", command=lambda l=lbl, e=d[3]: self.show_pass(l, e)).pack(side="right", padx=5)

    def del_confirm(self, btn_parent, id_no):
        for child in btn_parent.winfo_children():
            if child.cget("text") == "🗑️":
                child.configure(text="EMİN MİSİN?", width=100, fg_color=COLOR_DANGER, command=lambda: self.del_final(id_no))
                self.after(3000, lambda b=child, i=id_no: b.configure(text="🗑️", width=40, fg_color=COLOR_BG, command=lambda p=btn_parent, x=i: self.del_confirm(p, x)))

    def del_final(self, id_no):
        if self.ask_password_secure("Silme İşlemi Onayı"): self.backend.sifre_sil(id_no); self.notify("Silindi", COLOR_DANGER); self.go_list()
        else: self.go_list()

    def copy_anim(self, enc, row):
        # --- GÜVENLİK GÜNCELLEMESİ (30sn Kuralı) ---
        if not self.ask_password_secure("Kopyalama Onayı"): return
        try: 
            sifre = self.backend.sifre_coz(enc)
            pyperclip.copy(sifre)
            self.notify("Kopyalandı (30sn Sonra Silinir)", COLOR_SUCCESS)
            # 30 saniye sonra panoyu temizle
            self.after(30000, lambda: pyperclip.copy(""))
        except: pass

    def show_pass(self, lbl, enc):
        if self.ask_password_secure("Görüntüleme"):
            lbl.configure(text=self.backend.sifre_coz(enc), text_color=COLOR_SUCCESS, font=("Arial", 16)); self.after(5000, lambda: lbl.configure(text="••••••••", text_color=COLOR_TEXT_SUB, font=("Mono", 20)))

    def edit_win(self, id_no):
        if not self.ask_password_secure("Düzenleme"): return
        win = ctk.CTkToplevel(self); win.geometry("400x300"); win.title("Düzenle"); win.attributes('-topmost', True)
        bg = ctk.CTkFrame(win, fg_color=COLOR_BG); bg.pack(fill="both", expand=True)
        ctk.CTkLabel(bg, text="Yeni Şifre", font=("bold", 18), text_color=COLOR_TEXT_MAIN).pack(pady=30)
        ent = ctk.CTkEntry(bg, width=250, height=40, corner_radius=10, fg_color=COLOR_CARD, text_color=COLOR_TEXT_MAIN); ent.pack(pady=10)
        ctk.CTkButton(bg, text="GÜNCELLE", width=250, height=45, fg_color=COLOR_SUCCESS, font=("bold", 14), text_color="white", command=lambda: [self.backend.sifre_guncelle(id_no, ent.get()), win.destroy(), self.go_list(), self.notify("Güncellendi")] if ent.get() else None).pack(pady=20)

    # --- NOTLAR ---
    def go_notes(self):
        self.highlight("Gizli Notlar")
        for w in self.content.winfo_children(): w.destroy()
        
        head = ctk.CTkFrame(self.content, fg_color="transparent"); head.pack(fill="x", padx=40, pady=40)
        ctk.CTkLabel(head, text="Gizli Notlar", font=("Montserrat", 28, "bold"), text_color=COLOR_TEXT_MAIN).pack(side="left")
        
        add_box = ctk.CTkFrame(self.content, fg_color=COLOR_CARD, corner_radius=15); add_box.pack(fill="x", padx=40, pady=(0, 20))
        e_tit = ctk.CTkEntry(add_box, placeholder_text="Başlık", height=40, corner_radius=10, fg_color=COLOR_BG, text_color=COLOR_TEXT_MAIN); e_tit.pack(side="left", fill="x", expand=True, padx=10, pady=10)
        e_con = ctk.CTkEntry(add_box, placeholder_text="Gizli İçerik...", height=40, corner_radius=10, fg_color=COLOR_BG, text_color=COLOR_TEXT_MAIN); e_con.pack(side="left", fill="x", expand=True, padx=10, pady=10)
        ctk.CTkButton(add_box, text="+ EKLE", width=100, height=40, fg_color=COLOR_ACCENT, text_color="white", command=lambda: [self.backend.not_ekle(e_tit.get(), e_con.get()), self.notify("Not Eklendi"), self.go_notes()] if e_tit.get() else None).pack(side="right", padx=10)

        scroll = ctk.CTkScrollableFrame(self.content, fg_color="transparent"); scroll.pack(padx=30, fill="both", expand=True)
        for n in self.backend.notlari_getir():
            row = ctk.CTkFrame(scroll, fg_color=COLOR_CARD, corner_radius=15); row.pack(fill="x", pady=5, padx=10)
            ctk.CTkLabel(row, text=n[1], font=("bold", 16), text_color=COLOR_TEXT_MAIN).pack(side="left", padx=20, pady=15)
            lbl = ctk.CTkLabel(row, text="••••••••••••", text_color=COLOR_TEXT_SUB); lbl.pack(side="left", padx=20)
            
            def show_note(l, e):
                if self.ask_password_secure("Not Oku"): l.configure(text=self.backend.sifre_coz(e), text_color=COLOR_SUCCESS); self.after(10000, lambda: l.configure(text="••••••••••••", text_color=COLOR_TEXT_SUB))
            def del_note(id):
                if self.ask_password_secure("Not Sil"): self.backend.not_sil(id); self.go_notes()

            ctk.CTkButton(row, text="🗑️", width=40, height=40, fg_color=COLOR_BG, hover_color=COLOR_DANGER, text_color=COLOR_TEXT_MAIN, command=lambda i=n[0]: del_note(i)).pack(side="right", padx=5)
            ctk.CTkButton(row, text="📋", width=40, height=40, fg_color=COLOR_BG, text_color=COLOR_TEXT_MAIN, command=lambda e=n[2]: [pyperclip.copy(self.backend.sifre_coz(e)), self.notify("Kopyalandı")]).pack(side="right", padx=5)
            ctk.CTkButton(row, text="👁️", width=40, height=40, fg_color=COLOR_BG, text_color=COLOR_TEXT_MAIN, command=lambda l=lbl, e=n[2]: show_note(l, e)).pack(side="right", padx=5)

    # --- EKLE ---
    def go_add(self):
        self.highlight("Yeni Ekle")
        for w in self.content.winfo_children(): w.destroy()
        
        card = ctk.CTkFrame(self.content, fg_color=COLOR_CARD, corner_radius=30)
        card.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.6)
        
        ctk.CTkLabel(card, text="Yeni Şifre Ekle", font=("Montserrat", 24, "bold"), text_color=COLOR_TEXT_MAIN).pack(pady=30)

        self.e_plat = ctk.CTkEntry(card, placeholder_text="Platform (Örn: Instagram)", height=50, font=("Arial", 14), corner_radius=10, fg_color=COLOR_BG, text_color=COLOR_TEXT_MAIN)
        self.e_plat.pack(fill="x", padx=40, pady=10)
        self.e_user = ctk.CTkEntry(card, placeholder_text="Kullanıcı Adı / E-posta", height=50, font=("Arial", 14), corner_radius=10, fg_color=COLOR_BG, text_color=COLOR_TEXT_MAIN)
        self.e_user.pack(fill="x", padx=40, pady=10)
        
        pass_frame = ctk.CTkFrame(card, fg_color="transparent"); pass_frame.pack(fill="x", padx=40, pady=10)
        self.e_pass = ctk.CTkEntry(pass_frame, placeholder_text="Şifre", show="*", height=50, font=("Arial", 14), corner_radius=10, fg_color=COLOR_BG, text_color=COLOR_TEXT_MAIN)
        self.e_pass.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(pass_frame, text="👁️", width=50, height=50, fg_color=COLOR_BG, text_color=COLOR_TEXT_MAIN, command=lambda: self.e_pass.configure(show="" if self.e_pass.cget('show')=='*' else "*")).pack(side="left", padx=(10,0))
        ctk.CTkButton(pass_frame, text="⌨️", width=50, height=50, fg_color=COLOR_BG, text_color=COLOR_TEXT_MAIN, command=lambda: self.open_virtual_keyboard_window(self.e_pass)).pack(side="left", padx=(5,0))

        self.l_stat = ctk.CTkLabel(card, text="", font=("Arial", 12)); self.l_stat.pack(pady=5)

        tools = ctk.CTkFrame(card, fg_color="transparent"); tools.pack(pady=10)
        ctk.CTkButton(tools, text="🎲 Rastgele Üret", fg_color=COLOR_BG, text_color=COLOR_TEXT_MAIN, height=40, command=self.gen_p).pack(side="left", padx=5)
        ctk.CTkButton(tools, text="🕵️ Sızıntı Kontrol", fg_color=COLOR_BG, text_color=COLOR_TEXT_MAIN, height=40, command=self.chk_p).pack(side="left", padx=5)

        ctk.CTkButton(card, text="KAYDET", height=50, fg_color=COLOR_SUCCESS, font=("bold", 16), text_color="white", command=self.sav_p).pack(fill="x", padx=40, pady=30)

    def gen_p(self):
        p = ''.join(secrets.choice(string.ascii_letters+string.digits+"!@#$") for _ in range(16))
        self.e_pass.delete(0,'end'); self.e_pass.insert(0, p); self.e_pass.configure(show="")
    def chk_p(self):
        p = self.e_pass.get(); 
        if not p: return
        self.l_stat.configure(text="🔍 Analiz Ediliyor...", text_color="#F59E0B"); self.update(); self.after(500)
        c = self.backend.api_sizinti_kontrol(p)
        msg, color, _ = self.backend.yerel_zorluk_analizi(p)
        if c == -1: self.l_stat.configure(text="⚠️ İnternet Hatası", text_color="orange")
        elif c > 0: self.l_stat.configure(text=f"🚨 RİSKLİ: {c} Kez Sızmış! | Güç: {msg}", text_color=COLOR_DANGER)
        else: self.l_stat.configure(text=f"✅ GÜVENLİ: Sızıntı Yok | Güç: {msg}", text_color=color)
    def sav_p(self):
        if self.e_plat.get() and self.e_pass.get():
            self.backend.sifre_ekle(self.e_plat.get(), self.e_user.get(), self.e_pass.get())
            self.notify("Başarıyla Kaydedildi"); self.go_add()
        else: self.notify("Eksik Bilgi", "red")

    def open_2fa_setup(self):
        # 2FA Kurulum Penceresi
        win = ctk.CTkToplevel(self)
        win.title("2FA Kurulumu")
        win.geometry("400x550")
        win.attributes('-topmost', True)
        
        # Ekranın ortasında açılması için
        x = (self.winfo_screenwidth() - 400) // 2
        y = (self.winfo_screenheight() - 550) // 2
        win.geometry(f"+{x}+{y}")

        bg = ctk.CTkFrame(win, fg_color=COLOR_BG)
        bg.pack(fill="both", expand=True)

        ctk.CTkLabel(bg, text="Google Authenticator", font=("Montserrat", 20, "bold"), text_color=COLOR_TEXT_MAIN).pack(pady=(20, 5))
        ctk.CTkLabel(bg, text="Aşağıdaki QR kodu telefonunuzla taratın.", font=("Arial", 12), text_color=COLOR_TEXT_SUB).pack(pady=(0, 20))

        # Backend'den secret ve uri al
        secret, uri = self.backend.tfa_kurulum_baslat()
        
        # QR Kodu oluştur
        qr = qrcode.QRCode(box_size=10, border=2)
        qr.add_data(uri)
        qr.make(fit=True)
        
        # --- DÜZELTME BURADA ---
        # 1. .convert("RGB") ekledik (siyah beyaz modu bazen sorun çıkarır)
        img_qr = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        
        # 2. Resmi 'self' değişkenine atadık ki hafızadan silinmesin
        self.qr_image_ref = ctk.CTkImage(light_image=img_qr, dark_image=img_qr, size=(200, 200))
        
        lbl_qr = ctk.CTkLabel(bg, image=self.qr_image_ref, text="")
        lbl_qr.pack(pady=10)
        # -----------------------
        
        # Manuel kod gösterimi (kopyalamak için)
        ctk.CTkEntry(bg, placeholder_text=secret, width=250, justify="center", state="readonly").pack(pady=5)
        
        ctk.CTkLabel(bg, text="Telefonda üretilen kodu girin:", font=("Arial", 12, "bold"), text_color=COLOR_TEXT_MAIN).pack(pady=(20, 5))
        
        e_kod = ctk.CTkEntry(bg, width=200, height=40, font=("Arial", 18), justify="center", corner_radius=10)
        e_kod.pack(pady=5)
        
        def onayla():
            girilen = e_kod.get()
            totp = pyotp.TOTP(secret)
            if totp.verify(girilen):
                self.backend.tfa_kaydet(secret)
                self.notify("2FA Başarıyla Kuruldu!", COLOR_SUCCESS)
                win.destroy()
                self.go_tools() # Sayfayı yenile ki buton "Kaldır"a dönsün
            else:
                self.notify("Kod Hatalı!", COLOR_DANGER)
                e_kod.delete(0, 'end')

        ctk.CTkButton(bg, text="KURULUMU TAMAMLA", width=250, height=45, fg_color=COLOR_ACCENT, font=("bold", 14), command=onayla).pack(pady=20)

    # --- ARAÇLAR ---
    def go_tools(self):
        self.highlight("Araçlar")
        for w in self.content.winfo_children(): w.destroy()
        
        ctk.CTkLabel(self.content, text="Gelişmiş Araçlar", font=("Montserrat", 28, "bold"), text_color=COLOR_TEXT_MAIN).pack(pady=30, padx=40, anchor="w")
        
        grid = ctk.CTkScrollableFrame(self.content, fg_color="transparent")
        grid.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # --- 0. 2FA (İKİ AŞAMALI DOĞRULAMA) ---
        c_2fa = ctk.CTkFrame(grid, fg_color=COLOR_CARD, corner_radius=20)
        c_2fa.pack(fill="x", pady=10, padx=10)
        
        durum_text = "AKTİF ✅" if self.backend.tfa_aktif_mi() else "PASİF ❌"
        durum_renk = COLOR_SUCCESS if self.backend.tfa_aktif_mi() else COLOR_DANGER

        ctk.CTkLabel(c_2fa, text=f"🛡️  2FA Güvenliği ({durum_text})", font=("Arial", 16, "bold"), text_color=COLOR_TEXT_MAIN).pack(anchor="w", padx=20, pady=15)
        ctk.CTkLabel(c_2fa, text="Uygulama girişinde Google Authenticator kodu iste.", font=("Arial", 12), text_color=COLOR_TEXT_SUB).pack(anchor="w", padx=20, pady=(0,10))

        if not self.backend.tfa_aktif_mi():
            ctk.CTkButton(c_2fa, text="2FA Kurulumunu Başlat", fg_color=COLOR_ACCENT, text_color="white", height=40, anchor="w", command=self.open_2fa_setup).pack(fill="x", padx=20, pady=(5, 20))
        else:
            def kaldir_2fa():
                if self.ask_password_secure("2FA Kaldırma"):
                    self.backend.tfa_kaldir()
                    self.notify("2FA Kaldırıldı", COLOR_DANGER)
                    self.go_tools()

            ctk.CTkButton(c_2fa, text="2FA Korumasını Kaldır", fg_color=COLOR_DANGER, text_color="white", height=40, anchor="w", command=kaldir_2fa).pack(fill="x", padx=20, pady=(5, 20))

        # --- 1. VERİ TRANSFERİ & YEDEKLEME ---
        c1 = ctk.CTkFrame(grid, fg_color=COLOR_CARD, corner_radius=20)
        c1.pack(fill="x", pady=10, padx=10)
        ctk.CTkLabel(c1, text="💾  Veri Transferi ve Yedekleme", font=("Arial", 16, "bold"), text_color=COLOR_TEXT_MAIN).pack(anchor="w", padx=20, pady=15)
        
        def run_import():
            path = filedialog.askopenfilename(filetypes=[("CSV Dosyası", "*.csv")])
            if path:
                n = self.backend.chrome_csv_import(path)
                if n > 0: self.notify(f"{n} Şifre İçe Aktarıldı", COLOR_SUCCESS)
                elif n == 0: self.notify("Şifre Bulunamadı", "orange")
                else: self.notify("Format Hatası", COLOR_DANGER)
        
        btn_imp = ctk.CTkButton(c1, text="Chrome'dan İçe Aktar (.csv)", fg_color="#0F766E", text_color="white", height=40, anchor="w", command=run_import)
        btn_imp.pack(fill="x", padx=20, pady=5)

        def run_backup():
            path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON Kriptolu", "*.json")])
            if path:
                self.backend.yedek_al(path)
                self.notify("Yedek Şifreli Olarak Kaydedildi", COLOR_SUCCESS)

        btn_bkp = ctk.CTkButton(c1, text="Şifreli Yedek Al (.json)", fg_color="#0F766E", text_color="white", height=40, anchor="w", command=run_backup)
        btn_bkp.pack(fill="x", padx=20, pady=5)

        def run_restore():
            if not self.ask_password_secure("Yedek Yükleme"): return
            path = filedialog.askopenfilename(filetypes=[("JSON Kriptolu", "*.json")])
            if path:
                try:
                    n = self.backend.yedek_yukle(path)
                    self.notify(f"{n} Veri Geri Yüklendi", COLOR_SUCCESS)
                except: self.notify("Hatalı Yedek Dosyası", COLOR_DANGER)

        btn_rst = ctk.CTkButton(c1, text="Yedekten Geri Yükle", fg_color="#CA8A04", text_color="white", height=40, anchor="w", command=run_restore)
        btn_rst.pack(fill="x", padx=20, pady=(5, 20))

        # --- 2. AJAN MODU ---
        c2 = ctk.CTkFrame(grid, fg_color=COLOR_CARD, corner_radius=20)
        c2.pack(fill="x", pady=10, padx=10)
        ctk.CTkLabel(c2, text="🕵️  Ajan Modu (Resim İçine Gizle)", font=("Arial", 16, "bold"), text_color=COLOR_TEXT_MAIN).pack(anchor="w", padx=20, pady=15)
        
        ctk.CTkLabel(c2, text="Veritabanını bir resim dosyasının içine gizler veya gizlenmiş veriyi okur.", font=("Arial", 12), text_color=COLOR_TEXT_SUB).pack(anchor="w", padx=20, pady=(0,10))

        def run_hide_img():
            img = filedialog.askopenfilename(filetypes=[("Resim", "*.png;*.jpg;*.jpeg")])
            if img:
                out = self.backend.steg_gizle(img)
                self.notify(f"Gizlendi: {os.path.basename(out)}", COLOR_SUCCESS)
        
        def run_extract_img():
            if not self.ask_password_secure("Veri Çıkarma"): return
            img = filedialog.askopenfilename(filetypes=[("Resim", "*.png;*.jpg;*.jpeg")])
            if img:
                res = self.backend.steg_ice_aktar(img)
                if res >= 0: self.notify(f"{res} Hesap İçeri Aktarıldı", COLOR_SUCCESS)
                elif res == -2: self.notify("Bu resimde veri yok!", "orange")
                else: self.notify("Hata Oluştu", COLOR_DANGER)

        ctk.CTkButton(c2, text="Veritabanını Resme Göm", fg_color="#4338CA", text_color="white", height=40, anchor="w", command=run_hide_img).pack(fill="x", padx=20, pady=5)
        ctk.CTkButton(c2, text="Resimden Veri Çıkar & Birleştir", fg_color="#4338CA", text_color="white", height=40, anchor="w", command=run_extract_img).pack(fill="x", padx=20, pady=(5, 20))

        # --- 3. PANİK MODU ---
        c3 = ctk.CTkFrame(grid, fg_color=COLOR_DANGER, corner_radius=20)
        c3.pack(fill="x", pady=20, padx=10)
        ctk.CTkLabel(c3, text="☢️  PANİK PROTOKOLÜ", font=("Arial", 16, "bold"), text_color="white").pack(anchor="w", padx=20, pady=(15,5))
        ctk.CTkLabel(c3, text="Panik modunu açarken dikkatli olunmalıdır.", font=("Arial", 12), text_color="white").pack(anchor="w", padx=20, pady=(0,15))
        
        def set_panic_pass():
            if not messagebox.askyesno("GİZLİ PROTOKOL UYARISI", "BU ÇOK TEHLİKELİDİR!\n\nEğer giriş ekranına 'Panik Şifresi'ni yazarsanız, TÜM VERİLER SİLİNİR ve kurtarılamaz.\n\nBu şifre sadece baskı altındayken verileri yok etmek içindir.\n\nDevam etmek istiyor musun?"):
                return

            if not self.ask_password_secure("Panik Ayarı"): return
            new_p = simpledialog.askstring("Panik", "Yeni Panik Şifresi Belirle:")
            if new_p:
                self.backend.panik_sifresi_ayarla(new_p)
                self.notify("Panik Şifresi Aktif!", "white")
                self.show_login_frame() 

        btn_txt = "Panik Şifresini Değiştir" if self.backend.panik_aktif_mi() else "Panik Şifresi Oluştur"
        ctk.CTkButton(c3, text=btn_txt, fg_color="white", text_color=COLOR_DANGER[1], hover_color="gray90", command=set_panic_pass).pack(fill="x", padx=20, pady=(0,15))

if __name__ == "__main__":
    app = KriptonPassApp()
    app.mainloop()