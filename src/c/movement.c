#include "movement.h"
#include "layout.h"
#include "palette.h"

// The balance swings there and back once per PERIOD_MS and the escapement
// "beats" each time it passes the centre. Every beat lets the escape wheel on
// half a tooth and the train on TRAIN_STEP, eased over STEP_MS, so the whole
// movement ticks forward together.
#define PERIOD_MS 600
#define BEAT_MS (PERIOD_MS / 2)
#define STEP_MS 90
#define AMP_DEG 80        // balance amplitude
#define FORK_DEG 9        // pallet fork throw either side
#define TRAIN_STEP 64     // going train per beat, 1/256 tooth
#define ESCAPE_STEP 128   // escape wheel per beat: half a tooth

#define RUN_START_MS 6000   // after the face opens
#define RUN_POKE_MS 12000   // after a flick or a tap
#define RUN_MINUTE_MS 1800  // a few beats as each minute arrives

#define DEG(d) ((int32_t)(d) * TRIG_MAX_ANGLE / 360)

static Settings s_set;
static Palette s_pal;
static Clock s_clock;
static Sheet s_gear[LAY_GEARS];
static Sheet s_rim, s_overlay;
static uint32_t s_t;   // movement time, ms; only runs while the movement does
static int32_t s_run;  // ms left to run
static int s_battery = 100;

// ---------------------------------------------------------------- timing --

// 0..256 smoothstep of the current beat's step.
static int32_t step_ease(void) {
  int32_t x = (int32_t)(s_t % BEAT_MS) * 256 / STEP_MS;
  if (x >= 256) return 256;
  return x * x * (768 - 2 * x) / 65536;
}

// Gear angle, clockwise, in 1/256 tooth, 0 .. teeth * 256 - 1.
static int32_t gear_pos(const GearSpec *g) {
  int32_t m = g->teeth * 256;
  int32_t step = g->drive ? ESCAPE_STEP : TRAIN_STEP;
  uint32_t beats = s_t / BEAT_MS;
  int32_t p = (int32_t)(beats % (uint32_t)m) * step % m + step * step_ease() / 256;
  p %= m;
  if (g->dir < 0) p = m - p;
  return (p + g->phase) % m;
}

static int32_t balance_angle(void) {
  int32_t ph = (int32_t)(s_t % PERIOD_MS) * TRIG_MAX_ANGLE / PERIOD_MS;
  return DEG(AMP_DEG) * sin_lookup(ph) / TRIG_MAX_RATIO;
}

// The pallet fork snaps from one side to the other on each beat.
static int32_t fork_angle(void) {
  int32_t side = ((s_t / BEAT_MS) & 1) ? 1 : -1;
  return DEG(FORK_DEG) * side * (2 * step_ease() - 256) / 256;
}

// --------------------------------------------------------------- drawing --

static inline int32_t rx(int32_t r, int32_t ang) { return r * cos_lookup(ang) / TRIG_MAX_RATIO; }
static inline int32_t ry(int32_t r, int32_t ang) { return r * sin_lookup(ang) / TRIG_MAX_RATIO; }

// A raised bar lit from the upper left: shadow edge, lit edge, face.
static void spoke(Canvas *c, int32_t cx, int32_t cy, int32_t ang, int32_t r0, int32_t r1, int32_t w0,
                  int32_t w1, const Col *ramp) {
  int32_t ax = cx + rx(r0, ang), ay = cy + ry(r0, ang);
  int32_t bx = cx + rx(r1, ang), by = cy + ry(r1, ang);
  // gfx_bar's normal is (-sin, cos); the light comes from (-1, -1.25).
  int32_t lit = (sin_lookup(ang) - cos_lookup(ang) * 5 / 4) > 0 ? 1 : -1;
  gfx_bar(c, ax, ay, bx, by, w0, w1, 0, ramp[2]);
  gfx_bar(c, ax, ay, bx, by, w0 - 12, w1 - 12, lit * 6, ramp[5]);
  if (w1 > 30) gfx_bar(c, ax, ay, bx, by, w0 - 26, w1 - 26, 0, ramp[4]);
}

static void draw_gear(Canvas *c, int i) {
  const GearSpec *g = &LAY_GEAR[i];
  int32_t a = gear_pos(g);
  if (g->spokes) {
    int32_t ang = a * 256 / g->teeth;  // TRIG units: a full turn is teeth * 256
    for (int k = 0; k < g->spokes; k++) {
      spoke(c, g->cx16, g->cy16, ang + k * TRIG_MAX_ANGLE / g->spokes, g->r_hub16, g->r_in16, g->w_hub16,
            g->w_rim16, s_pal.wheel);
    }
  }
  int f = (int)((((a & 255) * g->frames) + 128) >> 8) % g->frames;
  gfx_sheet(c, &s_gear[i], f, s_pal.wheel);
}

