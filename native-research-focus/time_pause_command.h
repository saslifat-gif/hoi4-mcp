/* Native pause construction boundary, shared with the offline C regression.
 * The engine factory initializes CPauseGame, including its inline reason string.
 * Commands are retained until process exit, under the existing 64-request bound.
 */
#ifndef HOI4_TIME_PAUSE_COMMAND_H
#define HOI4_TIME_PAUSE_COMMAND_H
#include <stdint.h>
#include <stddef.h>
typedef uintptr_t (*TimePauseFactory)(void);
typedef int (*TimePauseReadable)(const void *, size_t);
typedef void (*TimePauseExecute)(void *);
static int execute_pause_command(int before, int desired, uintptr_t expected_vtable,
                                TimePauseFactory factory, TimePauseReadable readable,
                                TimePauseExecute execute) {
    if (before == desired) return 1;
    uintptr_t command = factory();
    if (!readable((const void *)command, 0x50) ||
        *(const uintptr_t *)command != expected_vtable) return 0;
    /* CPauseGame's user-pause flag is a toggle, not the desired final state.
     * The caller checks state before calling and verifies it again afterwards.
     * Leave the factory's string and only-if-unpaused flag untouched.
     */
    *(unsigned char *)(command + 0x48) = 1;
    execute((void *)command);
    return 1;
}
#endif
