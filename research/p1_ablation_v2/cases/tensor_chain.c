// Two real OpenGeMM jobs. In the tensor chain the full producer result is
// requantized and packed as the next job's A input.
#include <stdint.h>
#include <snrt.h>
#include "snax-streamer-gemm-lib.h"
#include "chain_golden.h"

#define CASE_CHAIN 0
#define CASE_READY 1
#define CASE_LATE 2
#define CASE_OBSERVE 3
#define PACKED_BYTES ((PILOT_K / 8) * 256)
#define MAX_STEPS 3
#define PAYLOAD_WORDS ((PILOT_DMA_BYTES ? PILOT_DMA_BYTES : 256) / sizeof(int32_t))

_Static_assert(PILOT_K >= 8 && PILOT_K % 8 == 0, "OpenGeMM K tiles");
_Static_assert(PILOT_STEPS >= 0 && PILOT_STEPS <= MAX_STEPS, "fixture capacity");
_Static_assert(PILOT_DMA_BYTES == 0 || PILOT_DMA_BYTES >= 256, "whole producer tile");

struct workspace {
    int8_t input_a[2][PACKED_BYTES];
    int8_t input_b[3][PACKED_BYTES];
    int8_t packed[MAX_STEPS][2][PACKED_BYTES];
    int32_t first[MAX_STEPS][PAYLOAD_WORDS];
    int32_t copied[MAX_STEPS][PAYLOAD_WORDS];
    int32_t second[MAX_STEPS][2][64];
    uint32_t observed[MAX_STEPS][3];
};
static volatile uintptr_t storage;

extern void chain_step(uint32_t a0, uint32_t b0, uint32_t c0, uint32_t a_alt,
                       uint32_t b1, uint32_t b_alt, uint32_t c1, uint32_t c_alt);

static unsigned offset(unsigned row, unsigned k) {
    return (k / 8) * 256 + row * 8 + (k % 8);
}

static uint32_t random_word(uint32_t *state) {
    uint32_t x = *state;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    return *state = x;
}

static void fill(int8_t *matrix, uint32_t *state) {
    for (unsigned row = 0; row < 8; ++row)
        for (unsigned k = 0; k < PILOT_K; ++k)
            matrix[offset(row, k)] = (int)(random_word(state) % 15) - 7;
}

static int32_t sentinel(unsigned slot, unsigned index) {
    return 0x58b50000u | (slot << 11) | index;
}

static int8_t quant(int32_t value) {
    int32_t scaled = value / 3;
    if (scaled < -128) return -128;
    if (scaled > 127) return 127;
    return scaled;
}

uint32_t _mlir_ciface_materialize(uint32_t raw) {
    struct workspace *w = (void *)storage;
    unsigned slot = ((uintptr_t)raw - (uintptr_t)w->first)/sizeof(w->first[0]);
    volatile int32_t *source = (volatile int32_t *)(uintptr_t)raw;
#if PILOT_CASE == CASE_OBSERVE
    w->observed[slot][0] = read_csr(978);
    w->observed[slot][1] = read_csr(979);
    w->observed[slot][2] = read_csr(980);
#endif
#if PILOT_DMA_BYTES
    snrt_cluster_hw_barrier();
    snrt_cluster_hw_barrier();
    source = w->copied[slot];
#endif
    unsigned choice = (uint32_t)source[0] & 1;
    int8_t *dest = w->packed[slot][choice];
    for (unsigned i = 0; i < 64; ++i)
        dest[offset(i/8,i%8)] = quant(source[i]);
    return (uintptr_t)dest;
}

static inline uint32_t boundary(void) {
    uint32_t cycle;
    asm volatile("csrr %0, mcycle" : "=r"(cycle) :: "memory");
    return cycle;
}

