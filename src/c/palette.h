#pragma once
// Finish and hand colours. The art is stored as roles (tools/make_art.py
// MATS); these tables turn roles into the 64 colours a Pebble can show.
#include "gfx.h"

typedef struct {
  Col wheel[16];    // gear rims, spokes and the balance: roles 1 (shadow) .. 6 (glint)
  Col overlay[16];  // 1-5 bridges, 6-9 gold work, 10-11 ruby, 12-13 blued screw, 14 ring, 15 white
  Col spring;       // hairspring
  Col steel[3];     // pallet fork: shadow, face, light
  Col hand[3];      // edge, shadow facet, lit facet
  Col cap;          // centre cap
  Col reserve;      // power-reserve hand
} Palette;

void palette_make(Palette *p, int finish, int hands);
