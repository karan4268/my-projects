from pynvml import nvmlInit, nvmlDeviceGetHandleByIndex, nvmlDeviceGetUtilizationRates, nvmlDeviceGetMemoryInfo, nvmlDeviceGetTemperature, nvmlShutdown, NVMLError, NVML_TEMPERATURE_GPU

try:
    nvmlInit()
    handle = nvmlDeviceGetHandleByIndex(0)  # Get handle for the first GPU (index 0)
    utilization = nvmlDeviceGetUtilizationRates(handle)
    memory_info = nvmlDeviceGetMemoryInfo(handle)
    temperature = nvmlDeviceGetTemperature(handle, NVML_TEMPERATURE_GPU)

    print(f"GPU Utilization: {utilization.gpu}%")
    print(f"GPU Memory Used: {memory_info.used / (1024**3):.2f} GB")
    print(f"GPU Temperature: {temperature}°C")

except NVMLError as error:
    print(f"Error initializing NVML: {error}")
finally:
    try:
        nvmlShutdown()
    except NVMLError as error:
        print(f"Error shutting down NVML: {error}")