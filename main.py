import os
import sys
import random
import ctypes
import winreg
import pystray
import threading
import configparser
import subprocess
from PIL import Image
from datetime import datetime

# ---------- RESOURCE PATH (برای PyInstaller) ----------
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# ---------- SINGLE INSTANCE CHECK ----------
def is_already_running():
    mutex_name = "SimpleWallpaperChanger_Unique_ID_12345"
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)
    if ctypes.windll.kernel32.GetLastError() == 183:
        return True
    return False

# ---------- PATHS ----------
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
    APP_PATH = sys.executable
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    APP_PATH = sys.executable + " " + os.path.abspath(__file__)

WALLPAPER_DIR = os.path.join(BASE_DIR, "Wallpapers")
ICON_PATH = resource_path("icon.png")

SETTINGS_FILE = os.path.join(BASE_DIR, "settings.ini")
HISTORY_FILE = os.path.join(BASE_DIR, "history.ini")

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "SimpleWallpaperChanger"

EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp")

numbers = [1, 2, 3, 4, 5, 10, 15, 20, 30]

# ---------- SETTINGS ----------
config = configparser.ConfigParser()

auto_change_enabled = False
interval_seconds = 60
last_change = None

tray_icon = None
total_count = 0

def load_settings():
    global auto_change_enabled, interval_seconds, last_change

    if os.path.exists(SETTINGS_FILE):
        config.read(SETTINGS_FILE)

    auto_change_enabled = config.getboolean("GENERAL", "auto", fallback=False)
    interval_seconds = config.getint("GENERAL", "interval", fallback=60)

    t = config.get("GENERAL", "last_change", fallback=None)
    if t:
        try:
            last_change = datetime.fromisoformat(t)
        except:
            last_change = None


def save_settings():
    config["GENERAL"] = {
        "auto": str(auto_change_enabled),
        "interval": str(interval_seconds),
        "last_change": last_change.isoformat() if last_change else ""
    }
    with open(SETTINGS_FILE, "w") as f:
        config.write(f)

# ---------- STARTUP ----------
def is_startup_enabled():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY)
        winreg.QueryValueEx(key, APP_NAME)
        winreg.CloseKey(key)
        return True
    except FileNotFoundError:
        return False


def enable_startup():
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE)
    winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, APP_PATH)
    winreg.CloseKey(key)


def disable_startup():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE)
        winreg.DeleteValue(key, APP_NAME)
        winreg.CloseKey(key)
    except FileNotFoundError:
        pass


def toggle_startup(icon, item):
    if is_startup_enabled():
        disable_startup()
    else:
        enable_startup()
    icon.update_menu()

# ---------- HISTORY ----------
def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return [x.strip() for x in f if x.strip()]


def write_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        if history:
            f.write("\n".join(history) + "\n")

# ---------- TOOLTIP ----------
def get_tooltip_text(path):
    global total_count

    if not path or not os.path.exists(path):
        return "Simple Wallpaper Changer"

    history = load_history()
    current_index = len(history)

    file_name = os.path.basename(path)
    parent_dir = os.path.basename(os.path.dirname(path))

    return f"Simple Wallpaper Changer\n{parent_dir} / {file_name}\n{current_index} / {total_count}"

# ---------- EXPLORER ----------
def open_current_wallpaper_in_explorer(icon, item):
    history = load_history()

    if not history:
        return

    current_path = history[-1]

    if os.path.exists(current_path):
        normalized = os.path.normpath(current_path)
        subprocess.Popen(f'explorer.exe /select,"{normalized}"')

# ---------- ABOUT ----------
def show_about(icon=None, item=None):
    def _display():
        text = (
            "Simple Wallpaper Changer\n"
            "A lightweight system tray wallpaper changer.\n\n"
            "Version: 1.3\n"
            "Date: 2026/06/03\n\n"
            "Author: Ghasem Nazari\n"
            "Email: Ghasem.Nazari@gmail.com\n"
            "Github: qsmnzr"
        )
        ctypes.windll.user32.MessageBoxW(0, text, "About", 0x40)

    threading.Thread(target=_display, daemon=True).start()

# ---------- SAMPLE WALLPAPERS ----------
def ensure_sample_wallpapers():
    solids = os.path.join(WALLPAPER_DIR, "Solids")

    if os.path.exists(solids):
        return

    os.makedirs(solids, exist_ok=True)

    colors = {
        "White": (255,255,255),
        "Blue": (0,0,255),
        "Green": (0,128,0),
        "Yellow": (255,255,0),
        "Red": (255,0,0),
        "Black": (0,0,0),
        "Brown": (101,67,33)
    }

    for name,rgb in colors.items():
        img = Image.new("RGB",(3840,2160),rgb)
        img.save(os.path.join(solids,f"{name}.png"))

