#include "palette.h"
#include "settings.h"

// Ramps, darkest first. Pebble colours are 2 bits per channel, so metals are
// built from neighbouring hues rather than shades of one.
static const uint32_t WHEEL_GOLD[6] = { 0x550000, 0xAA5500, 0xFFAA00, 0xFFAA00, 0xFFFF55, 0xFFFFAA };
// Role 4 is the flat face, 5-6 the lit bevel, 1-3 the shadowed one.
static const uint32_t WHEEL_RHODIUM[6] = { 0x000055, 0x555555, 0xAAAAAA, 0xAAAAAA, 0xFFFFFF, 0xFFFFFF };
static const uint32_t WHEEL_GUNMETAL[6] = { 0x000000, 0x000055, 0x555555, 0x555555, 0xAAAAAA, 0xFFFFFF };
static const uint32_t WHEEL_ROSE[6] = { 0x550000, 0xAA5555, 0xFFAA55, 0xFFAA55, 0xFFAAAA, 0xFFFFFF };

static const uint32_t BRIDGE_RHODIUM[5] = { 0x000055, 0x555555, 0xAAAAAA, 0xFFFFFF, 0xFFFFFF };
static const uint32_t BRIDGE_GOLD[5] = { 0x550000, 0xAA5500, 0xFFAA00, 0xFFAA55, 0xFFFFAA };
static const uint32_t BRIDGE_BLACK[5] = { 0x000000, 0x000000, 0x555555, 0x555555, 0xAAAAAA };

static const uint32_t ACCENT_GOLD[4] = { 0xAA5500, 0xFFAA00, 0xFFFF55, 0xFFFFAA };
static const uint32_t ACCENT_STEEL[4] = { 0x555555, 0xAAAAAA, 0xFFFFFF, 0xFFFFFF };
static const uint32_t ACCENT_ROSE[4] = { 0xAA5555, 0xFFAA55, 0xFFAAAA, 0xFFFFFF };

typedef struct {
  const uint32_t *wheel, *bridge, *accent;
  uint32_t ring;
} Finish;

static const Finish FINISHES[FINISH_COUNT] = {
  [FINISH_CLASSIC] = { WHEEL_GOLD, BRIDGE_RHODIUM, ACCENT_GOLD, 0x000000 },
  [FINISH_GOLD] = { WHEEL_RHODIUM, BRIDGE_GOLD, ACCENT_GOLD, 0x000000 },
  [FINISH_STEEL] = { WHEEL_GUNMETAL, BRIDGE_RHODIUM, ACCENT_STEEL, 0x000055 },
  [FINISH_ROSE] = { WHEEL_ROSE, BRIDGE_RHODIUM, ACCENT_ROSE, 0x000000 },
  [FINISH_BLACK] = { WHEEL_GOLD, BRIDGE_BLACK, ACCENT_GOLD, 0x000000 },
};

void palette_make(Palette *p, int finish, int hands) {
  if (finish < 0 || finish >= FINISH_COUNT) finish = FINISH_CLASSIC;
  const Finish *f = &FINISHES[finish];
  memset(p, 0, sizeof(*p));
  for (int i = 0; i < 6; i++) p->wheel[1 + i] = COL(f->wheel[i]);
  for (int i = 0; i < 5; i++) p->overlay[1 + i] = COL(f->bridge[i]);
  for (int i = 0; i < 4; i++) p->overlay[6 + i] = COL(f->accent[i]);
  p->overlay[10] = COL(0xAA0000);
  p->overlay[11] = COL(0xFF0055);
  p->overlay[12] = COL(0x0000AA);
  p->overlay[13] = COL(0x0055FF);
  p->overlay[14] = COL(f->ring);
  p->overlay[15] = COL(0xFFFFFF);
  p->spring = COL(0x0055FF);
  p->steel[0] = COL(0x555555);
  p->steel[1] = COL(0xAAAAAA);
  p->steel[2] = COL(0xFFFFFF);
  switch (hands) {
    case HANDS_BLUED:
      p->hand[0] = COL(0x000000);
      p->hand[1] = COL(0x0000AA);
      p->hand[2] = COL(0x0055FF);
      break;
    case HANDS_GOLD:
      p->hand[0] = COL(0x000000);
      p->hand[1] = COL(0xFFAA00);
      p->hand[2] = COL(0xFFFF55);
      break;
    default:
      p->hand[0] = COL(0x000000);
      p->hand[1] = COL(0xAAAAAA);
      p->hand[2] = COL(0xFFFFFF);
      break;
  }
  p->cap = p->hand[2];
  p->reserve = p->overlay[8];
}
