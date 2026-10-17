#ifndef REVOSCAN_GPU_MAP_CONFIG_H
#define REVOSCAN_GPU_MAP_CONFIG_H

#include "gpu_property_map.h"

/* Parse the launcher's hexadecimal adapter/target environment fields. */
int parse_gpu_map(const char *source_vendor,
                  const char *source_device,
                  const char *target_vendor,
                  const char *target_name,
                  GpuMap *mapping);

#endif
