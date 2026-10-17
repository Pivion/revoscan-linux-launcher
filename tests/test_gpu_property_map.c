#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <vulkan/vulkan.h>

#include "gpu_property_map.h"
#include "gpu_map_config.h"

static VkPhysicalDeviceProperties sample(uint32_t vendor, uint32_t device,
                                          VkPhysicalDeviceType type,
                                          const char *name) {
    VkPhysicalDeviceProperties props = {0};
    props.vendorID = vendor;
    props.deviceID = device;
    props.deviceType = type;
    snprintf(props.deviceName, sizeof(props.deviceName), "%s", name);
    return props;
}

int main(void) {
    GpuMap mapping = {
        .enabled = 1,
        .source_vendor_id = 0x8086,
        .source_device_id = 0x7d55,
        .target_vendor_id = 0x1002,
        .target_name = "AMD Radeon RX 7700 XT",
    };
    VkPhysicalDeviceProperties intel = sample(
        0x8086, 0x7d55, VK_PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU, "Intel Arc Graphics");
    assert(apply_gpu_map(&intel, &mapping) == 1);
    assert(intel.vendorID == 0x1002);
    assert(intel.deviceID == 0x7d55); /* Keep the real PCI device ID. */
    assert(intel.deviceType == VK_PHYSICAL_DEVICE_TYPE_DISCRETE_GPU);
    assert(strcmp(intel.deviceName, "AMD Radeon RX 7700 XT") == 0);

    VkPhysicalDeviceProperties other = sample(
        0x1002, 0x1900, VK_PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU, "Radeon 780M");
    assert(apply_gpu_map(&other, &mapping) == 0);
    assert(other.vendorID == 0x1002 && other.deviceID == 0x1900);
    assert(other.deviceType == VK_PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU);
    assert(strcmp(other.deviceName, "Radeon 780M") == 0);

    mapping.enabled = 0;
    intel = sample(0x8086, 0x7d55, VK_PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU, "Intel Arc Graphics");
    assert(apply_gpu_map(&intel, &mapping) == 0);
    assert(intel.vendorID == 0x8086 && intel.deviceID == 0x7d55);
    assert(intel.deviceType == VK_PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU);
    assert(strcmp(intel.deviceName, "Intel Arc Graphics") == 0);

    GpuMap parsed = {0};
    assert(parse_gpu_map("8086", "7d55", "1002", "AMD Radeon RX 7700 XT", &parsed) == 1);
    assert(parsed.enabled == 1 && parsed.source_vendor_id == 0x8086);
    assert(parsed.source_device_id == 0x7d55 && parsed.target_vendor_id == 0x1002);
    assert(strcmp(parsed.target_name, "AMD Radeon RX 7700 XT") == 0);
    assert(parse_gpu_map("10de", "2684", "1002", "AMD Radeon RX 7700 XT", &parsed) == 0);
    assert(parse_gpu_map("8086", "oops", "1002", "AMD Radeon RX 7700 XT", &parsed) == 0);
    assert(parse_gpu_map("8086", "7d55", "10de", "NVIDIA", &parsed) == 0);
    assert(parse_gpu_map("8086", "7d55", "1002", "", &parsed) == 0);
    return 0;
}
