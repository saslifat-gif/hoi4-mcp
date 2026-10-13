/* Offline simulation of the command factory/executor ABI, not a live HOI4 test. */
#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include "time_pause_command.h"

static union { uintptr_t align; unsigned char bytes[0x50]; } object;
static const uintptr_t expected_vtable = 0x12345678;
static int mode, factory_calls, execute_calls, state;
static uintptr_t factory(void) {
    factory_calls++;
    if (mode == 1) return 0;
    memset(object.bytes, 0, sizeof object.bytes);
    *(uintptr_t *)object.bytes = mode == 3 ? 0x87654321 : expected_vtable;
    *(int *)(object.bytes + 0xc) = -1;
    *(unsigned int *)(object.bytes + 0x14) = 0xffff0000;
    *(uintptr_t *)(object.bytes + 0x40) = 15; /* Inline reason-string capacity. */
    return (uintptr_t)object.bytes;
}
static int readable(const void *ptr, size_t length) {
    return mode != 2 && ptr == object.bytes && length <= sizeof object.bytes;
}
static void execute(void *ptr) {
    assert(ptr == object.bytes);
    assert(*(uintptr_t *)object.bytes == expected_vtable);
    assert(*(int *)(object.bytes + 0xc) == -1);
    assert(*(unsigned int *)(object.bytes + 0x14) == 0xffff0000);
    /* The engine receives its factory-initialized empty string, never null. */
    for (int i = 0x28; i < 0x40; i++) assert(object.bytes[i] == 0);
    assert(*(uintptr_t *)(object.bytes + 0x40) == 15);
    assert(object.bytes[0x48] == 1);
    assert(object.bytes[0x49] == 0);
    execute_calls++;
    state = !state;
}
int main(int argc, char **argv) {
    assert(argc == 4);
    state = atoi(argv[1]);
    int desired = atoi(argv[2]);
    mode = atoi(argv[3]);
    int before = state;
    int ok = execute_pause_command(before, desired, expected_vtable,
                                   factory, readable, execute);
    if (before == desired) {
        assert(ok && !factory_calls && !execute_calls && state == before);
    } else if (mode) {
        assert(!ok && factory_calls == 1 && !execute_calls && state == before);
    } else {
        assert(ok && factory_calls == 1 && execute_calls == 1 && state == desired);
        /* Repeating the desired state must not toggle it back. */
        assert(execute_pause_command(state, desired, expected_vtable,
                                     factory, readable, execute));
        assert(factory_calls == 1 && execute_calls == 1 && state == desired);
    }
    return 0;
}
