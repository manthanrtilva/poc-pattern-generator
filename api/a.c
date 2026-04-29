/**
 * V4 segment-based pattern decoder for MCU.
 *
 * Binary format:
 *   HEADER:
 *     [4B leds (u32 BE)] [4B num_frames (u32 BE)] [4B delay_ms (u32 BE)]
 *     [1B pal_len (0=256)] [pal_len * 3B RGB palette]
 *   KEYFRAME:
 *     [1B num_runs] [runs: 1B count, 1B palette_idx] ...
 *   SEGMENTS:
 *     [1B num_segments] [per seg: 1B start_led, 1B repeat_count, 1B flags]
 *       flags 0 = kernel [-1,-1,+1,+1]
 *       flags 1 = kernel [+1,+1,-1,-1]
 *
 * Usage:
 *   1. Call v4_init() once with the binary blob pointer.
 *   2. In your main loop call v4_next_frame() which fills the RGB
 *      output buffer and returns the delay in ms (0 = animation done).
 *
 * Memory: only needs a small framebuffer of palette indices (1 byte/LED)
 * plus the palette itself; the binary data is read directly from flash.
 */

#include <stdint.h>
#include <stddef.h>
#include <string.h>

/* ---------- configuration ---------- */
#ifndef V4_MAX_LEDS
#define V4_MAX_LEDS 256
#endif

#ifndef V4_MAX_PALETTE
#define V4_MAX_PALETTE 256
#endif

/* ---------- types ---------- */
typedef struct {
    /* Parsed header */
    uint16_t leds;
    uint32_t num_frames;
    uint32_t delay_ms;

    /* Palette */
    uint16_t pal_len;
    uint8_t  palette[V4_MAX_PALETTE][3]; /* [idx][R,G,B] */

    /* Framebuffer: palette indices per LED (signed for ±1 arithmetic) */
    int16_t fb[V4_MAX_LEDS];

    /* Segment playback state */
    const uint8_t *seg_ptr;    /* points into binary blob at segments section */
    uint8_t  num_segments;
    uint8_t  cur_segment;      /* which segment we're on */
    uint8_t  seg_start;        /* start_led of current segment */
    uint8_t  seg_remaining;    /* repeats left in current segment */
    int8_t   seg_kernel[4];    /* current kernel */

    /* Frame counter */
    uint32_t frame_idx;

    /* Whether keyframe has been emitted */
    uint8_t  keyframe_emitted;
} v4_state_t;

/* ---------- helpers ---------- */
static inline uint32_t read_u32_be(const uint8_t *p)
{
    return ((uint32_t)p[0] << 24) |
           ((uint32_t)p[1] << 16) |
           ((uint32_t)p[2] <<  8) |
           ((uint32_t)p[3]);
}

static void v4_load_segment(v4_state_t *s)
{
    if (s->cur_segment >= s->num_segments) {
        s->seg_remaining = 0;
        return;
    }
    const uint8_t *p = s->seg_ptr + (s->cur_segment * 3);
    s->seg_start     = p[0];
    s->seg_remaining = p[1];
    uint8_t flags    = p[2];

    if (flags == 0) {
        s->seg_kernel[0] = -1;
        s->seg_kernel[1] = -1;
        s->seg_kernel[2] =  1;
        s->seg_kernel[3] =  1;
    } else {
        s->seg_kernel[0] =  1;
        s->seg_kernel[1] =  1;
        s->seg_kernel[2] = -1;
        s->seg_kernel[3] = -1;
    }
}

/* ---------- public API ---------- */

/**
 * Initialise the decoder from a binary blob (e.g. from flash / SPIFFS).
 * Returns 0 on success, -1 on invalid data.
 */
