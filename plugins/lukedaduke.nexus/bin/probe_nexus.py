#!/usr/bin/python3
"""Hardware topology probe for the lukedaduke.nexus panel.

All external tools run by absolute path under a fixed minimal environment
with a per-call byte budget and deadline; the whole job self-terminates at
JOB_DEADLINE_S. Device-controlled strings are length-capped before they
reach the QML layer.
"""
import json, os, glob, selectors, shutil, signal, subprocess, sys, time

JOB_DEADLINE_S = 8
MAX_OUT_BYTES = 262144
MAX_STR = 64
MAX_ITEMS = 64

SAFE_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"
SAFE_ENV = {"PATH": SAFE_PATH, "LC_ALL": "C", "LANG": "C"}

# Universal hardware dictionary
KNOWN_HARDWARE = {
    "05ac:12a8": ("iPhone Link", "Mobile", "󰏲", "Fast Charge & Data Sync"),
    "05ac:024f": ("USB Keyboard Bridge", "Input", "󰌌", "CYH Hardware Adapter"),
    "3443:60bb": ("NexiGo N60 Pro FHD", "Camera", "󰖠", "1080p Webcam + Stereo Mic"),
    "346d:5678": ("USB 3.0 Flash Drive", "Storage", "󱊞", "Ventoy Multi-Boot Stick"),
    "0bda:8153": ("Gigabit Ethernet", "Network", "󰈀", "Realtek 1000M Wired Port"),
    "0bda:1100": ("Dock Management", "Bridge", "󰕓", "Hotplug & Power Controller"),
    "2109:8884": ("DisplayPort Alt-Mode", "Display", "󰡁", "External Monitor Output"),
    "2109:2822": ("Dock USB 2.0 Hub", "Hub", "󰕓", "VIA Labs VL822 High-Speed"),
    "2109:0822": ("Dock USB 3.1 Hub", "Hub", "󰕓", "VIA Labs VL822 10 Gbps"),
    "0bda:5411": ("Dock Expansion Hub", "Hub", "󰕓", "Realtek RTS5411 USB 2.0"),
    "0bda:0411": ("Dock USB 3.1 Hub", "Hub", "󰕓", "Realtek RTS5411 USB 3.0"),
    "1a86:8095": ("Multi-Port Splitter", "Hub", "󰕓", "WCH High-Speed Controller"),
    "27c6:63ac": ("Fingerprint Sensor", "Security", "󰌆", "Power Button Biometric"),
    "0c45:672e": ("Integrated Webcam", "Camera", "󰖠", "Internal HD Video Sensor"),
    "8087:0026": ("Bluetooth Radio", "Wireless", "󰂯", "Intel AX201 HCI Adapter"),
}


def _tool(name):
    """Absolute path for an external helper, resolved under SAFE_PATH only."""
    return shutil.which(name, path=SAFE_PATH)


