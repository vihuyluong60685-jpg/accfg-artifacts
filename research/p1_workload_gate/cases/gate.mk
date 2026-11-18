include ../../runtime/snax-streamer-gemm.rules
include ../../runtime/Makefile.rules

# The target is bare metal and supplies no libc memory intrinsics.
CFLAGS += -ffreestanding -fno-builtin -DGATE_MOBILE=$(MOBILE)

gate.x: gates.o workload.o
	$(LD) $(LDFLAGS) $^ -o $@
