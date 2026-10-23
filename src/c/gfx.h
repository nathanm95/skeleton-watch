#pragma once
// Tiny software rasteriser that writes straight into the captured framebuffer
// (or a Mac buffer in the harness). Colours are GColor8 bytes. Shapes take
// coordinates in 1/16 px ("x16"); a pixel is filled when its centre is inside.
#include <pebble.h>
#include "config.h"

typedef uint8_t Col;
// 0xRRGGBB -> GColor8 byte (two bits per channel, opaque).
#define COL(hex) ((Col)(0xC0u | ((((uint32_t)(hex) >> 22) & 3u) << 4) | ((((uint32_t)(hex) >> 14) & 3u) << 2) | (((uint32_t)(hex) >> 6) & 3u)))

typedef struct {
  uint8_t *row[SCR_H];  // one byte per pixel, indexed by screen x
  int16_t x0[SCR_H];    // first drawable x on each row (the screen is round)
  int16_t x1[SCR_H];    // last drawable x on each row
} Canvas;

// A run-length role sheet made by tools/make_art.py (its docstring has the
// layout). Frames are drawn at the sheet's own screen position.
typedef struct {
  const uint8_t *table;  // frame offset table
  const uint8_t *data;   // frame data
  uint8_t frames;
  uint16_t w, h;
  int16_t left, top;
} Sheet;

// Reads sheet `index` out of an art blob.
void gfx_sheet_init(Sheet *s, const uint8_t *blob, int index);
// Draws frame f; role 0 is clear, other roles are looked up in pal.
void gfx_sheet(Canvas *c, const Sheet *s, int f, const Col *pal);

void gfx_clear(Canvas *c, Col col);
void gfx_span(Canvas *c, int y, int xa, int xb, Col col);
void gfx_pixel(Canvas *c, int x, int y, Col col);
// Convex polygon, n points as x16, y16 pairs.
void gfx_poly(Canvas *c, const int32_t *xy16, int n, Col col);
void gfx_disc(Canvas *c, int32_t cx16, int32_t cy16, int32_t r16, Col col);
// One-pixel line between two x16 points.
void gfx_line(Canvas *c, int32_t x0, int32_t y0, int32_t x1, int32_t y1, Col col);
// A bar from (ax, ay) to (bx, by), w16a wide at a and w16b wide at b, offset
// sideways by off16 (towards the bar's left-hand normal). All x16.
void gfx_bar(Canvas *c, int32_t ax, int32_t ay, int32_t bx, int32_t by, int32_t w16a, int32_t w16b,
             int32_t off16, Col col);
