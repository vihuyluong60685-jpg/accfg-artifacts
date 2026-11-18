builtin.module {
  func.func @audit_loop(%trips: index, %a0: i32, %a: i32, %b: i32, %c0: i32, %c: i32) {
    %zero = arith.constant 0 : index
    %step = arith.constant 1 : index
    %one = arith.constant 1 : i5
    %stride = arith.constant 256 : i32
    %initial = accfg.setup "snax_gemm" to ("a_ptr" = %a0 : i32, "b_ptr" = %b : i32, "c_ptr" = %c0 : i32) : !accfg.state<"snax_gemm">
    %has_work = arith.cmpi slt, %zero, %trips : index
    %entry = scf.if %has_work -> (!accfg.state<"snax_gemm">) {
      %first = accfg.setup "snax_gemm" from %initial to ("a_ptr" = %a : i32, "c_ptr" = %c : i32) : !accfg.state<"snax_gemm">
      scf.yield %first : !accfg.state<"snax_gemm">
    } else {
      scf.yield %initial : !accfg.state<"snax_gemm">
    }
    %exit = scf.for %i = %zero to %trips step %step iter_args(%state = %entry) -> (!accfg.state<"snax_gemm">) {
      %run = "accfg.launch"(%one, %one, %state) <{accelerator = "snax_gemm", param_names = ["launch_streamer", "launch_gemm"]}> : (i5, i5, !accfg.state<"snax_gemm">) -> !accfg.token<"snax_gemm">
      %next_i = arith.addi %i, %step : index
      %keep = arith.cmpi slt, %next_i, %trips : index
      %next = scf.if %keep -> (!accfg.state<"snax_gemm">) {
        %j = arith.index_cast %next_i : index to i32
        %off = arith.muli %stride, %j : i32
        %aj = arith.addi %a, %off : i32
        %cj = arith.addi %c, %off : i32
        %cfg = accfg.setup "snax_gemm" from %state to ("a_ptr" = %aj : i32, "c_ptr" = %cj : i32) : !accfg.state<"snax_gemm">
        scf.yield %cfg : !accfg.state<"snax_gemm">
      } else {
        scf.yield %state : !accfg.state<"snax_gemm">
      }
      "accfg.await"(%run) : (!accfg.token<"snax_gemm">) -> ()
      scf.yield %next : !accfg.state<"snax_gemm">
    }
    %follow = "accfg.launch"(%one, %one, %exit) <{accelerator = "snax_gemm", param_names = ["launch_streamer", "launch_gemm"]}> : (i5, i5, !accfg.state<"snax_gemm">) -> !accfg.token<"snax_gemm">
    "accfg.await"(%follow) : (!accfg.token<"snax_gemm">) -> ()
    func.return
  }
}
