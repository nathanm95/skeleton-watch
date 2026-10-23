#pragma once
// Per-watch screen size. The Mac harness defines the same PBL_PLATFORM_*
// macros the SDK does. Skeleton is for the round watches only.

#if defined(PBL_PLATFORM_GABBRO)
#define SCR_W 260
#define SCR_H 260
#elif defined(PBL_PLATFORM_CHALK)
#define SCR_W 180
#define SCR_H 180
#else
#error "Skeleton supports the round watches (chalk, gabbro) only"
#endif