# ---------- WALLPAPER ----------
def get_all_wallpapers():
    images = []

    if not os.path.exists(WALLPAPER_DIR):
        return images

    for root,_,files in os.walk(WALLPAPER_DIR):
        for f in files:
            if f.lower().endswith(EXTENSIONS):
                images.append(os.path.abspath(os.path.join(root,f)))

    return images


def apply_wallpaper(path, add_to_history=True):
    global last_change, tray_icon

    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,r"Control Panel\Desktop",0,winreg.KEY_SET_VALUE)
    winreg.SetValueEx(key,"WallpaperStyle",0,winreg.REG_SZ,"10")
    winreg.SetValueEx(key,"TileWallpaper",0,winreg.REG_SZ,"0")
    winreg.CloseKey(key)

    ctypes.windll.user32.SystemParametersInfoW(20,0,path,3)

    if add_to_history:
        history = load_history()
        history.append(path)
        write_history(history)

    last_change = datetime.now()
    save_settings()

    if tray_icon:
        tray_icon.title = get_tooltip_text(path)

# ---------- NEXT ----------
def set_random_wallpaper(icon=None,item=None):

    images = get_all_wallpapers()

    if not images:
        return

    history = load_history()

    available = [i for i in images if i not in history]

    if not available:
        history=[]
        write_history(history)
        available=images

    apply_wallpaper(random.choice(available))

# ---------- PREVIOUS ----------
def set_previous_wallpaper(icon=None,item=None):

    history = load_history()

    if len(history) < 2:
        return

    last = history.pop()

    history.insert(0,last)

    write_history(history)

    new_wallpaper = history[-1]

    apply_wallpaper(new_wallpaper, add_to_history=False)

# ---------- AUTO ----------
stop_event = threading.Event()

def auto_worker():

    while not stop_event.is_set():

        if not auto_change_enabled:
            stop_event.wait(1)
            continue

        now = datetime.now()

        step = interval_seconds

        epoch = int(now.timestamp())

        next_boundary = epoch - (epoch % step) + step

        wait_time = next_boundary - epoch

        if wait_time > 0:
            stop_event.wait(wait_time)

        if auto_change_enabled:
            set_random_wallpaper()

# ---------- MENU ----------
def toggle_auto(icon,item):

    global auto_change_enabled

    auto_change_enabled = not auto_change_enabled

    save_settings()

    icon.update_menu()


def set_interval(value):

    global interval_seconds

    interval_seconds=value

    save_settings()


def get_interval_text():

    s=interval_seconds

    if s%86400==0: return f"{s//86400} Day"
    if s%3600==0: return f"{s//3600} Hour"
    if s%60==0: return f"{s//60} Minute"

    return f"{s} Sec"


def create_number_menu(mult):

    items=[]

    for n in numbers:

        value=n*mult

        def make_action(v):
            return lambda icon,item:set_interval(v)

        def make_checked(v):
            return lambda item:interval_seconds==v

        items.append(pystray.MenuItem(str(n),make_action(value),checked=make_checked(value)))

    return pystray.Menu(*items)


def create_menu():

    return pystray.Menu(

        pystray.MenuItem("Next Wallpaper",set_random_wallpaper,default=True),

        pystray.MenuItem("Previous Wallpaper",set_previous_wallpaper),

        pystray.MenuItem("Open in Explorer",open_current_wallpaper_in_explorer),

        pystray.Menu.SEPARATOR,

        pystray.MenuItem(lambda item:f"Auto Change ({get_interval_text()})",toggle_auto,checked=lambda item:auto_change_enabled),

        pystray.MenuItem("Start with Windows",toggle_startup,checked=lambda item:is_startup_enabled()),

        pystray.MenuItem("Every",pystray.Menu(

            pystray.MenuItem("Minute",create_number_menu(60)),

            pystray.MenuItem("Hour",create_number_menu(3600)),

            pystray.MenuItem("Day",create_number_menu(86400)),

        )),

        pystray.Menu.SEPARATOR,

        pystray.MenuItem("About",show_about),

        pystray.MenuItem("Exit",lambda icon,item:icon.stop())

    )

# ---------- MAIN ----------
if __name__=="__main__":
    
    if is_already_running():
        sys.exit(0)

    ensure_sample_wallpapers()

    load_settings()

    all_images=get_all_wallpapers()

    total_count=len(all_images)

    history=load_history()

    initial_path = history[-1] if history else None

    if os.path.exists(ICON_PATH):
        image=Image.open(ICON_PATH)
    else:
        image=Image.new("RGB",(64,64),(70,120,200))

    icon=pystray.Icon(
        "WallpaperChanger",
        image,
        get_tooltip_text(initial_path),
        create_menu()
    )

    tray_icon=icon

    if not history:
        set_random_wallpaper()

    threading.Thread(target=auto_worker,daemon=True).start()

    icon.run()
