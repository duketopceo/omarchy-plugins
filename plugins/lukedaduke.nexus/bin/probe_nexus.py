#!/usr/bin/env python3
import json, os, glob, subprocess, sys

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
    "0bda:0411": ("Dock Expansion Hub", "Hub", "󰕓", "Realtek RTS5411 USB 3.0"),
    "1a86:8095": ("Multi-Port Splitter", "Hub", "󰕓", "WCH High-Speed Controller"),
    "27c6:63ac": ("Fingerprint Sensor", "Security", "󰌆", "Power Button Biometric"),
    "0c45:672e": ("Integrated Webcam", "Camera", "󰖠", "Internal HD Video Sensor"),
    "8087:0026": ("Bluetooth Radio", "Wireless", "󰂯", "Intel AX201 HCI Adapter"),
}

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
    for d in sorted(glob.glob("/sys/bus/usb/devices/[0-9]*")):
        base = os.path.basename(d)
        if ":" in base: continue
        def rf(f):
            p = os.path.join(d, f)
            if os.path.exists(p):
                try: return open(p).read().strip()
                except: return ""
            return ""
        vid = rf("idVendor")
        pid = rf("idProduct")
        if not vid or not pid: continue
        vid_pid = f"{vid}:{pid}"
        prod = rf("product") or ""
        mfg = rf("manufacturer") or ""
        cls = rf("bDeviceClass") or "00"
        speed = rf("speed") or "0"
        speed_tag = "10G" if speed == "10000" else ("5G" if speed == "5000" else ("480M" if speed == "480" else "12M"))
        runtime = rf("power/runtime_status") or "active"

        name, cat, icon, desc = resolve_device(vid_pid, prod, mfg, cls)
        is_hub = cls == "09"

        usb_list.append({
            "id": base,
            "name": name,
            "category": cat,
            "desc": desc,
            "speed": speed_tag,
            "status": "ONLINE" if runtime == "active" else "SLEEP",
            "is_hub": is_hub,
            "icon": icon,
            "tier": base.count(".") if "-" in base else 0
        })

    # Bluetooth
    bt_list = []
    try:
        out = subprocess.check_output(["bluetoothctl", "devices", "Connected"], stderr=subprocess.DEVNULL, timeout=2).decode()
        for line in out.splitlines():
            if line.startswith("Device"):
                p = line.split(" ", 2)
                mac = p[1]
                name = p[2] if len(p)>2 else "Bluetooth Device"
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
    except Exception: pass

    # Networks
    net_list = []
    try:
        ip_out = json.loads(subprocess.check_output(["ip", "-j", "addr"], stderr=subprocess.DEVNULL, timeout=2).decode())
        for iface in ip_out:
            name = iface.get("ifname", "")
            state = iface.get("operstate", "UNKNOWN")
            if name == "lo" or name.startswith("veth") or name.startswith("br-") or name == "docker0": continue
            ips = [a.get("local") for a in iface.get("addr_info", []) if a.get("family") == "inet"]
            ip_str = ips[0] if ips else "No IP"
            
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
    except Exception: pass

    # Storage
    storage_list = []
    try:
        ls_out = json.loads(subprocess.check_output(["lsblk", "-J", "-o", "NAME,MODEL,TRAN,SIZE,MOUNTPOINTS,TYPE"], stderr=subprocess.DEVNULL, timeout=2).decode())
        for dev in ls_out.get("blockdevices", []):
            if dev.get("type") == "loop": continue
            name = dev.get("name")
            model = dev.get("model") or ""
            tran = dev.get("tran") or "ram"
            size = dev.get("size")
            mounts = []
            def walk(d):
                for m in d.get("mountpoints") or []:
                    if m: mounts.append(m)
                for ch in d.get("children") or []:
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
                "name": title,
                "desc": desc,
                "size": size,
                "mount": mounts[0] if mounts else "Unmounted",
                "icon": icon,
                "status": "MOUNTED" if mounts else "READY"
            })
    except Exception: pass

    return {
        "ok": True,
        "usb": usb_list,
        "bluetooth": bt_list,
        "network": net_list,
        "storage": storage_list
    }

if __name__ == "__main__":
    print(json.dumps(get_nexus()))