static void draw_balance(Canvas *c) {
  int32_t th = balance_angle();
  for (int k = 0; k < LAY_BAL_ARMS; k++) {
    spoke(c, LAY_BAL_CX16, LAY_BAL_CY16, th + k * TRIG_MAX_ANGLE / LAY_BAL_ARMS, 0, LAY_BAL_RIN16,
          LAY_BAL_ARM_W16, LAY_BAL_ARM_W16, s_pal.wheel);
  }
  gfx_sheet(c, &s_rim, 0, s_pal.wheel);
  // Timing screws round the rim.
  for (int k = 0; k < LAY_BAL_SCREWS; k++) {
    int32_t ang = th + k * TRIG_MAX_ANGLE / LAY_BAL_SCREWS + TRIG_MAX_ANGLE / (2 * LAY_BAL_SCREWS);
    int32_t x = LAY_BAL_CX16 + rx(LAY_BAL_SCREW_AT16, ang), y = LAY_BAL_CY16 + ry(LAY_BAL_SCREW_AT16, ang);
    gfx_disc(c, x, y, LAY_BAL_SCREW_R16, s_pal.wheel[1]);
    gfx_disc(c, x - 4, y - 5, LAY_BAL_SCREW_R16 - 6, s_pal.wheel[5]);
  }
  // Hairspring: an Archimedean spiral pinned at the stud (outer end) and
  // turning with the balance at the collet (inner end), so it breathes.
  int segs = LAY_SPRING_TURNS * 18;
  int32_t stud = DEG(LAY_SPRING_STUD_DEG);
  int32_t px = 0, py = 0;
  for (int j = 0; j <= segs; j++) {
    int32_t free = (segs - j) * 256 / segs;  // 256 at the collet, 0 at the stud
    int32_t r = LAY_SPRING_R1_16 - (LAY_SPRING_R1_16 - LAY_SPRING_R0_16) * free / 256;
    int32_t ang = stud - LAY_SPRING_TURNS * free * (TRIG_MAX_ANGLE / 256) + th * free / 256;
    int32_t x = LAY_BAL_CX16 + rx(r, ang), y = LAY_BAL_CY16 + ry(r, ang);
    if (j) gfx_line(c, px, py, x, y, s_pal.spring);
    px = x;
    py = y;
  }
}

static void draw_pallet(Canvas *c) {
  int32_t f = fork_angle();
  int32_t cs = cos_lookup(f), sn = sin_lookup(f);
  int32_t lever = DEG(LAY_PALLET_LEVER_DEG) + f;
  int32_t lx = LAY_PALLET_X16 + rx(LAY_PALLET_LEVER16, lever), ly = LAY_PALLET_Y16 + ry(LAY_PALLET_LEVER16, lever);
  gfx_bar(c, LAY_PALLET_X16, LAY_PALLET_Y16, lx, ly, LAY_PALLET_W16, LAY_PALLET_W16 * 2 / 3, 0, s_pal.steel[0]);
  gfx_bar(c, LAY_PALLET_X16, LAY_PALLET_Y16, lx, ly, LAY_PALLET_W16 - 10, LAY_PALLET_W16 * 2 / 3 - 10, 0,
          s_pal.steel[1]);
  for (int k = 0; k < 2; k++) {
    int32_t sx = LAY_STONE16[k][0], sy = LAY_STONE16[k][1];
    int32_t x = LAY_PALLET_X16 + (sx * cs - sy * sn) / TRIG_MAX_RATIO;
    int32_t y = LAY_PALLET_Y16 + (sx * sn + sy * cs) / TRIG_MAX_RATIO;
    gfx_bar(c, LAY_PALLET_X16, LAY_PALLET_Y16, x, y, LAY_PALLET_W16, LAY_PALLET_W16 * 3 / 4, 0, s_pal.steel[0]);
    gfx_bar(c, LAY_PALLET_X16, LAY_PALLET_Y16, x, y, LAY_PALLET_W16 - 10, LAY_PALLET_W16 * 3 / 4 - 10, 0,
            s_pal.steel[1]);
    gfx_disc(c, x, y, LAY_STONE_R16, s_pal.overlay[10]);
    gfx_disc(c, x - 3, y - 3, LAY_STONE_R16 - 6, s_pal.overlay[11]);
  }
}

// A faceted dauphine hand; ang is a clock angle (0 = 12, clockwise).
static void hand(Canvas *c, int32_t ang, int32_t len, int32_t w, int32_t tail) {
  int32_t cx = SCR_W * 8, cy = SCR_H * 8;
  int32_t dx = sin_lookup(ang), dy = -cos_lookup(ang);  // along the hand
  int32_t nx = cos_lookup(ang), ny = sin_lookup(ang);   // to its right
  int32_t base = LAY_CAP_R16 * 3 / 2;
#define PT(along, side) cx + ((along) * dx + (side) * nx) / TRIG_MAX_RATIO, cy + ((along) * dy + (side) * ny) / TRIG_MAX_RATIO
  int32_t edge[8] = { PT(len + 22, 0), PT(base, w / 2 + 16), PT(-tail - 16, 0), PT(base, -w / 2 - 16) };
  int32_t left[6] = { PT(-tail, 0), PT(base, -w / 2), PT(len, 0) };
  int32_t right[6] = { PT(-tail, 0), PT(len, 0), PT(base, w / 2) };
#undef PT
  gfx_poly(c, edge, 4, s_pal.hand[0]);
  // The left facet faces -n; it is lit when -n points towards the light (-1, -1.25).
  bool left_lit = (cos_lookup(ang) + sin_lookup(ang) * 5 / 4) > 0;
  gfx_poly(c, left, 3, s_pal.hand[left_lit ? 2 : 1]);
  gfx_poly(c, right, 3, s_pal.hand[left_lit ? 1 : 2]);
}

