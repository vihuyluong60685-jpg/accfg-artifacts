#include <stdint.h>
#include <snrt.h>
#include "snax-streamer-gemm-lib.h"

struct scratch {
    int8_t a[5][256],b[256];
    int32_t c[5][64];
};
static volatile uintptr_t shared;
extern void audit_loop(uint32_t, uint32_t,uint32_t,uint32_t,uint32_t,uint32_t);

int main(void) {
    if (snrt_is_dm_core()) {
        const uintptr_t t=(uintptr_t)snrt_l1alloc(sizeof(struct scratch)+255);
        shared=(t+255)&~255u;
    }
    snrt_cluster_hw_barrier();
    if (snrt_is_dm_core()) {
        snrt_cluster_hw_barrier();
        return 0;
    }
    struct scratch *s=(void *)shared;
    for (unsigned row=0; row<5; ++row)
        for (unsigned i=0;i<64;++i)
            ((volatile int8_t *)s->a[row])[i]=row+1;
    for (unsigned i=0; i<64; ++i) ((volatile int8_t *)s->b)[i]=1;
    unsigned errors=0;
    for (unsigned t=0; t<3; ++t) {
        unsigned trips=t==2 ? 3:t;
        for (unsigned row=0;row<5;++row)
            for (unsigned i=0;i<64;++i)
                ((volatile int32_t *)s->c[row])[i]=-9000;
        uintptr_t origin=(uintptr_t)snrt_l1_next();
        set_streamer_csr(1,1,1,256,512,8,256,512,8,256,256,32,
            (uintptr_t)s->a[0]-origin,(uintptr_t)s->b-origin,(uintptr_t)s->c[0]-origin);
        set_block_gemm_csr(1,1,1,0);
        audit_loop(trips,(uintptr_t)s->a[0],(uintptr_t)s->a[1],(uintptr_t)s->b,
                   (uintptr_t)s->c[0],(uintptr_t)s->c[1]);
        unsigned bad=0;
        for (unsigned row=0;row<5;++row)
            for (unsigned i=0;i<64;++i)
                bad+=s->c[row][i]!=(((row>0 && row<=trips) || (AUDIT_LIVE_CONSUMER && row==trips)) ? (int)(row+1)*8:-9000);
        uint32_t a=read_csr(978), b=read_csr(979), c=read_csr(980);
        unsigned live=(a!=(uintptr_t)s->a[trips])+(b!=(uintptr_t)s->b)+(c!=(uintptr_t)s->c[trips]);
        // Explicit external reset used after observation and before the next run.
        write_csr(978,(uintptr_t)s->a[0]);
        unsigned reset=(read_csr(978)!=(uintptr_t)s->a[0]);
        printf("AUDIT_LIVE trips=%u golden_errors=%u live_errors=%u reset_errors=%u actual_a=%x expected_a=%x actual_c=%x expected_c=%x\n",
                trips,bad,live,reset,a,(unsigned)(uintptr_t)s->a[trips],c,(unsigned)(uintptr_t)s->c[trips]);
        errors+=bad+live+reset;
    }
    snrt_cluster_hw_barrier();
    return errors!=0;
}
