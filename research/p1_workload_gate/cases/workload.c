// Quantized graph harness. Fixed separate SPM objects across both launches.
#include <stdint.h>
#include <snrt.h>
#include "gate_fixtures.h"

struct workspace {
    int8_t a[2][256];
    int8_t b[2][256];
    int32_t c[2][64];
    int8_t output[64];
};
static volatile uintptr_t shared;

extern void gate_graph(uint32_t a0,uint32_t b0,uint32_t c0,
                       uint32_t a1,uint32_t b1,uint32_t c1);

static inline int bounded(int x,int lo,int hi) {
    return x<lo ? lo : (x>hi ? hi : x);
}

void _mlir_ciface_publish_middle(uint32_t producer,uint32_t destination) {
    const int32_t *scores = (const void *)(uintptr_t)producer;
    int8_t *next = (void *)(uintptr_t)destination;
#if GATE_MOBILE
    int8_t activations[64];
    for (unsigned i = 0; i < 64; ++i)
        activations[i] = bounded(scores[i]/4,0,24);
    for (int row = 0; row < 2; ++row) {
        for (int col = 0; col < 4; ++col) {
            for (int ch = 0; ch < 8; ++ch) {
                int sum = 0;
                for (int dr = -1; dr <= 1; ++dr) {
                    for (int dc = -1; dc <= 1; ++dc) {
                        int rr = row + dr, cc = col + dc;
                        if (rr>=0 && rr<2 && cc>=0 && cc<4)
                            sum += activations[(rr*4+cc)*8+ch]*fixture_kernel[((dr+1)*3+dc+1)*8+ch];
                    }
                }
                next[(row*4+col)*8+ch] = bounded(sum/8,0,24);
            }
        }
    }
#else
    for (int row = 0; row < 8; ++row) {
        const int32_t *in = scores + row*8;
        int max = in[0], contribution[8], denom = 0;
        for (int j = 1; j < 8; ++j)
            if (in[j] > max) max = in[j];
        for (int j = 0; j < 8; ++j) {
            int index = bounded((max-in[j]+4)/8,0,31);
            contribution[j] = fixture_exp[index];
            denom += contribution[j];
        }
        for (int j = 0; j < 8; ++j)
            next[row*8+j] = (contribution[j]*127+denom/2)/denom;
    }
#endif
}

static inline uint32_t boundary(void) {
    uint32_t result;
    asm volatile("csrr %0, mcycle" : "=r"(result) :: "memory");
    return result;
}

int main(void) {
    if (snrt_is_dm_core()) {
        uintptr_t raw = (uintptr_t)snrt_l1alloc(sizeof(struct workspace)+255);
        shared = (raw+255) & ~(uintptr_t)255;
    }
    snrt_cluster_hw_barrier();
    if (snrt_is_dm_core()) {
        snrt_cluster_hw_barrier();
        return 0;
    }
    struct workspace *w = (void *)shared;
    unsigned total_errors = 0;
    const uint32_t a0=(uintptr_t)w->a[0], b0=(uintptr_t)w->b[0], c0=(uintptr_t)w->c[0];
    const uint32_t a1=(uintptr_t)w->a[1], b1=(uintptr_t)w->b[1], c1=(uintptr_t)w->c[1];
    for (unsigned case_id = 0; case_id < sizeof(seeds)/sizeof(seeds[0]); ++case_id) {
        // All payload packing is timed. The destination's unused tile padding
        // is never consumed in the fixed single-tile GEMMs.
        uint32_t begin = boundary();
        for (unsigned i = 0; i < 64; ++i) {
            w->a[0][i] = fixture_data[case_id][i];
            w->b[0][i] = fixture_b0[case_id][i];
            w->b[1][i] = fixture_b1[case_id][i];
        }
        gate_graph(a0,b0,c0,a1,b1,c1);
        for (unsigned i = 0; i < 64; ++i) {
#if GATE_MOBILE
            int projected = w->c[1][i]/8 + fixture_data[case_id][i];
#else
            int projected = w->c[1][i]/127;
#endif
            w->output[i] = bounded(projected,-128,127);
        }
        uint32_t end = boundary();
        unsigned errors = 0;
        unsigned live = (read_csr(978)!=a1) + (read_csr(979)!=b1) + (read_csr(980)!=c1);
        for (unsigned i = 0; i < 64; ++i) {
            errors += w->c[0][i]!=fixture_producer[case_id][i];
            errors += w->a[1][i]!=fixture_inter[case_id][i];
            errors += w->c[1][i]!=fixture_consumer[case_id][i];
            errors += w->output[i]!=fixture_final[case_id][i];
        }
        printf("GATE seed=%u start=%u end=%u cycles=%u errors=%u live_errors=%u first_a=%x first_b=%x first_c=%x next_a=%x next_b=%x next_c=%x\n",
               seeds[case_id],begin,end,end-begin,errors,live,a0,b0,c0,a1,b1,c1);
        total_errors += errors+live;
    }
    snrt_cluster_hw_barrier();
    return total_errors != 0;
}
