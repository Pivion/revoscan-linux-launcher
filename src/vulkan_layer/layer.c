#define VK_NO_PROTOTYPES
#include <vulkan/vulkan.h>
#include <vulkan/vk_layer.h>
#include "gpu_map_config.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if defined(_WIN32)
#define LAYER_EXPORT __declspec(dllexport)
#else
#define LAYER_EXPORT __attribute__((visibility("default")))
#endif

static PFN_vkGetInstanceProcAddr g_next_gipa;
static PFN_vkGetDeviceProcAddr g_next_gdpa;
static PFN_vkGetPhysicalDeviceProperties g_next_props;
static PFN_vkGetPhysicalDeviceProperties2 g_next_props2;
static PFN_vkGetPhysicalDeviceProperties2KHR g_next_props2_khr;
static VkInstance g_instance;
static GpuMap g_mapping;
static int g_mapping_loaded;

static void load_mapping_from_env(void) {
    if (g_mapping_loaded) return;
    g_mapping_loaded = 1;
    if (!parse_gpu_map(getenv("REVOSCAN_MAP_SOURCE_VENDOR"),
                       getenv("REVOSCAN_MAP_SOURCE_DEVICE"),
                       getenv("REVOSCAN_MAP_TARGET_VENDOR"),
                       getenv("REVOSCAN_MAP_TARGET_NAME"),
                       &g_mapping)) {
        memset(&g_mapping, 0, sizeof(g_mapping));
        return;
    }
    fprintf(stderr, "[revoscan-gpu-map] opt-in mapping enabled for %04x:%04x -> %s\n",
            g_mapping.source_vendor_id, g_mapping.source_device_id,
            g_mapping.target_name);
}

static void apply_mapping(VkPhysicalDeviceProperties *properties) {
    if (!properties || !g_mapping.enabled) return;
    uint32_t original_vendor = properties->vendorID;
    uint32_t original_device = properties->deviceID;
    VkPhysicalDeviceType original_type = properties->deviceType;
    char original_name[VK_MAX_PHYSICAL_DEVICE_NAME_SIZE];
    snprintf(original_name, sizeof(original_name), "%s", properties->deviceName);
    if (!apply_gpu_map(properties, &g_mapping)) return;
    fprintf(stderr,
            "[revoscan-gpu-map] Vulkan identity %04x:%04x '%s' type=%d -> %04x:%04x '%s' type=%d (deviceID preserved)\n",
            original_vendor, original_device, original_name, (int)original_type,
            properties->vendorID, properties->deviceID, properties->deviceName,
            (int)properties->deviceType);
}

static VKAPI_ATTR void VKAPI_CALL layer_get_properties(
    VkPhysicalDevice physicalDevice, VkPhysicalDeviceProperties *pProperties) {
    if (!g_next_props && g_next_gipa)
        g_next_props = (PFN_vkGetPhysicalDeviceProperties)
            g_next_gipa(g_instance, "vkGetPhysicalDeviceProperties");
    if (g_next_props) g_next_props(physicalDevice, pProperties);
    apply_mapping(pProperties);
}

static VKAPI_ATTR void VKAPI_CALL layer_get_properties2(
    VkPhysicalDevice physicalDevice, VkPhysicalDeviceProperties2 *pProperties) {
    if (g_next_props2) g_next_props2(physicalDevice, pProperties);
    else if (g_next_props2_khr) g_next_props2_khr(physicalDevice, pProperties);
    else if (g_next_gipa) {
        PFN_vkGetPhysicalDeviceProperties2 fn = (PFN_vkGetPhysicalDeviceProperties2)
            g_next_gipa(g_instance, "vkGetPhysicalDeviceProperties2");
        if (fn) fn(physicalDevice, pProperties);
    }
    apply_mapping(&pProperties->properties);
}

static VKAPI_ATTR void VKAPI_CALL layer_get_properties2_khr(
    VkPhysicalDevice physicalDevice, VkPhysicalDeviceProperties2KHR *pProperties) {
    layer_get_properties2(physicalDevice, (VkPhysicalDeviceProperties2 *)pProperties);
}

static VKAPI_ATTR PFN_vkVoidFunction VKAPI_CALL layer_get_physdev_proc_addr(
    VkInstance instance, const char *pName) {
    if (!pName) return NULL;
    if (strcmp(pName, "vkGetPhysicalDeviceProperties") == 0)
        return (PFN_vkVoidFunction)layer_get_properties;
    if (strcmp(pName, "vkGetPhysicalDeviceProperties2") == 0)
        return (PFN_vkVoidFunction)layer_get_properties2;
    if (strcmp(pName, "vkGetPhysicalDeviceProperties2KHR") == 0)
        return (PFN_vkVoidFunction)layer_get_properties2_khr;
    return g_next_gipa ? g_next_gipa(instance, pName) : NULL;
}