// The battery, as the power-reserve hand at 8 o'clock.
static void draw_reserve(Canvas *c) {
  int pct = s_battery < 0 ? 0 : s_battery > 100 ? 100 : s_battery;
  int32_t ang = DEG(LAY_RESERVE_START_DEG) + DEG(LAY_RESERVE_SWEEP_DEG) * pct / 100;
  int32_t x = LAY_RESERVE_X16 + rx(LAY_RESERVE_LEN16, ang), y = LAY_RESERVE_Y16 + ry(LAY_RESERVE_LEN16, ang);
  gfx_bar(c, LAY_RESERVE_X16, LAY_RESERVE_Y16, x, y, LAY_RESERVE_W16, LAY_RESERVE_W16 / 2, 0, s_pal.reserve);
  gfx_disc(c, LAY_RESERVE_X16, LAY_RESERVE_Y16, LAY_RESERVE_PIN16, s_pal.overlay[12]);
  gfx_disc(c, LAY_RESERVE_X16 - 4, LAY_RESERVE_Y16 - 4, LAY_RESERVE_PIN16 - 8, s_pal.overlay[13]);
}

static void draw_hands(Canvas *c) {
  int32_t m = s_clock.min * TRIG_MAX_ANGLE / 60;
  int32_t h = ((s_clock.hour % 12) * 60 + s_clock.min) * TRIG_MAX_ANGLE / 720;
  hand(c, h, LAY_HAND_HOUR16, LAY_HAND_HOUR_W16, LAY_HAND_TAIL16);
  hand(c, m, LAY_HAND_MIN16, LAY_HAND_MIN_W16, LAY_HAND_TAIL16);
  int32_t cx = SCR_W * 8, cy = SCR_H * 8;
  gfx_disc(c, cx, cy, LAY_CAP_R16 + 16, s_pal.hand[0]);
  gfx_disc(c, cx, cy, LAY_CAP_R16, s_pal.hand[1]);
  gfx_disc(c, cx - 8, cy - 8, LAY_CAP_R16 - 16, s_pal.cap);
  gfx_disc(c, cx, cy, LAY_CAP_R16 / 3, s_pal.hand[0]);
}

void scene_draw(Canvas *c) {
  gfx_clear(c, COL(0x000000));
  for (int i = 0; i < LAY_GEARS; i++) draw_gear(c, i);
  draw_pallet(c);  // under the balance, as in the real thing
  draw_balance(c);
  gfx_sheet(c, &s_overlay, 0, s_pal.overlay);
  draw_reserve(c);
#ifndef SKEL_NO_HANDS
  draw_hands(c);
#endif
}

// ----------------------------------------------------------------- state --

static void run_for(int32_t ms) {
  if (s_set.motion == MOTION_STILL) return;
  if (s_run < ms) s_run = ms;
}

void scene_init(const Settings *s, const Clock *c, const uint8_t *art) {
  for (int i = 0; i < LAY_GEARS; i++) gfx_sheet_init(&s_gear[i], art, LAY_GEAR[i].sheet);
  gfx_sheet_init(&s_rim, art, LAY_BAL_SHEET);
  gfx_sheet_init(&s_overlay, art, LAY_OVERLAY_SHEET);
  s_clock = *c;
  s_t = PERIOD_MS / 4;  // the balance at the end of a swing
  s_run = 0;
  scene_settings(s);
  run_for(RUN_START_MS);
}

void scene_settings(const Settings *s) {
  s_set = *s;
  palette_make(&s_pal, s_set.finish, s_set.hands);
  if (s_set.motion == MOTION_STILL) s_run = 0;
}

void scene_minute(const Clock *c) {
  s_clock = *c;
  if (s_set.motion == MOTION_STILL) {
    s_t += BEAT_MS;  // still moves on a tick each minute
  } else {
    run_for(RUN_MINUTE_MS);
  }
}

void scene_poke(void) { run_for(RUN_POKE_MS); }

void scene_battery(int percent) { s_battery = percent; }

bool scene_step(int dt) {
  if (s_set.motion == MOTION_ALWAYS) {
    s_t += (uint32_t)dt;
    return true;
  }
  if (s_run <= 0) return false;
  s_t += (uint32_t)dt;
  s_run -= dt;
  return s_run > 0;
}
