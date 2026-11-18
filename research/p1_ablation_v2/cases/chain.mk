include ../../runtime/snax-streamer-gemm.rules
include ../../runtime/Makefile.rules

CFLAGS += -DPILOT_K=$(K) -DPILOT_STEPS=$(STEPS) -DPILOT_DMA_BYTES=$(DMA) -DPILOT_SEED=$(SEED) -DPILOT_CASE=$(SCENARIO)

chain.x: tensor_chain.o chain.o
	$(LD) $(LDFLAGS) $^ -o $@
