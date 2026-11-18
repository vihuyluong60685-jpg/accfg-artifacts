// Two real 8-by-K-by-8 GEMMs per iteration. The second B tensor is selected
// by the parity of the first output word from the immediately preceding GEMM.
#include <stdint.h>
#include <snrt.h>
#include "snax-streamer-gemm-lib.h"

#define MAX_STEPS 4
#define PACKED_BYTES ((PILOT_K / 8) * 256)

_Static_assert(PILOT_K >= 8 && PILOT_K % 8 == 0, "unsupported K");
_Static_assert(PILOT_STEPS >= 0 && PILOT_STEPS <= MAX_STEPS, "unsupported trip count");

struct workspace {
    int8_t a[2][PACKED_BYTES];
    int8_t b[3][PACKED_BYTES];
    int32_t first[MAX_STEPS][64];
    int32_t second[MAX_STEPS][64];
    int32_t copied[MAX_STEPS];
};

static volatile uintptr_t storage;

extern void pilot_step(uint32_t a0, uint32_t b0, uint32_t c0, uint32_t a1,
                       uint32_t b_even, uint32_t b_odd, uint32_t c1, uint32_t slot);

static unsigned offset(unsigned row, unsigned k) {
    return (k / 8) * 256 + row * 8 + (k % 8);
}

static uint32_t next_random(uint32_t *state) {
    uint32_t x = *state;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    *state = x;
    return x;
}

static void fill(int8_t *matrix, uint32_t *state) {
    for (unsigned row = 0; row < 8; ++row)
        for (unsigned k = 0; k < PILOT_K; ++k)
            matrix[offset(row, k)] = (int)(next_random(state) % 15) - 7;
}

static int32_t gold(const int8_t *a, const int8_t *b, unsigned row, unsigned col) {
    int32_t sum = 0;
    for (unsigned k = 0; k < PILOT_K; ++k)
        sum += (int32_t)a[offset(row, k)] * (int32_t)b[offset(col, k)];
    return sum;
}

uint32_t _mlir_ciface_pilot_late_b(uint32_t src, uint32_t even, uint32_t odd, uint32_t slot) {
#if PILOT_DMA
    (void)src;
    struct workspace *work = (void *)storage;
    // Producer has been awaited by pilot_step. Hand off to the DMA hart, then
    // wait for DMA completion plus the publishing barrier before reading L1.
    snrt_cluster_hw_barrier();
    snrt_cluster_hw_barrier();
    const int32_t word = ((volatile int32_t *)work->copied)[slot];
#else
    (void)slot;
    const int32_t word = *(volatile int32_t *)(uintptr_t)src;
#endif
    return (word & 1) ? odd : even;
}

static inline uint32_t timed_boundary(void) {
    uint32_t value;
    asm volatile("csrr %0, mcycle" : "=r"(value) :: "memory");
    return value;
}

int main(void) {
    if (snrt_is_dm_core()) {
        uintptr_t raw = (uintptr_t)snrt_l1alloc(sizeof(struct workspace) + 256);
        storage = (raw + 255) & ~(uintptr_t)255;
    }
    snrt_cluster_hw_barrier();
    struct workspace *work = (void *)storage;
    if (snrt_is_dm_core()) {
#if PILOT_DMA
        for (unsigned slot = 0; slot < PILOT_STEPS; ++slot) {
            snrt_cluster_hw_barrier();
            snrt_dma_start_1d(&work->copied[slot], &work->first[slot][0], sizeof(int32_t));
            snrt_dma_wait_all();
            snrt_cluster_hw_barrier();
        }
#endif
        snrt_cluster_hw_barrier();
        return 0;
    }

    uint32_t state = PILOT_SEED;
    for (unsigned i = 0; i < 2; ++i)
        fill(work->a[i], &state);
    for (unsigned i = 0; i < 3; ++i)
        fill(work->b[i], &state);
    for (unsigned slot = 0; slot < MAX_STEPS; ++slot) {
        work->copied[slot] = 0x12345678;
        for (unsigned i = 0; i < 64; ++i) {
            work->first[slot][i] = 0x12345678;
            work->second[slot][i] = 0x12345678;
        }
    }

    uintptr_t origin = (uintptr_t)snrt_l1_next();
    set_streamer_csr(PILOT_K / 8, 1, 1, 256, 512, 8, 256, 512, 8, 256, 256, 32,
                     (uintptr_t)work->a[0] - origin, (uintptr_t)work->b[0] - origin,
                     (uintptr_t)work->first[0] - origin);
    set_block_gemm_csr(PILOT_K / 8, 1, 1, 0);

    // Reporting outside the two markers. Replaying the same ELF should be
    // deterministic. The DMA scope times metadata copy, not all input staging.
    const uint32_t start = timed_boundary();
    for (unsigned slot = 0; slot < PILOT_STEPS; ++slot) {
        pilot_step((uintptr_t)work->a[0], (uintptr_t)work->b[0],
                   (uintptr_t)work->first[slot], (uintptr_t)work->a[1],
                   (uintptr_t)work->b[1], (uintptr_t)work->b[2],
                   (uintptr_t)work->second[slot], slot);
    }
    const uint32_t end = timed_boundary();

    unsigned errors = 0;
    unsigned choices = 0;
    uintptr_t live_a = (uintptr_t)work->a[0], live_b = (uintptr_t)work->b[0];
    uintptr_t live_c = (uintptr_t)work->first[0];
    for (unsigned slot = 0; slot < PILOT_STEPS; ++slot) {
        int32_t selector = gold(work->a[0], work->b[0], 0, 0);
        unsigned choice = 1 + (selector & 1);
        choices |= 1u << (choice - 1);
        printf("P1_EXPECT slot=%u selector=%d first_a=%x first_b=%x first_c=%x next_a=%x next_b=%x next_c=%x\n",
               slot, (int)selector, (uint32_t)(uintptr_t)work->a[0], (uint32_t)(uintptr_t)work->b[0],
               (uint32_t)(uintptr_t)work->first[slot], (uint32_t)(uintptr_t)work->a[1],
               (uint32_t)(uintptr_t)work->b[choice], (uint32_t)(uintptr_t)work->second[slot]);
#if PILOT_DMA
        errors += work->copied[slot] != selector;
#endif
        for (unsigned row = 0; row < 8; ++row)
            for (unsigned col = 0; col < 8; ++col) {
                errors += work->first[slot][row * 8 + col] != gold(work->a[0], work->b[0], row, col);
                errors += work->second[slot][row * 8 + col] != gold(work->a[1], work->b[choice], row, col);
            }
        live_a = (uintptr_t)work->a[1];
        live_b = (uintptr_t)work->b[choice];
        live_c = (uintptr_t)work->second[slot];
    }
    unsigned live_errors = (read_csr(978) != live_a) + (read_csr(979) != live_b) +
                           (read_csr(980) != live_c);
    if (PILOT_STEPS == 0) {
        errors += work->first[0][0] != 0x12345678;
        errors += work->second[0][0] != 0x12345678;
    }
    printf("P1_RESULT cycles=%u start=%u end=%u errors=%u live_errors=%u choices=%u K=%u steps=%u dma=%u seed=%u\n",
           end - start, start, end, errors, live_errors, choices,
           PILOT_K, PILOT_STEPS, PILOT_DMA, PILOT_SEED);
    snrt_cluster_hw_barrier();
    return errors != 0 || live_errors != 0;
}
