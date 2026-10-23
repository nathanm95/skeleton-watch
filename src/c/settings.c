#include <pebble.h>
#include "settings.h"

#define KEY_SETTINGS 1
#define SETTINGS_VERSION 1

typedef struct {
  uint8_t version;
  Settings s;
} Saved;

void settings_default(Settings *s) {
  s->finish = FINISH_CLASSIC;
  s->hands = HANDS_WHITE;
  s->motion = MOTION_FLICK;
}

void settings_load(Settings *s) {
  settings_default(s);
  Saved saved = { 0, *s };
  int n = persist_exists(KEY_SETTINGS) ? persist_read_data(KEY_SETTINGS, &saved, sizeof(saved)) : 0;
  if (saved.version == SETTINGS_VERSION && n == (int)sizeof(saved)) *s = saved.s;
}

// Clay sends selects as strings and toggles as numbers; take either.
static int tuple_int(Tuple *t) {
  if (t->type == TUPLE_CSTRING) return atoi(t->value->cstring);
  if (t->length == 1) return t->type == TUPLE_INT ? t->value->int8 : t->value->uint8;
  if (t->length == 2) return t->type == TUPLE_INT ? t->value->int16 : t->value->uint16;
  return (int)t->value->int32;
}

bool settings_handle_inbox(DictionaryIterator *it, Settings *out) {
  Settings s = *out;
  bool any = false;
  Tuple *t;
  if ((t = dict_find(it, MESSAGE_KEY_Finish))) { any = true; s.finish = (uint8_t)(tuple_int(t) % FINISH_COUNT); }
  if ((t = dict_find(it, MESSAGE_KEY_Hands))) { any = true; s.hands = (uint8_t)(tuple_int(t) % HANDS_COUNT); }
  if ((t = dict_find(it, MESSAGE_KEY_Motion))) { any = true; s.motion = (uint8_t)(tuple_int(t) % MOTION_COUNT); }
  if (!any) return false;
  *out = s;
  Saved saved = { SETTINGS_VERSION, s };
  persist_write_data(KEY_SETTINGS, &saved, sizeof(saved));
  return true;
}