int v4_init(v4_state_t *s, const uint8_t *data, size_t len)
{
    memset(s, 0, sizeof(*s));

    if (len < 13)
        return -1;

    size_t off = 0;

    /* Header */
    s->leds       = (uint16_t)read_u32_be(data + off); off += 4;
    s->num_frames = read_u32_be(data + off);            off += 4;
    s->delay_ms   = read_u32_be(data + off);            off += 4;

    if (s->leds > V4_MAX_LEDS)
        return -1;

    uint8_t pl = data[off]; off += 1;
    s->pal_len = (pl == 0) ? 256 : pl;

    if (s->pal_len > V4_MAX_PALETTE)
        return -1;
    if (off + s->pal_len * 3 > len)
        return -1;

    /* Read palette */
    for (uint16_t i = 0; i < s->pal_len; i++) {
        s->palette[i][0] = data[off];
        s->palette[i][1] = data[off + 1];
        s->palette[i][2] = data[off + 2];
        off += 3;
    }

    /* Decode keyframe RLE into framebuffer */
    if (off >= len)
        return -1;
    uint8_t num_runs = data[off]; off += 1;
    uint16_t fb_pos = 0;
    for (uint8_t r = 0; r < num_runs; r++) {
        if (off + 2 > len)
            return -1;
        uint8_t count = data[off];
        uint8_t idx   = data[off + 1];
        off += 2;
        for (uint8_t c = 0; c < count && fb_pos < s->leds; c++) {
            s->fb[fb_pos++] = (int16_t)idx;
        }
    }

    /* Read segments header */
    if (off >= len)
        return -1;
    s->num_segments = data[off]; off += 1;

    if (off + s->num_segments * 3 > len)
        return -1;

    s->seg_ptr     = data + off;
    s->cur_segment = 0;
    s->frame_idx   = 0;
    s->keyframe_emitted = 0;

    /* Pre-load first segment */
    v4_load_segment(s);

    return 0;
}

/**
 * Fill `rgb_out` with the next frame's pixel data (3 bytes per LED: R,G,B).
 * `rgb_out` must be at least s->leds * 3 bytes.
 *
 * Returns delay_ms (>0) if a frame was produced.
 * Returns 0 when the animation is finished (no more frames).
 */
uint32_t v4_next_frame(v4_state_t *s, uint8_t *rgb_out)
{
    if (s->frame_idx >= s->num_frames)
        return 0;

    if (!s->keyframe_emitted) {
        /* First call: emit keyframe as-is */
        s->keyframe_emitted = 1;
    } else {
        /* Apply one step of the current segment's kernel */
        if (s->seg_remaining == 0) {
            /* Shouldn't happen if data is valid, but guard anyway */
            return 0;
        }

        uint8_t st = s->seg_start;
        for (uint8_t k = 0; k < 4; k++) {
            if (st + k < s->leds) {
                s->fb[st + k] += s->seg_kernel[k];
            }
        }

        s->seg_remaining--;
        if (s->seg_remaining == 0) {
            s->cur_segment++;
            v4_load_segment(s);
        }
    }

    /* Expand framebuffer palette indices to RGB */
    for (uint16_t i = 0; i < s->leds; i++) {
        int16_t idx = s->fb[i];
        if (idx < 0) idx = 0;
        if (idx >= (int16_t)s->pal_len) idx = s->pal_len - 1;
        rgb_out[i * 3]     = s->palette[idx][0];
        rgb_out[i * 3 + 1] = s->palette[idx][1];
        rgb_out[i * 3 + 2] = s->palette[idx][2];
    }

    s->frame_idx++;
    return s->delay_ms;
}

/**
 * Reset playback to the beginning (re-init from the same blob).
 * Cheaper than calling v4_init again if you have the state.
 * `data` must be the same pointer passed to v4_init.
 */
int v4_reset(v4_state_t *s, const uint8_t *data, size_t len)
{
    return v4_init(s, data, len);
}

/*
 * Example usage (pseudo-code for ESP32 / Arduino / bare-metal):
 *
 *   #include "a.c"  // or split into .h/.c
 *
 *   // Binary blob from maxicanwave_bin_generator_v4.py stored in flash
 *   extern const uint8_t pattern_data[];
 *   extern const size_t  pattern_size;
 *
 *   static v4_state_t state;
 *   static uint8_t    rgb_buf[V4_MAX_LEDS * 3];
 *
 *   void setup() {
 *       v4_init(&state, pattern_data, pattern_size);
 *   }
 *
 *   void loop() {
 *       uint32_t delay = v4_next_frame(&state, rgb_buf);
 *       if (delay == 0) {
 *           // Animation done — loop it
 *           v4_reset(&state, pattern_data, pattern_size);
 *           return;
 *       }
 *       // Send rgb_buf to your LED strip (WS2812 / NeoPixel / etc.)
 *       led_strip_write(rgb_buf, state.leds);
 *       delay_ms(delay);
 *   }
 */