int main(void) {
    if (snrt_is_dm_core()) {
        uintptr_t raw = (uintptr_t)snrt_l1alloc(sizeof(struct workspace) + 256);
        storage = (raw + 255) & ~(uintptr_t)255;
    }
    snrt_cluster_hw_barrier();
    struct workspace *w = (void *)storage;
    if (snrt_is_dm_core()) {
#if PILOT_DMA_BYTES
        for (unsigned slot = 0; slot < PILOT_STEPS; ++slot) {
            snrt_cluster_hw_barrier();
            snrt_dma_start_1d(w->copied[slot], w->first[slot], PILOT_DMA_BYTES);
            snrt_dma_wait_all();
            snrt_cluster_hw_barrier();
        }
#endif
        snrt_cluster_hw_barrier();
        return 0;
    }
    uint32_t rng = PILOT_SEED;
    for (unsigned i = 0; i < 2; ++i) fill(w->input_a[i], &rng);
    for (unsigned i = 0; i < 3; ++i) fill(w->input_b[i], &rng);
    for (unsigned slot = 0; slot < MAX_STEPS; ++slot) {
        for (unsigned i = 0; i < PAYLOAD_WORDS; ++i) {
            w->first[slot][i] = sentinel(slot, i);
            ((volatile int32_t *)w->copied[slot])[i] = -1;
        }
        for (unsigned pos = 0; pos < 2; ++pos) {
            for (unsigned i = 0; i < PACKED_BYTES; ++i) ((volatile int8_t *)w->packed[slot][pos])[i] = 0;
            for (unsigned i = 0; i < 64; ++i) w->second[slot][pos][i] = sentinel(slot, i);
        }
    }
    uintptr_t origin = (uintptr_t)snrt_l1_next();
    set_streamer_csr(PILOT_K/8, 1, 1, 256, 512, 8, 256, 512, 8, 256, 256, 32,
                     (uintptr_t)w->input_a[0]-origin, (uintptr_t)w->input_b[0]-origin,
                     (uintptr_t)w->first[0]-origin);
    set_block_gemm_csr(PILOT_K/8, 1, 1, 0);
    uint32_t begin = boundary();
    for (unsigned slot = 0; slot < PILOT_STEPS; ++slot)
        chain_step((uintptr_t)w->input_a[0], (uintptr_t)w->input_b[0], (uintptr_t)w->first[slot],
#if PILOT_CASE == CASE_READY
                   (uintptr_t)w->input_a[1],
#else
                   (uintptr_t)w->packed[slot][1],
#endif
                   (uintptr_t)w->input_b[1], (uintptr_t)w->input_b[2],
                   (uintptr_t)w->second[slot][0], (uintptr_t)w->second[slot][1]);
    uint32_t end = boundary();

    uint32_t errors = 0, live_errors = 0, observed_errors = 0, dma_errors = 0;
    uintptr_t live_a = (uintptr_t)w->input_a[0], live_b = (uintptr_t)w->input_b[0];
    uintptr_t live_c = (uintptr_t)w->first[0];
    for (unsigned slot = 0; slot < PILOT_STEPS; ++slot) {
        int32_t selector = expected_first[0];
        unsigned choice = (uint32_t)selector & 1;
        const unsigned next_variant = PILOT_CASE == CASE_LATE && choice;
        uint32_t a = (uintptr_t)w->input_a[0], b = (uintptr_t)w->input_b[0], c = (uintptr_t)w->first[slot];
        live_a = PILOT_CASE == CASE_READY ? (uintptr_t)w->input_a[1] : (uintptr_t)w->packed[slot][choice];
        live_b = (uintptr_t)w->input_b[1+next_variant];
        live_c = (uintptr_t)w->second[slot][next_variant];
        printf("P2_EXPECT slot=%u selector=%d first_a=%x first_b=%x first_c=%x next_a=%x next_b=%x next_c=%x source=%x\n",
               slot, (int)selector, a, b, c, (uint32_t)live_a, (uint32_t)live_b, (uint32_t)live_c,
#if PILOT_DMA_BYTES
               (uint32_t)(uintptr_t)w->copied[slot]
#else
               c
#endif
        );
        for (unsigned i = 0; i < 64; ++i) {
            errors += w->first[slot][i] != expected_first[i];
            errors += w->second[slot][next_variant][i] != expected_second[i];
#if PILOT_CASE != CASE_READY
            errors += w->packed[slot][choice][offset(i/8,i%8)] != expected_packed[i];
#endif
#if PILOT_DMA_BYTES
            dma_errors += w->copied[slot][i] != expected_first[i];
#endif
        }
#if PILOT_DMA_BYTES
        if (PAYLOAD_WORDS > 64)
            dma_errors += w->copied[slot][PAYLOAD_WORDS-1] != sentinel(slot,PAYLOAD_WORDS-1);
#endif
#if PILOT_CASE == CASE_OBSERVE
        observed_errors += w->observed[slot][0] != a;
        observed_errors += w->observed[slot][1] != b;
        observed_errors += w->observed[slot][2] != c;
#endif
    }
    if (PILOT_STEPS == 0)
        errors += (w->first[0][0] != sentinel(0,0)) + (w->second[0][0][0] != sentinel(0,0));
    live_errors = (read_csr(978) != live_a) + (read_csr(979) != live_b) + (read_csr(980) != live_c);
    printf("P2_RESULT cycles=%u start=%u end=%u errors=%u live_errors=%u dma_errors=%u observed_errors=%u K=%u steps=%u dma_bytes=%u seed=%u scenario=%u\n",
           end-begin, begin, end, errors, live_errors, dma_errors, observed_errors,
           PILOT_K, PILOT_STEPS, PILOT_DMA_BYTES, PILOT_SEED, PILOT_CASE);
    snrt_cluster_hw_barrier();
    return errors || live_errors || dma_errors || observed_errors;
}
