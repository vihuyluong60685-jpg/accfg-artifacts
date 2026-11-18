builtin.module {
  func.func @audit_loop(%trips: index, %a0: i32, %a: i32, %b: i32, %c0: i32, %c: i32) {
    %zero = arith.constant 0 : index
    %step = arith.constant 1 : index
    %one = arith.constant 1 : i5
    %stride = arith.constant 256 : i32
    %initial = accfg.setup "snax_gemm" to ("a_ptr" = %a0 : i32, "b_ptr" = %b : i32, "c_ptr" = %c0 : i32) : !accfg.state<"snax_gemm">
    %exit = scf.for %i = %zero to %trips step %step iter_args(%state = %initial) -> (!accfg.state<"snax_gemm">) {
      %j = arith.index_cast %i : index to i32
      %off = arith.muli %stride, %j : i32
      %aj = arith.addi %a, %off : i32
      %cj = arith.addi %c, %off : i32
      %cfg = accfg.setup "snax_gemm" from %state to ("a_ptr" = %aj : i32, "c_ptr" = %cj : i32) : !accfg.state<"snax_gemm">
      %run = "accfg.launch"(%one, %one, %cfg) <{accelerator = "snax_gemm", param_names = ["launch_streamer", "launch_gemm"]}> : (i5, i5, !accfg.state<"snax_gemm">) -> !accfg.token<"snax_gemm">
      "accfg.await"(%run) : (!accfg.token<"snax_gemm">) -> ()
      scf.yield %cfg : !accfg.state<"snax_gemm">
    }
    func.return
  }
}
