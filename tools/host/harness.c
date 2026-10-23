// Mac harness: runs the real movement code and dumps frames as PPM.
//
//   harness <out_dir> <HH:MM> [events...]
//
// Events, run in order (FRAME_MS of movement time per dumped frame):
//   w<ms>   run the movement for ms, dumping every frame
//   s       dump one still               p    a wrist flick
//   m       the next minute arrives      t<HH:MM>  set the time
//   f<k>    finish k   h<k> hands k   M<k> motion k
//   b<pct>  battery
#include <pebble.h>
#include "movement.h"

#ifndef PLAT
#define PLAT "gabbro"
#endif
#define FRAME_MS 40

static uint8_t fb[SCR_H][SCR_W];
static Canvas canvas;
static const char *out_dir;
static int frame_no;

static uint8_t *load_art(void) {
  char path[256];
  snprintf(path, sizeof(path), "resources/data/art~%s.bin", PLAT);
  FILE *f = fopen(path, "rb");
  if (!f) {
    fprintf(stderr, "missing %s (run tools/make_art.py)\n", path);
    exit(1);
  }
  fseek(f, 0, SEEK_END);
  long n = ftell(f);
  fseek(f, 0, SEEK_SET);
  uint8_t *b = malloc((size_t)n);
  fread(b, 1, (size_t)n, f);
  fclose(f);
  return b;
}

static void dump(void) {
  memset(fb, 0xC0, sizeof(fb));
  scene_draw(&canvas);
  char path[512];
  snprintf(path, sizeof(path), "%s/f%04d.ppm", out_dir, frame_no++);
  FILE *f = fopen(path, "wb");
  fprintf(f, "P6 %d %d 255\n", SCR_W, SCR_H);
  for (int y = 0; y < SCR_H; y++) {
    for (int x = 0; x < SCR_W; x++) {
      uint8_t c = fb[y][x];
      uint8_t rgb[3] = { (uint8_t)(((c >> 4) & 3) * 85), (uint8_t)(((c >> 2) & 3) * 85), (uint8_t)((c & 3) * 85) };
      if (x < canvas.x0[y] || x > canvas.x1[y]) rgb[0] = rgb[1] = rgb[2] = 0;
      fwrite(rgb, 1, 3, f);
    }
  }
  fclose(f);
}

int main(int argc, char **argv) {
  if (argc < 3) {
    fprintf(stderr, "usage: harness out HH:MM [events]\n");
    return 2;
  }
  out_dir = argv[1];
  for (int y = 0; y < SCR_H; y++) {
    canvas.row[y] = fb[y];
    // Same inset the round framebuffers report per row.
    double r = SCR_W / 2.0, dy = y + 0.5 - r;
    int half = (int)floor(sqrt(r * r - dy * dy) + 0.5);
    canvas.x0[y] = (int16_t)(SCR_W / 2 - half);
    canvas.x1[y] = (int16_t)(SCR_W / 2 + half - 1);
  }
  Clock t = { 10, 8 };
  sscanf(argv[2], "%hhu:%hhu", &t.hour, &t.min);
  Settings s = { FINISH_CLASSIC, HANDS_WHITE, MOTION_FLICK };
  scene_init(&s, &t, load_art());
  scene_battery(70);
  for (int i = 3; i < argc; i++) {
    const char *e = argv[i];
    if (e[0] == 'w') {
      int ms = atoi(e + 1);
      for (int k = 0; k < ms; k += FRAME_MS) {
        scene_step(FRAME_MS);
        dump();
      }
    } else if (e[0] == 's') {
      dump();
    } else if (e[0] == 'p') {
      scene_poke();
    } else if (e[0] == 'm') {
      t.min++;
      if (t.min == 60) {
        t.min = 0;
        t.hour = (uint8_t)((t.hour + 1) % 24);
      }
      scene_minute(&t);
    } else if (e[0] == 't') {
      sscanf(e + 1, "%hhu:%hhu", &t.hour, &t.min);
      scene_minute(&t);
    } else if (e[0] == 'f') {
      s.finish = (uint8_t)atoi(e + 1);
      scene_settings(&s);
    } else if (e[0] == 'h') {
      s.hands = (uint8_t)atoi(e + 1);
      scene_settings(&s);
    } else if (e[0] == 'M') {
      s.motion = (uint8_t)atoi(e + 1);
      scene_settings(&s);
    } else if (e[0] == 'b') {
      scene_battery(atoi(e + 1));
    }
  }
  printf("%d frames\n", frame_no);
  return 0;
}
