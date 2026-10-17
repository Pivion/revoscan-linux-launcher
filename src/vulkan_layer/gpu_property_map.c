#include "gpu_property_map.h"

#include <stdio.h>
#include <string.h>

int apply_gpu_map(VkPhysicalDeviceProperties *properties, const GpuMap *mapping) {
    if (!properties || !mapping || !mapping->enabled) return 0;
    if (mapping->target_vendor_id != REVOSCAN_GPU_TARGET_VENDOR_AMD) return 0;
    if (mapping->source_vendor_id != 0x1002u && mapping->source_vendor_id != 0x8086u) return 0;
    if (properties->vendorID != mapping->source_vendor_id ||
        properties->deviceID != mapping->source_device_id) return 0;
    if (mapping->target_name[0] == '\0' ||
        !memchr(mapping->target_name, '\0', sizeof(mapping->target_name))) return 0;

    properties->vendorID = mapping->target_vendor_id;
    properties->deviceType = VK_PHYSICAL_DEVICE_TYPE_DISCRETE_GPU;
    snprintf(properties->deviceName, sizeof(properties->deviceName), "%s", mapping->target_name);
    return 1;
}
