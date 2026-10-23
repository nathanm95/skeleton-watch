#pragma once
// The see-through movement: going train, escapement, balance, bridges and
// hands. Portable C: the watch (main.c) and the Mac harness (tools/host)
// both drive it.
#include "gfx.h"
#include "settings.h"

typedef struct {
  uint8_t hour, min;
} Clock;

// art: the blob from resources/data/art~<platform>.bin; it must outlive the scene.
void scene_init(const Settings *s, const Clock *c, const uint8_t *art);
void scene_settings(const Settings *s);
void scene_minute(const Clock *c);
// A flick or a tap: run the movement for a while.
void scene_poke(void);
void scene_battery(int percent);
// Advances the movement by dt ms. True while it is still running (the caller
// keeps its frame timer going only then).
bool scene_step(int dt);
void scene_draw(Canvas *c);