static VKAPI_ATTR VkResult VKAPI_CALL layer_create_device(
    VkPhysicalDevice physicalDevice,
    const VkDeviceCreateInfo *pCreateInfo,
    const VkAllocationCallbacks *pAllocator,
    VkDevice *pDevice) {
    const VkBaseInStructure *base = (const VkBaseInStructure *)pCreateInfo->pNext;
    VkLayerDeviceCreateInfo *chainInfo = NULL;
    while (base) {
        if (base->sType == VK_STRUCTURE_TYPE_LOADER_DEVICE_CREATE_INFO) {
            VkLayerDeviceCreateInfo *candidate = (VkLayerDeviceCreateInfo *)base;
            if (candidate->function == VK_LAYER_LINK_INFO) {
                chainInfo = candidate;
                break;
            }
        }
        base = base->pNext;
    }
    if (!chainInfo || !chainInfo->u.pLayerInfo) {
        fprintf(stderr, "[revoscan-gpu-map] device loader link info missing\\n");
        return VK_ERROR_INITIALIZATION_FAILED;
    }
    VkLayerDeviceLink *link = chainInfo->u.pLayerInfo;
    g_next_gdpa = link->pfnNextGetDeviceProcAddr;
    PFN_vkCreateDevice next_create = (PFN_vkCreateDevice)
        link->pfnNextGetInstanceProcAddr(g_instance, "vkCreateDevice");
    chainInfo->u.pLayerInfo = link->pNext;
    if (!next_create) return VK_ERROR_INITIALIZATION_FAILED;
    return next_create(physicalDevice, pCreateInfo, pAllocator, pDevice);
}

static VKAPI_ATTR PFN_vkVoidFunction VKAPI_CALL layer_get_device_proc_addr(
    VkDevice device, const char *pName) {
    if (!g_next_gdpa || !pName) return NULL;
    return g_next_gdpa(device, pName);
}

static VKAPI_ATTR VkResult VKAPI_CALL layer_create_instance(
    const VkInstanceCreateInfo *pCreateInfo,
    const VkAllocationCallbacks *pAllocator,
    VkInstance *pInstance) {
    const VkBaseInStructure *base = (const VkBaseInStructure *)pCreateInfo->pNext;
    VkLayerInstanceCreateInfo *chainInfo = NULL;
    while (base) {
        if (base->sType == VK_STRUCTURE_TYPE_LOADER_INSTANCE_CREATE_INFO) {
            VkLayerInstanceCreateInfo *candidate = (VkLayerInstanceCreateInfo *)base;
            if (candidate->function == VK_LAYER_LINK_INFO) {
                chainInfo = candidate;
                break;
            }
        }
        base = base->pNext;
    }
    if (!chainInfo || !chainInfo->u.pLayerInfo) {
        fprintf(stderr, "[revoscan-gpu-map] loader link info missing\n");
        return VK_ERROR_INITIALIZATION_FAILED;
    }
    VkLayerInstanceLink *link = chainInfo->u.pLayerInfo;
    g_next_gipa = link->pfnNextGetInstanceProcAddr;
    load_mapping_from_env();
    PFN_vkCreateInstance next_create = (PFN_vkCreateInstance)
        g_next_gipa(VK_NULL_HANDLE, "vkCreateInstance");
    chainInfo->u.pLayerInfo = link->pNext;
    if (!next_create) return VK_ERROR_INITIALIZATION_FAILED;
    VkResult result = next_create(pCreateInfo, pAllocator, pInstance);
    if (result == VK_SUCCESS) {
        g_instance = *pInstance;
        g_next_props = (PFN_vkGetPhysicalDeviceProperties)
            g_next_gipa(g_instance, "vkGetPhysicalDeviceProperties");
        g_next_props2 = (PFN_vkGetPhysicalDeviceProperties2)
            g_next_gipa(g_instance, "vkGetPhysicalDeviceProperties2");
        g_next_props2_khr = (PFN_vkGetPhysicalDeviceProperties2KHR)
            g_next_gipa(g_instance, "vkGetPhysicalDeviceProperties2KHR");
    }
    return result;
}

LAYER_EXPORT VKAPI_ATTR PFN_vkVoidFunction VKAPI_CALL vkGetInstanceProcAddr(
    VkInstance instance, const char *pName) {
    if (!pName) return NULL;
    if (strcmp(pName, "vkCreateInstance") == 0)
        return (PFN_vkVoidFunction)layer_create_instance;
    if (strcmp(pName, "vkCreateDevice") == 0)
        return (PFN_vkVoidFunction)layer_create_device;
    if (strcmp(pName, "vkGetDeviceProcAddr") == 0)
        return (PFN_vkVoidFunction)layer_get_device_proc_addr;
    if (strcmp(pName, "vkGetPhysicalDeviceProperties") == 0)
        return (PFN_vkVoidFunction)layer_get_properties;
    if (strcmp(pName, "vkGetPhysicalDeviceProperties2") == 0)
        return (PFN_vkVoidFunction)layer_get_properties2;
    if (strcmp(pName, "vkGetPhysicalDeviceProperties2KHR") == 0)
        return (PFN_vkVoidFunction)layer_get_properties2_khr;
    return g_next_gipa ? g_next_gipa(instance, pName) : NULL;
}

LAYER_EXPORT VKAPI_ATTR VkResult VKAPI_CALL vkNegotiateLoaderLayerInterfaceVersion(
    VkNegotiateLayerInterface *pVersionStruct) {
    if (!pVersionStruct || pVersionStruct->sType != LAYER_NEGOTIATE_INTERFACE_STRUCT)
        return VK_ERROR_INITIALIZATION_FAILED;
    if (pVersionStruct->loaderLayerInterfaceVersion > CURRENT_LOADER_LAYER_INTERFACE_VERSION)
        pVersionStruct->loaderLayerInterfaceVersion = CURRENT_LOADER_LAYER_INTERFACE_VERSION;
    pVersionStruct->pfnGetInstanceProcAddr = vkGetInstanceProcAddr;
    pVersionStruct->pfnGetDeviceProcAddr = layer_get_device_proc_addr;
    pVersionStruct->pfnGetPhysicalDeviceProcAddr = layer_get_physdev_proc_addr;
    return VK_SUCCESS;
}
