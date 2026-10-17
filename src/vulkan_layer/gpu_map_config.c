#include "gpu_map_config.h"

#include <ctype.h>
#include <errno.h>
#include <stdlib.h>
#include <string.h>

static int parse_hex_id(const char *text, uint32_t *result) {
    if (!text || !*text || !result) return 0;
    if (text[0] == '0' && (text[1] == 'x' || text[1] == 'X')) text += 2;
    size_t length = strlen(text);
    if (length == 0 || length > 4) return 0;
    for (size_t i = 0; i < length; ++i) {
        if (!isxdigit((unsigned char)text[i])) return 0;
    }
    errno = 0;
    char *end = NULL;
    unsigned long value = strtoul(text, &end, 16);
    if (errno || !end || *end != '\0' || value > 0xfffful) return 0;
    *result = (uint32_t)value;
    return 1;
}

int parse_gpu_map(const char *source_vendor,
                  const char *source_device,
                  const char *target_vendor,
                  const char *target_name,
                  GpuMap *mapping) {
    if (!mapping) return 0;
    memset(mapping, 0, sizeof(*mapping));

    uint32_t source_vendor_id = 0;
    uint32_t source_device_id = 0;
    uint32_t target_vendor_id = 0;
    if (!parse_hex_id(source_vendor, &source_vendor_id) ||
        !parse_hex_id(source_device, &source_device_id) ||
        !parse_hex_id(target_vendor, &target_vendor_id)) return 0;
    if (source_vendor_id != 0x1002u && source_vendor_id != 0x8086u) return 0;
    if (target_vendor_id != REVOSCAN_GPU_TARGET_VENDOR_AMD) return 0;
    if (!target_name || !target_name[0]) return 0;

    size_t name_length = strlen(target_name);
    if (name_length >= sizeof(mapping->target_name)) return 0;
    for (size_t i = 0; i < name_length; ++i) {
        unsigned char ch = (unsigned char)target_name[i];
        if (ch < 0x20u || ch == 0x7fu) return 0;
    }

    mapping->enabled = 1;
    mapping->source_vendor_id = source_vendor_id;
    mapping->source_device_id = source_device_id;
    mapping->target_vendor_id = target_vendor_id;
    memcpy(mapping->target_name, target_name, name_length + 1);
    return 1;
}
