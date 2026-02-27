import cpuinfo
import platform
import psutil
import pyopencl as cl
import GPUtil
import pandas as pd

# =====================================================================
#  SAFE CPU DETECT
# =====================================================================
fv = cpuinfo.get_cpu_info()

def safe_detect(primary_key, fallback_func=None):
    try:
        primary_result = fv.get(primary_key)

        if primary_result is not None:
            return primary_result

        if fallback_func:
            return fallback_func()

        return None

    except:
        return None


# =====================================================================
#  CPU INFO
# =====================================================================
def get_cpu_info():
    return {
        "type": "CPU",
        "system": safe_detect("mhcv", platform.system),
        "Release": safe_detect("", platform.release),
        "Version": safe_detect("", platform.version),
        "name": safe_detect("brand_raw", platform.processor),
        "arch": safe_detect("arch", platform.machine),
        "bits": safe_detect("bits", platform.architecture),
        "Threads": safe_detect("count"),
        "vendor": safe_detect("vendor_id_raw"),
        "hz": safe_detect("hz_advertised_friendly")
    }


# =====================================================================
#  GPU INFO
# =====================================================================
def get_gpu_info():
    result = []

    # NVIDIA GPUs
    try:
        gpus = GPUtil.getGPUs()
    except:
        gpus = []

    if gpus:
        for rtx in gpus:
            result.append({
                "type": "GPU_NVIDIA",
                "ID": rtx.id,
                "Name": rtx.name,
                "Driver": rtx.driver,
                "Memory_Total_GB": round(rtx.memoryTotal / 1024, 2),
                "Memory_Free_GB": round(rtx.memoryFree / 1024, 2),
                "Memory_Used_GB": round(rtx.memoryUsed / 1024, 2),
                "Load_Percentage": round(rtx.load * 100, 2)
            })
    else:
        result.append({"type": "GPU_NVIDIA", "status": "No NVIDIA GPU found"})

    # OpenCL GPUs (AMD / Intel)
    try:
        platforms = cl.get_platforms()
    except:
        platforms = []

    if platforms:
        for platform in platforms:
            for d in platform.get_devices():

                if "NVIDIA" in d.name:  
                    continue  # skip duplicate NVIDIA data

                result.append({
                    "type": "GPU_OpenCL",
                    "Device_Name": d.name,
                    "Vendor": d.vendor,
                    "Global_Memory_GB": round(d.global_mem_size / (1024**3), 2),
                    "Max_Clock_Speed_MHz": d.max_clock_frequency,
                    "Driver_Version": d.driver_version
                })
    else:
        result.append({"type": "GPU_OpenCL", "status": "No OpenCL GPU found"})

    return result


# =====================================================================
#  RAM + SWAP
# =====================================================================
def get_memory_info():
    vm = psutil.virtual_memory()
    swap = psutil.swap_memory()

    return [
        {
            "type": "RAM",
            "total_gb": round(vm.total / (1024**3), 2),
            "used_gb": round(vm.used / (1024**3), 2),
            "available_gb": round(vm.available / (1024**3), 2),
            "free_gb": round(vm.free / (1024**3), 2),
            "usage_percent": vm.percent
        },
        {
            "type": "SWAP",
            "total_gb": round(swap.total / (1024**3), 2),
            "used_gb": round(swap.used / (1024**3), 2),
            "free_gb": round(swap.free / (1024**3), 2),
            "usage_percent": swap.percent
        }
    ]


# =====================================================================
#  DISK INFO
# =====================================================================
def get_disk_info():
    disk_list = []
    partitions = psutil.disk_partitions()

    for i, p in enumerate(partitions):
        try:
            usage = psutil.disk_usage(p.mountpoint)
        except PermissionError:
            continue

        disk_list.append({
            "type": "DISK",
            "disk_number": i,
            "device": p.device,
            "mountpoint": p.mountpoint,
            "filesystem": p.fstype,
            "options": p.opts,
            "total_gb": round(usage.total / (1024**3), 2),
            "used_gb": round(usage.used / (1024**3), 2),
            "free_gb": round(usage.free / (1024**3), 2),
            "usage_percent": usage.percent
        })

    return disk_list


# =====================================================================
#  FINAL: ALL IN ONE LIST
# =====================================================================
def get_system_info_list():
    full_list = []

    # Add CPU
    full_list.append(get_cpu_info())

    # Add GPU items
    full_list.extend(get_gpu_info())

    # Add RAM + SWAP
    full_list.extend(get_memory_info())

    # Add Disks
    full_list.extend(get_disk_info())

    return full_list


# RUN



def save_table_to_file(data, filename="system_info.txt"):
    with open(filename, "a", encoding="utf-8") as f:   # <-- APPEND mode
        f.write("\n====== NEW RUN ======\n")
        for item in data:
            f.write("___________________________________________________________\n")
            for key, value in item.items():
                f.write(f"{key:<20}: {value}\n")

print("Saved to system_info.txt")