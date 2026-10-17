#ifndef REVOSCAN_GPU_PROPERTY_MAP_H
#define REVOSCAN_GPU_PROPERTY_MAP_H

#include <stdint.h>
#include <vulkan/vulkan.h>

#define REVOSCAN_GPU_TARGET_VENDOR_AMD 0x1002u

typedef struct GpuMap {
    int enabled;
    uint32_t source_vendor_id;
    uint32_t source_device_id;
    uint32_t target_vendor_id;
    char target_name[VK_MAX_PHYSICAL_DEVICE_NAME_SIZE];
} GpuMap;

/* Returns 1 only when an explicitly configured source adapter was mapped. */
int apply_gpu_map(VkPhysicalDeviceProperties *properties, const GpuMap *mapping);

#endif
