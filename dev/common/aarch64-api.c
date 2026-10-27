// Uses the existing validation startup/UART without modifying those sources.
#include "uart.h"
int validation_api_check(void);
void smoke_main(void) {
    if (!validation_api_check()) {uart_puts("LLVM_API_EXEC FAIL aarch64\n");return;}
    uart_puts("LLVM_API_EXEC PASS aarch64\nAARCH64 API DONE\n");
}
