// Skeleton Watch: Pebble glue. The movement (movement.c) draws straight into the
// framebuffer; this file feeds it the time, flicks, taps, battery and
// settings, and runs the frame timer only while the movement is going.
#include <pebble.h>
#include "movement.h"
#include "settings.h"

#define FRAME_MS 40

static Window *s_window;
static Layer *s_layer;
static AppTimer *s_timer;
static Canvas s_canvas;
static Settings s_settings;
static uint8_t *s_art;
static uint32_t s_last_ms;

// --------------------------------------------------------------- time --

#if defined(SKEL_SHOW_TIME) || defined(SKEL_FAST)
// Debug clock: starts at SKEL_SHOW_TIME and, with SKEL_FAST, a minute lasts
// SKEL_FAST seconds. The emulator ignores attempts to set its own clock.
#ifndef SKEL_SHOW_TIME
#define SKEL_SHOW_TIME 1008
#endif
static int s_fake = (SKEL_SHOW_TIME / 100) * 60 + SKEL_SHOW_TIME % 100;
#endif

static void clock_now(Clock *c) {
  time_t t = time(NULL);
  struct tm *tm = localtime(&t);
  c->hour = (uint8_t)tm->tm_hour;
  c->min = (uint8_t)tm->tm_min;
#if defined(SKEL_SHOW_TIME) || defined(SKEL_FAST)
  c->hour = (uint8_t)((s_fake / 60) % 24);
  c->min = (uint8_t)(s_fake % 60);
#endif
}

static uint32_t now_ms(void) {
  time_t s;
  uint16_t ms;
  time_ms(&s, &ms);
  return (uint32_t)s * 1000u + ms;
}

// -------------------------------------------------------------- frames --

static void frame(void *ctx) {
  s_timer = NULL;
  uint32_t now = now_ms();
  int dt = (int)(now - s_last_ms);
  // time_ms() is not atomic across a second boundary: ignore silly deltas.
  if (dt <= 0 || dt > 250) dt = FRAME_MS;
  s_last_ms = now;
  bool busy = scene_step(dt);
  if (s_layer) layer_mark_dirty(s_layer);
  if (busy) s_timer = app_timer_register(FRAME_MS, frame, NULL);
}

static void kick(void) {
  if (s_timer) return;
  s_last_ms = now_ms();
  s_timer = app_timer_register(FRAME_MS, frame, NULL);
}

static void update_proc(Layer *layer, GContext *ctx) {
  GBitmap *fb = graphics_capture_frame_buffer(ctx);
  if (!fb) return;
  for (int y = 0; y < SCR_H; y++) {
    GBitmapDataRowInfo r = gbitmap_get_data_row_info(fb, (uint16_t)y);
    s_canvas.row[y] = r.data;
    s_canvas.x0[y] = r.min_x;
    s_canvas.x1[y] = r.max_x;
  }
#if defined(SKEL_DEBUG)
  uint32_t t0 = now_ms();
#endif
  scene_draw(&s_canvas);
  graphics_release_frame_buffer(ctx, fb);
#if defined(SKEL_DEBUG)
  // Draw time of this frame and the worst so far, big enough to read in a shot.
  static uint32_t worst;
  uint32_t ms = now_ms() - t0;
  if (ms < 1000 && ms > worst) worst = ms;
  static char buf[32];
  snprintf(buf, sizeof(buf), "%lu/%lums %uB", (unsigned long)ms, (unsigned long)worst,
           (unsigned)heap_bytes_free());
  graphics_context_set_text_color(ctx, GColorWhite);
  graphics_draw_text(ctx, buf, fonts_get_system_font(FONT_KEY_GOTHIC_24_BOLD), GRect(0, SCR_H / 2 + 20, SCR_W, 30),
                     GTextOverflowModeFill, GTextAlignmentCenter, NULL);
#endif
}

// ------------------------------------------------------------- events --

static void minute(void) {
  Clock c;
  clock_now(&c);
  scene_minute(&c);
  if (s_layer) layer_mark_dirty(s_layer);
  kick();
}

#if defined(SKEL_FAST)
static void fake_minute(void *ctx) {
  s_fake++;
  minute();
  app_timer_register(SKEL_FAST * 1000, fake_minute, NULL);
}
#endif

static void tick_handler(struct tm *tm, TimeUnits changed) {
#if !defined(SKEL_SHOW_TIME) && !defined(SKEL_FAST)
  minute();
#endif
}

static void tap_handler(AccelAxisType axis, int32_t direction) {
  scene_poke();
  kick();
}

#if defined(PBL_TOUCH)
static void touch_handler(const TouchEvent *e, void *ctx) {
  if (e->type == TouchEvent_Touchdown) {
    scene_poke();
    kick();
  }
}
#endif

static void battery_handler(BatteryChargeState s) {
  scene_battery(s.charge_percent);
  if (s_layer && !s_timer) layer_mark_dirty(s_layer);
}

static void inbox(DictionaryIterator *it, void *ctx) {
  if (settings_handle_inbox(it, &s_settings)) {
    scene_settings(&s_settings);
    scene_poke();
    kick();
  }
  if (s_layer) layer_mark_dirty(s_layer);
}

// ------------------------------------------------------------- window --

static void window_load(Window *w) {
  Layer *root = window_get_root_layer(w);
  s_layer = layer_create(layer_get_bounds(root));
  layer_set_update_proc(s_layer, update_proc);
  layer_add_child(root, s_layer);
}

static void window_unload(Window *w) {
  layer_destroy(s_layer);
  s_layer = NULL;
}

static uint8_t *load_art(void) {
  ResHandle h = resource_get_handle(RESOURCE_ID_ART);
  size_t n = resource_size(h);
  uint8_t *b = malloc(n);
  if (b) resource_load_byte_range(h, 0, b, n);
  return b;
}

static void init(void) {
  s_art = load_art();
  if (!s_art) return;
  settings_load(&s_settings);
  Clock c;
  clock_now(&c);
  scene_init(&s_settings, &c, s_art);
  scene_battery(battery_state_service_peek().charge_percent);

  s_window = window_create();
  window_set_window_handlers(s_window, (WindowHandlers){ .load = window_load, .unload = window_unload });
  window_stack_push(s_window, false);

  tick_timer_service_subscribe(MINUTE_UNIT, tick_handler);
  accel_tap_service_subscribe(tap_handler);
#if defined(PBL_TOUCH)
  touch_service_subscribe(touch_handler, NULL);
#endif
  battery_state_service_subscribe(battery_handler);
  // The phone sends settings (Clay).
  app_message_register_inbox_received(inbox);
  app_message_open(128, 32);
#if defined(SKEL_FAST)
  app_timer_register(SKEL_FAST * 1000, fake_minute, NULL);
#endif
  kick();
}

static void deinit(void) {
  if (!s_art) return;
  if (s_timer) app_timer_cancel(s_timer);
  tick_timer_service_unsubscribe();
  accel_tap_service_unsubscribe();
#if defined(PBL_TOUCH)
  touch_service_unsubscribe();
#endif
  battery_state_service_unsubscribe();
  window_destroy(s_window);
  free(s_art);
}

int main(void) {
  init();
  app_event_loop();
  deinit();
}
