from ctypes import c_uint64, c_uint32
import math


# https://github.com/apple-oss-distributions/xnu/blob/94d3b452840153a99b38a3a9659680b2a006908e/osfmk/arm/cpu_capabilities.h#L56-L101

# Bit definitions for CPU capabilities

bits_cpu_capabilities = dict(

    kHasFeatFP16=                    0x00000008,      # ARM v8.2 NEON FP16 supported
    kCache32=                        0x00000010,      # cache line size is 32 bytes
    kCache64=                        0x00000020,      # cache line size is 64 bytes
    kCache128=                       0x00000040,      # cache line size is 128 bytes
    kFastThreadLocalStorage=         0x00000080,      # TLS ptr is kept in a user-mode-readable register
    kHasAdvSIMD=                     0x00000100,      # Advanced SIMD is supported
    kHasAdvSIMD_HPFPCvt=             0x00000200,      # Advanced SIMD half-precision
    kHasVfp=                         0x00000400,      # VFP is supported
    kHasUCNormalMemory=              0x00000800,      # Uncacheable normal memory type supported
    kHasEvent=                       0x00001000,      # WFE/SVE and period event wakeup
    kHasFMA=                         0x00002000,      # Fused multiply add is supported
    kHasFeatFHM=                     0x00004000,      # Optional ARMv8.2 FMLAL/FMLSL instructions (required in ARMv8.4)
    kUP=                             0x00008000,      # set if (kNumCPUs == 1)
    kNumCPUs=                        0x00FF0000,      # number of CPUs (see _NumCPUs() below)
    kHasARMv8Crypto=                 0x01000000,      # Optional ARMv8 Crypto extensions
    kHasFeatLSE=                     0x02000000,      # ARMv8.1 Atomic instructions supported
    kHasARMv8Crc32=                  0x04000000,      # Optional ARMv8 crc32 instructions (required in ARMv8.1)
    kHasFeatSHA512=                  0x80000000,      # Optional ARMv8.2 SHA512 instructions
# Extending into 64-bits from here:
    kHasFeatSHA3=            0x0000000100000000,      # Optional ARMv8.2 SHA3 instructions
    kHasFeatFCMA=            0x0000000200000000,      # ARMv8.3 complex number instructions
    kHasFEATFlagM=           0x0000010000000000,
    kHasFEATFlagM2=          0x0000020000000000,
    kHasFeatDotProd=         0x0000040000000000,
    kHasFeatRDM=             0x0000080000000000,
    kHasFeatSPECRES=         0x0000100000000000,
    kHasFeatSB=              0x0000200000000000,
    kHasFeatFRINTTS=         0x0000400000000000,
    kHasArmv8GPI=            0x0000800000000000,
    kHasFeatLRCPC=           0x0001000000000000,
    kHasFeatLRCPC2=          0x0002000000000000,
    kHasFeatJSCVT=           0x0004000000000000,
    kHasFeatPAuth=           0x0008000000000000,
    kHasFeatDPB=             0x0010000000000000,
    kHasFeatDPB2=            0x0020000000000000,
    kHasFeatLSE2=            0x0040000000000000,
    kHasFeatCSV2=            0x0080000000000000,
    kHasFeatCSV3=            0x0100000000000000,
    kHasFeatDIT=             0x0200000000000000,
    kHasFP_SyncExceptions=   0x0400000000000000,
)
# https://github.com/apple-oss-distributions/xnu/blob/94d3b452840153a99b38a3a9659680b2a006908e/osfmk/arm/cpu_capabilities.h#L162
commpage_addr = 0x0000000FFFFFC000

# https://github.com/apple-oss-distributions/xnu/blob/94d3b452840153a99b38a3a9659680b2a006908e/osfmk/arm/cpu_capabilities.h#L292
cpu_capabilities_offset = 0x010

def get_rightmost_set_bit(n):
    return int(math.log2(n & ~(n - 1)))

cpu_feats = c_uint64.from_address(commpage_addr + cpu_capabilities_offset).value
print(bin(cpu_feats))
for name, mask in bits_cpu_capabilities.items():
    bitvector = mask & cpu_feats
    has = bool(bitvector)
    ramt = get_rightmost_set_bit(mask)
    num = bitvector >> ramt
    print(f"{name:30} : {has:1}   {hex(num)} {(num)}")


# LLVM
# CPU model info: https://github.com/llvm/llvm-project/blob/15a699f98ebc9d7d2dad31ef4b8bd31d1c371e38/llvm/include/llvm/TargetParser/AArch64TargetParser.h#L458C4-L465C56
# TableGen: https://github.com/llvm/llvm-project/blob/00fa3fbfb846756a902527cdd793f1ad7ad9369b/llvm/lib/Target/AArch64/AArch64Features.td


# {"apple-m1", ARMV8_4A,
#  AArch64::ExtensionBitset({AArch64::AEK_AES, AArch64::AEK_SHA2,
#                            AArch64::AEK_SHA3, AArch64::AEK_FP16,
#                            AArch64::AEK_FP16FML})},
# {"apple-m2", ARMV8_6A,
#  AArch64::ExtensionBitset({AArch64::AEK_AES, AArch64::AEK_SHA2,
#                            AArch64::AEK_SHA3, AArch64::AEK_FP16,
#                            AArch64::AEK_FP16FML})},
# AEK_AES -> aes
# AEK_SHA2 -> sha2
# AEK_SHA3 -> sha3
# AEK_FP16 -> fullfp16
# AEK_FP16FML -> fp16fml
#

