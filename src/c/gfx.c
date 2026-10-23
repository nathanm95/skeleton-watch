#include "gfx.h"

static inline uint16_t rd16(const uint8_t *p) { return (uint16_t)(p[0] | (p[1] << 8)); }
static inline uint32_t rd32(const uint8_t *p) {
  return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

// floor(a / 16) and ceil(a / 16) for negative a too.
static inline int fl16(int32_t a) { return (int)(a >> 4); }
static inline int ce16(int32_t a) { return (int)((a + 15) >> 4); }

static uint32_t isqrt(uint32_t v) {
  uint32_t r = 0, bit = 1u << 30;
  while (bit > v) bit >>= 2;
  while (bit) {
    if (v >= r + bit) {
      v -= r + bit;
      r = (r >> 1) + bit;
    } else {
      r >>= 1;
    }
    bit >>= 2;
  }
  return r;
}

void gfx_sheet_init(Sheet *s, const uint8_t *blob, int index) {
  const uint8_t *p = blob + rd32(blob + 4 + 4 * index);
  s->frames = p[0];
  s->w = rd16(p + 2);
  s->h = rd16(p + 4);
  s->left = (int16_t)rd16(p + 6);
  s->top = (int16_t)rd16(p + 8);
  s->table = p + 12;
  s->data = p + 12 + 4 * s->frames;
}

void gfx_sheet(Canvas *c, const Sheet *s, int f, const Col *pal) {
  if (f < 0 || f >= s->frames) f = 0;
  const uint8_t *p = s->data + rd32(s->table + 4 * f);
  for (int y = 0; y < s->h; y++) {
    int sy = s->top + y;
    int x = 0;
    while (x < s->w) {
      uint8_t b = *p++;
      int n = (b >> 4) + 1;
      int v = b & 15;
      if (v) gfx_span(c, sy, s->left + x, s->left + x + n - 1, pal[v]);
      x += n;
    }
  }
}

void gfx_clear(Canvas *c, Col col) {
  for (int y = 0; y < SCR_H; y++) {
    if (c->x1[y] >= c->x0[y]) memset(c->row[y] + c->x0[y], col, (size_t)(c->x1[y] - c->x0[y] + 1));
  }
}

void gfx_span(Canvas *c, int y, int xa, int xb, Col col) {
  if (y < 0 || y >= SCR_H) return;
  if (xa < c->x0[y]) xa = c->x0[y];
  if (xb > c->x1[y]) xb = c->x1[y];
  if (xa > xb) return;
  memset(c->row[y] + xa, col, (size_t)(xb - xa + 1));
}

void gfx_pixel(Canvas *c, int x, int y, Col col) {
  if (y < 0 || y >= SCR_H || x < c->x0[y] || x > c->x1[y]) return;
  c->row[y][x] = col;
}

void gfx_poly(Canvas *c, const int32_t *p, int n, Col col) {
  int32_t ymin = p[1], ymax = p[1];
  for (int i = 1; i < n; i++) {
    if (p[2 * i + 1] < ymin) ymin = p[2 * i + 1];
    if (p[2 * i + 1] > ymax) ymax = p[2 * i + 1];
  }
  // Rows whose centre (y * 16 + 8) lies inside [ymin, ymax].
  int ya = ce16(ymin - 8), yb = fl16(ymax - 8);
  if (ya < 0) ya = 0;
  if (yb > SCR_H - 1) yb = SCR_H - 1;
  for (int y = ya; y <= yb; y++) {
    int32_t yc = y * 16 + 8;
    int32_t lo = INT32_MAX, hi = INT32_MIN;
    for (int i = 0; i < n; i++) {
      int32_t x0 = p[2 * i], y0 = p[2 * i + 1];
      int32_t x1 = p[2 * ((i + 1) % n)], y1 = p[2 * ((i + 1) % n) + 1];
      if ((y0 <= yc && yc < y1) || (y1 <= yc && yc < y0)) {
        int32_t x = x0 + (yc - y0) * (x1 - x0) / (y1 - y0);
        if (x < lo) lo = x;
        if (x > hi) hi = x;
      }
    }
    if (lo > hi) continue;
    gfx_span(c, y, ce16(lo - 8), fl16(hi - 8), col);
  }
}

void gfx_disc(Canvas *c, int32_t cx, int32_t cy, int32_t r, Col col) {
  if (r <= 0) return;
  int ya = ce16(cy - r - 8), yb = fl16(cy + r - 8);
  for (int y = ya; y <= yb; y++) {
    int32_t dy = y * 16 + 8 - cy;
    int32_t d2 = r * r - dy * dy;
    if (d2 < 0) continue;
    int32_t dx = (int32_t)isqrt((uint32_t)d2);
    gfx_span(c, y, ce16(cx - dx - 8), fl16(cx + dx - 8), col);
  }
}

void gfx_line(Canvas *c, int32_t x0, int32_t y0, int32_t x1, int32_t y1, Col col) {
  int ax = fl16(x0), ay = fl16(y0), bx = fl16(x1), by = fl16(y1);
  int dx = abs(bx - ax), dy = -abs(by - ay);
  int sx = ax < bx ? 1 : -1, sy = ay < by ? 1 : -1;
  int err = dx + dy;
  for (;;) {
    gfx_pixel(c, ax, ay, col);
    if (ax == bx && ay == by) break;
    int e2 = 2 * err;
    if (e2 >= dy) {
      err += dy;
      ax += sx;
    }
    if (e2 <= dx) {
      err += dx;
      ay += sy;
    }
  }
}

void gfx_bar(Canvas *c, int32_t ax, int32_t ay, int32_t bx, int32_t by, int32_t wa, int32_t wb,
             int32_t off, Col col) {
  int32_t dx = bx - ax, dy = by - ay;
  int32_t len = (int32_t)isqrt((uint32_t)(dx * dx + dy * dy));
  if (len == 0) return;
  // Unit normal in 1/1024.
  int32_t nx = -dy * 1024 / len, ny = dx * 1024 / len;
  int32_t pa = off + wa / 2, ma = off - wa / 2, pb = off + wb / 2, mb = off - wb / 2;
  int32_t q[8] = {
    ax + nx * pa / 1024, ay + ny * pa / 1024,
    bx + nx * pb / 1024, by + ny * pb / 1024,
    bx + nx * mb / 1024, by + ny * mb / 1024,
    ax + nx * ma / 1024, ay + ny * ma / 1024,
  };
  gfx_poly(c, q, 4, col);
}