def _kill_tree(proc):
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except (OSError, ProcessLookupError):
        pass
    try:
        proc.wait(timeout=0.5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (OSError, ProcessLookupError):
            pass
        try:
            proc.wait(timeout=0.5)
        except subprocess.TimeoutExpired:
            pass


def _run(argv, timeout=2.0, max_bytes=MAX_OUT_BYTES):
    """Run argv with minimal env, hard deadline, producer byte cap.

    Child runs in its own process group so TERM/KILL reaches the tree.
    Returns stdout text or None on failure/timeout/overflow.
    """
    if not argv or not argv[0]:
        return None
    try:
        proc = subprocess.Popen(
            argv, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            env=SAFE_ENV, start_new_session=True,
        )
    except OSError:
        return None
    buf = bytearray()
    deadline = time.monotonic() + timeout
    completed = False
    sel = selectors.DefaultSelector()
    try:
        sel.register(proc.stdout, selectors.EVENT_READ)
        while True:
            if proc.poll() is not None:
                tail = proc.stdout.read()
                if tail:
                    buf += tail
                completed = True
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            if not sel.select(remaining):
                break
            try:
                chunk = os.read(proc.stdout.fileno(), 65536)
            except OSError:
                break
            if not chunk:
                completed = True
                break
            buf += chunk
            if len(buf) > max_bytes:
                break
    finally:
        sel.close()
        if proc.poll() is None:
            _kill_tree(proc)
        try:
            proc.stdout.close()
        except OSError:
            pass
    if not completed or len(buf) > max_bytes:
        return None
    return buf.decode(errors="replace")


def _clip(value, limit=MAX_STR):
    return str(value or "")[:limit]


def resolve_device(vid_pid, raw_product, raw_mfg, dev_class):
    if vid_pid in KNOWN_HARDWARE:
        return KNOWN_HARDWARE[vid_pid]

    p = (raw_product or "").lower()
    m = (raw_mfg or "").lower()

    if dev_class == "09":
        return (f"{raw_mfg or 'Generic'} Hub", "Hub", "󰕓", "USB Splitter / Cascade")
    if "keyboard" in p or "keyboard" in m:
        return (f"{raw_mfg or 'USB'} Keyboard", "Input", "󰌌", "Human Interface Device")
    if "mouse" in p or "trackpad" in p:
        return (f"{raw_mfg or 'USB'} Mouse", "Input", "󰍽", "Pointer Device")
    if "webcam" in p or "camera" in p:
        return (f"{raw_mfg or 'USB'} Camera", "Camera", "󰖠", "Video Capture")
    if "audio" in p or "headset" in p or "mic" in p:
        return (f"{raw_mfg or 'USB'} Audio", "Audio", "󰋋", "Sound In/Out")
    if "disk" in p or "storage" in p or "flash" in p:
        return (f"{raw_mfg or 'USB'} Drive", "Storage", "󱊞", "External Media")
    if "lan" in p or "ethernet" in p:
        return (f"{raw_mfg or 'USB'} Ethernet", "Network", "󰈀", "Wired Network Interface")
    if "phone" in p or "iphone" in p or "android" in p:
        return (f"{raw_mfg or 'Mobile'} Phone", "Mobile", "󰏲", "Smart Device")

    name = raw_product if raw_product and raw_product != "Generic Device" else (raw_mfg or "USB Peripheral")
    return (name, "Peripheral", "󱊞", "Connected Device")

def get_nexus():
    # USB Devices
    usb_list = []
    for d in sorted(glob.glob("/sys/bus/usb/devices/[0-9]*"))[:MAX_ITEMS]:
        base = os.path.basename(d)
        if ":" in base: continue
        def rf(f):
            p = os.path.join(d, f)
            if os.path.exists(p):
                try: return open(p).read(4096).strip()
                except: return ""
            return ""
        vid = rf("idVendor")
        pid = rf("idProduct")
        if not vid or not pid: continue
        vid_pid = f"{vid}:{pid}"
        prod = _clip(rf("product"))
        mfg = _clip(rf("manufacturer"))
        cls = rf("bDeviceClass") or "00"
        speed = rf("speed") or "0"
        speed_tag = "10G" if speed == "10000" else ("5G" if speed == "5000" else ("480M" if speed == "480" else "12M"))
        runtime = rf("power/runtime_status") or "active"

        name, cat, icon, desc = resolve_device(vid_pid, prod, mfg, cls)
        is_hub = cls == "09"

        usb_list.append({
            "id": _clip(base, 32),
            "name": _clip(name),
            "category": cat,
            "desc": _clip(desc),
            "speed": speed_tag,
            "status": "ONLINE" if runtime == "active" else "SLEEP",
            "is_hub": is_hub,
            "icon": icon,
            "tier": base.count(".") if "-" in base else 0
        })

    # Bluetooth
    bt_list = []
    bt = _tool("bluetoothctl")
    if bt:
        out = _run([bt, "devices", "Connected"], timeout=2, max_bytes=65536)
        if out:
            for line in out.splitlines()[:MAX_ITEMS]:
                if line.startswith("Device"):
                    p = line.split(" ", 2)
                    mac = _clip(p[1], 24)
                    name = _clip(p[2]) if len(p)>2 else "Bluetooth Device"
                    icon = "󰂯"
                    cat = "Wireless"
                    desc = "Connected & Active"
                    if "mchncl" in name.lower():
                        name = "MX Mechanical Keyboard"
                        cat = "Keyboard"
                        icon = "󰌌"
                    elif "master" in name.lower():
                        name = "MX Master 3S Mouse"
                        cat = "Mouse"
                        icon = "󰍽"
                    elif "anc" in name.lower() or "pod" in name.lower():
                        name = "Status Between 3ANC"
                        cat = "Earbuds"
                        icon = "󰋋"
                    bt_list.append({
                        "mac": mac,
                        "name": name,
                        "category": cat,
                        "desc": desc,
                        "icon": icon,
                        "status": "ONLINE"
                    })

    # Networks
    net_list = []
    ip = _tool("ip")
    if ip:
        raw = _run([ip, "-j", "addr"], timeout=2)
        try:
            ip_out = json.loads(raw) if raw else []
        except ValueError:
            ip_out = []
        for iface in ip_out[:MAX_ITEMS]:
            name = _clip(iface.get("ifname", ""), 32)
            state = iface.get("operstate", "UNKNOWN")
            if name == "lo" or name.startswith("veth") or name.startswith("br-") or name == "docker0": continue
            ips = [a.get("local") for a in iface.get("addr_info", [])[:16] if a.get("family") == "inet"]
            ip_str = _clip(ips[0], 48) if ips else "No IP"

            title = name
            desc = "Network"
            icon = "󰈀"
            if name == "enp0s20f0u1u2u4":
                title = "Dock Gigabit LAN"
                desc = "High-speed wired link"
                icon = "󰈀"
            elif name.startswith("wl"):
                title = "Wi-Fi 6 Wireless"
                desc = "Primary Wi-Fi connection"
                icon = "󰤨"
            elif name == "nordlynx":
                title = "NordVPN Tunnel"
                desc = "Encrypted VPN connection"
                icon = "󰖂"
            elif name == "tailscale0":
                title = "Tailscale Mesh"
                desc = "Homelab & server overlay"
                icon = "󰖂"

            net_list.append({
                "name": title,
                "desc": desc,
                "ip": ip_str,
                "icon": icon,
                "status": "CONNECTED" if (state == "UP" or ips) else "OFFLINE"
            })

    # Storage
    storage_list = []
    lsblk = _tool("lsblk")
    if lsblk:
        raw = _run([lsblk, "-J", "-o", "NAME,MODEL,TRAN,SIZE,MOUNTPOINTS,TYPE"], timeout=2)
        try:
            ls_out = json.loads(raw) if raw else {}
        except ValueError:
            ls_out = {}
        for dev in (ls_out.get("blockdevices") or [])[:MAX_ITEMS]:
            if dev.get("type") == "loop": continue
            name = _clip(dev.get("name"), 32)
            model = _clip(dev.get("model"))
            tran = _clip(dev.get("tran"), 16) or "ram"
            size = _clip(dev.get("size"), 16)
            mounts = []
            def walk(d):
                for m in d.get("mountpoints") or []:
                    if m and len(mounts) < 16: mounts.append(_clip(m, 128))
                for ch in (d.get("children") or [])[:32]:
                    walk(ch)
            walk(dev)

            title = f"Storage ({name})"
            desc = f"{tran.upper()} drive"
            icon = "󰋊"
            if "PC711" in model:
                title = "OS Root NVMe (512GB)"
                desc = "Encrypted System Drive (/home)"
            elif "SN520" in model:
                title = "Data NVMe (256GB)"
                desc = "Fast Storage (/mnt/data)"
            elif tran == "usb" or name.startswith("sd"):
                title = f"USB Flash Drive ({size})"
                desc = "Ventoy Multi-Boot USB Stick"
                icon = "󱊞"
            elif name == "zram0":
                title = f"ZRAM Fast Swap ({size})"
                desc = "In-memory RAM swap"
                icon = "󰡨"

            storage_list.append({
                "name": _clip(title),
                "desc": _clip(desc),
                "size": size,
                "mount": mounts[0] if mounts else "Unmounted",
                "icon": icon,
                "status": "MOUNTED" if mounts else "READY"
            })

    return {
        "ok": True,
        "usb": usb_list[:MAX_ITEMS],
        "bluetooth": bt_list[:MAX_ITEMS],
        "network": net_list[:MAX_ITEMS],
        "storage": storage_list[:MAX_ITEMS]
    }

if __name__ == "__main__":
    signal.signal(signal.SIGALRM, lambda *_: os._exit(124))
    signal.alarm(JOB_DEADLINE_S)
    sys.stdout.write(json.dumps(get_nexus())[:MAX_OUT_BYTES] + "\n")