# Julia: https://github.com/JuliaLang/julia/blob/68fe51285f928ca5ca3629ad28ede14f0877b671/src/processor_arm.cpp#L358-L359
#
# constexpr auto apple_m1 = armv8_5a_crypto | get_feature_masks(dotprod,fp16fml, fullfp16, sha3);
# constexpr auto apple_m2 = armv8_5a_crypto | get_feature_masks(dotprod,fp16fml, fullfp16, sha3, i8mm, bf16);
#
# Note1: it mistaken M1 as ARM8.5a. It is 8.4a. See https://github.com/llvm/llvm-project/commit/39f09e8dcd9ceff5c5030ede6393155782b7cdad
# Note2: It mistaken M2 as ARM8.5a. It is 8.6a instead. See https://github.com/llvm/llvm-project/commit/dad73bcd802c35bc877d0ec1ceef3722bafb0f33

# See following for feature of 8.4 and 8.5
# https://github.com/llvm/llvm-project/blob/ca33796d54ce6d2c711032b269caf32851c5915a/clang/lib/Basic/Targets/AArch64.cpp#L78-L90
#
#
# https://github.com/llvm/llvm-project/blob/31440738bd6b1345ea978914fe01d2e19f4aa373/llvm/lib/Target/AArch64/AArch64Processors.td#L743-L752#

# For simplicity.
# M1: is +8.4a       +fp-armv8 +fp16fml +fullfp16 +sha3 +ssbs +sb +fptoint
# M2: is +8.4a +8.6a +fp-armv8 +fp16fml +fullfp16 +sha3 +ssbs +sb +fptoint +bti +predres +i8mm +bf16

print("LLVM mappables")
cpu_feat_to_llvm = {
    "kHasAdvSIMD": "neon",
    "kHasFeatFP16": "fullfp16",
    "kHasFeatDotProd": 'dotprod',
    "kHasFeatFRINTTS": "fptoint",

    # HasAlternativeNZCV: "altnzcv"
    # HasSSBS : "ssbs",
    "FEAT_SB": "sb",
    "FEAT_BTI": "bti",
    "FEAT_SPECRES": "predres",
}

# CPU FAMILY
# https://github.com/apple-oss-distributions/xnu/blob/94d3b452840153a99b38a3a9659680b2a006908e/osfmk/arm/cpu_capabilities.h#L332
cpu_family_offset = 0x80
cpu_family = c_uint32.from_address(commpage_addr + cpu_family_offset).value
print("cpu family", hex(cpu_family))


CPUFAMILY_UNKNOWN =                0,
# https://github.com/apple-oss-distributions/xnu/blob/94d3b452840153a99b38a3a9659680b2a006908e/osfmk/mach/machine.h#L428-L444
bits_cpu_families = dict(

    CPUFAMILY_ARM_9=                  0xe73283ae,
    CPUFAMILY_ARM_11=                 0x8ff620d8,
    CPUFAMILY_ARM_XSCALE=             0x53b005f5,
    CPUFAMILY_ARM_12=                 0xbd1b0ae9,
    CPUFAMILY_ARM_13=                 0x0cc90e64,
    CPUFAMILY_ARM_14=                 0x96077ef1,
    CPUFAMILY_ARM_15=                 0xa8511bca,
    CPUFAMILY_ARM_SWIFT=              0x1e2d6381,
    CPUFAMILY_ARM_CYCLONE=            0x37a09642,
    CPUFAMILY_ARM_TYPHOON=            0x2c91a47e,
    CPUFAMILY_ARM_TWISTER=            0x92fb37c8,
    CPUFAMILY_ARM_HURRICANE=          0x67ceee93,
    CPUFAMILY_ARM_MONSOON_MISTRAL=    0xe81e7ef6,
    CPUFAMILY_ARM_VORTEX_TEMPEST=     0x07d34b9f,
    CPUFAMILY_ARM_LIGHTNING_THUNDER=  0x462504d2,
    CPUFAMILY_ARM_FIRESTORM_ICESTORM= 0x1b588bb3,  # M1
    # From running sysctl hw.cpufamily on a M2
    # hw.cpufamily: -634136515
    CPUFAMILY_ARM_AVALANCHE_BILLZARD= 0xda33d83d,  # M2

)

for name, mask in bits_cpu_families.items():
    bitvector = mask & cpu_family
    if bitvector == mask:
        print(name)

# https://github.com/apple-oss-distributions/xnu/blob/94d3b452840153a99b38a3a9659680b2a006908e/osfmk/arm/cpuid.c#L123-L208



# OTHER CAPABILTIES without commpage.
# Must go through sysctlbyname()
# See Apple doc: https://developer.apple.com/documentation/kernel/1387446-sysctlbyname/determining_instruction_set_characteristics
# See LLVM code: https://github.com/llvm/llvm-project/blob/main/compiler-rt/lib/builtins/cpu_model/aarch64/fmv/apple.inc
# FEAT_FHM -> fp16fml
# test_cpu_capability("BF16", 0, false, "hw.optional.arm.FEAT_BF16", try_bf16);
# test_cpu_capability("I8MM", 0, false, "hw.optional.arm.FEAT_I8MM", try_i8mm);