// Separate translation unit, built with vectorization disabled. Unsigned wrap is defined.
#include <stddef.h>
#include <stdint.h>
void validation_add_ref(uint32_t *out, const uint32_t *a, const uint32_t *b, size_t n) {
    for (size_t i=0; i<n; ++i) out[i] = a[i] + b[i];
}
