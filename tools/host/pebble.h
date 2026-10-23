// Just enough of pebble.h for the portable movement code to build on a Mac.
#pragma once
#include <math.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define TRIG_MAX_ANGLE 0x10000
#define TRIG_MAX_RATIO 0xffff

typedef struct DictionaryIterator DictionaryIterator;

static inline int32_t sin_lookup(int32_t a) {
  return (int32_t)lround(sin((double)a * 2.0 * M_PI / TRIG_MAX_ANGLE) * TRIG_MAX_RATIO);
}
static inline int32_t cos_lookup(int32_t a) {
  return (int32_t)lround(cos((double)a * 2.0 * M_PI / TRIG_MAX_ANGLE) * TRIG_MAX_RATIO);
}
