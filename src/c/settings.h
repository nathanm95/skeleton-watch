#pragma once
#include <pebble.h>

enum { FINISH_CLASSIC, FINISH_GOLD, FINISH_STEEL, FINISH_ROSE, FINISH_BLACK, FINISH_COUNT };
enum { HANDS_WHITE, HANDS_BLUED, HANDS_GOLD, HANDS_COUNT };
enum { MOTION_FLICK, MOTION_ALWAYS, MOTION_STILL, MOTION_COUNT };

typedef struct {
  uint8_t finish;
  uint8_t hands;
  uint8_t motion;
} Settings;

void settings_default(Settings *s);
void settings_load(Settings *s);
// Applies any settings in a Clay message; true if one was there.
bool settings_handle_inbox(DictionaryIterator *it, Settings *s);
