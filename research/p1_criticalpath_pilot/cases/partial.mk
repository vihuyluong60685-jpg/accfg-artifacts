include ../../runtime/snax-streamer-gemm.rules
include ../../runtime/Makefile.rules

CFLAGS += -DPILOT_K=$(K) -DPILOT_STEPS=$(STEPS) -DPILOT_DMA=$(DMA) -DPILOT_SEED=$(SEED) -DPILOT_FAST_GOLD=$(FAST_GOLD)

pilot.x: partial_harness.o pilot.o
	$(LD) $(LDFLAGS) $^ -o $@
