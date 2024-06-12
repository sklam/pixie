// SO dynamic lookup https://stackoverflow.com/questions/66256300/c-c-code-to-have-different-execution-block-on-m1-and-intel
// Julia reference: https://github.com/JuliaLang/julia/blob/68fe51285f928ca5ca3629ad28ede14f0877b671/src/processor_arm.cpp#L712-L727
// Go reference: https://github.com/golang/sys/pull/114/files
// - https://github.com/apple-oss-distributions/xnu/blob/94d3b452840153a99b38a3a9659680b2a006908e/osfmk/arm/cpu_capabilities.h#L292
// - https://github.com/apple-oss-distributions/xnu/blob/94d3b452840153a99b38a3a9659680b2a006908e/libsyscall/wrappers/__get_cpu_capabilities.s#L34
// Apple reference: https://developer.apple.com/documentation/apple-silicon/addressing-architectural-differences-in-your-macos-code#Fetch-System-and-Hardware-Details-Dynamically
// opencv: https://github.com/opencv/opencv/blob/a03b81316782ae30038b288fd3568993fa1e3538/modules/core/src/system.cpp#L857


#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/sysctl.h>
#include <mach/machine.h>

int main(void) {
    cpu_type_t type;
    size_t size = sizeof(type);
    sysctlbyname("hw.cputype", &type, &size, NULL, 0);

    // Check if the process is emulated on an M1 Mac
    int procTranslated;
    size = sizeof(procTranslated);
    sysctlbyname("sysctl.proc_translated", &procTranslated, &size, NULL, 0);

    if (procTranslated) {
        printf("Running on an M1 Mac under emulation.\n");
    } else {
        // Remove CPU_ARCH_ABI64 or CPU_ARCH_ABI64_32 encoded with the Type
        cpu_type_t typeWithABIInfoRemoved = type & ~CPU_ARCH_MASK;

        if (typeWithABIInfoRemoved == CPU_TYPE_X86) {
            printf("Running on an Intel-based Mac.\n");
        } else if (typeWithABIInfoRemoved == CPU_TYPE_ARM) {
            printf("Running on an Apple Silicon Mac.\n");
        }
    }
    char buffer[128];
    size_t bufferlen = 128;
    sysctlbyname("machdep.cpu.brand_string",&buffer,&bufferlen,NULL,0);

    printf("CPU Brand String: %s\n", buffer);
    return 0;
}