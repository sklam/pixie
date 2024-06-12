# arm64 - Apple silicon target
from enum import auto, Enum, IntEnum

from llvmlite import ir

from pixie.targets.common import create_cpu_enum_for_target, FeaturesEnum
from pixie.selectors import Selector
from pixie.mcext import c, langref

cpus = create_cpu_enum_for_target("arm64-unknown-unknown")


class features(FeaturesEnum):
    NONE = 0
    # microarch profile
    v8_4a = 1
    v8_5a = 2
    v8_6a = 3
    # features
    neon = 4 # same as fp_armv8
    fullfp16 = 5
    fp16fml = 6
    sha3 = 7
    i8mm = 8
    bf16 = 9

    # TODO: implement
    feature_max       = auto()  # noqa: E221

    def __str__(self):
        return self.name.replace('_', '-')


class cpu_features(IntEnum):
    NONE = 0
    # microarch profile
    V8_4A = 1
    V8_5A = 2
    V8_6A = 3
    # features
    NEON = 4 # same as fp_armv8
    FULLFP16 = 5
    FP16FML = 6
    SHA3 = 7
    I8MM = 8
    BF16 = 9


class cpu_dispatchable(IntEnum):
    V8_4A = (1 << cpu_features.V8_4A)
    V8_5A = (1 << cpu_features.V8_5A) | V8_4A
    V8_6A = (1 << cpu_features.V8_6A) | V8_5A

    NEON = (1 << cpu_features.NEON)
    FULLFP16 = (1 << cpu_features.FULLFP16)
    FP16FML = (1 << cpu_features.FP16FML)
    SHA3 = (1 << cpu_features.SHA3)
    I8MM = (1 << cpu_features.I8MM)
    BF16 = (1 << cpu_features.BF16)


_cd = cpu_dispatchable

class cpu_family_features(Enum):
    # M1: is +8.4a       +fp-armv8 +fp16fml +fullfp16 +sha3 +ssbs +sb +fptoint
    APPLE_M1 = _cd.V8_4A | _cd.NEON | _cd.FULLFP16 | _cd.FP16FML | _cd.SHA3
    # M2: is +8.4a +8.6a +fp-armv8 +fp16fml +fullfp16 +sha3 +ssbs +sb +fptoint +bti +predres +i8mm +bf16
    APPLE_M2 = _cd.V8_6A | _cd.NEON | _cd.FULLFP16 | _cd.FP16FML | _cd.SHA3 | _cd.I8MM | _cd.BF16


class arm64CPUSelector(Selector):
    def selector_impl(self, builder):
        self._DEBUG = True
        from pprint import pprint
        pprint(self._embedded_data)
        # Check the keys supplied are valid
        def check_keys():
            supplied_variants = set(self._data.keys())
            assert 'baseline' in supplied_variants, supplied_variants
            supplied_variants.remove('baseline')
            memb = cpu_dispatchable.__members__

            for k in supplied_variants:
                assert k in memb, f"{k} not in {memb.keys()}"

        check_keys()

        i32 = langref.types.i32
        i32_ptr = i32.as_pointer()
        i64 = langref.types.i64
        i64_ptr = i64.as_pointer()

        # commpage address
        commpage_addr = ir.Constant(i64, 0x0000000FFFFFC000)
        cpu_family_offset = ir.Constant(i64, 0x80)

        cpu_families = dict(
            UNKNOWN = 0,
            # Reference: https://github.com/apple-oss-distributions/xnu/blob/94d3b452840153a99b38a3a9659680b2a006908e/osfmk/mach/machine.h#L428-L444
            APPLE_M1 = 0x1b588bb3,  # M1 is FIRESTORM_ICESTORM
            # From running sysctl hw.cpufamily on a M2
            # hw.cpufamily: -634136515
            APPLE_M2 = 0xda33d83d,  # M2 is AVALANCHE_BILLZARD
        )
        def gen_cpu_family_probe(module):
            """
            Probe commpage cpu-family
            """
            ftype = ir.FunctionType(i32, ())
            fn = ir.Function(module, ftype,
                             name="_pixie_darwin_arm64_cpu_family_probe")
            fn.linkage = 'internal'
            builder = ir.IRBuilder(fn.append_basic_block('entry'))
            cpu_fam_sel = builder.alloca(i32, name='cpu_fam_sel')
            builder.store(i32(0), cpu_fam_sel)
            commpage_cpu_fam_ptr = builder.inttoptr(
                commpage_addr.add(cpu_family_offset), i32_ptr,
                name="commpage_cpu_fam_ptr",
            )
            cpu_fam = builder.load(commpage_cpu_fam_ptr, name='cpu_fam')
            self.debug_print(builder, "[_pixie_darwin_arm64_cpu_family_probe] commpage value = %llu\n", cpu_fam)

            for i, (name, cpuid) in enumerate(cpu_families.items()):
                matched = builder.icmp_unsigned('==', i32(cpuid), cpu_fam)
                with builder.if_then(matched):
                    builder.store(i32(i), cpu_fam_sel)
                    self.debug_print(builder, f"[_pixie_darwin_arm64_cpu_family_probe] matched {name}\n")

            output = builder.load(cpu_fam_sel, name='output')

            message = f"[_pixie_darwin_arm64_cpu_family_probe] output=%d\n"
            self.debug_print(builder, message, output)

            builder.ret(output)
            return fn


        fn_cpu_family_probe = gen_cpu_family_probe(builder.module)
        cpu_sel = builder.call(fn_cpu_family_probe, ())

        bb_default = builder.append_basic_block()
        swt = builder.switch(cpu_sel, bb_default)
        with builder.goto_block(bb_default):
            self._select(builder, 'baseline')  # or error?
            builder.ret_void()

        for i, name in enumerate(cpu_families):
            if i != 0: # skip unknown
                bb = builder.append_basic_block()
                with builder.goto_block(bb):
                    features = cpu_family_features.__members__[name]
                    self.debug_print(builder, f'[selector] cpu is {name}\n')
                    for featname in parse_features(features.value):
                        if featname in self._embedded_data: # XXX?
                            self.debug_print(builder, f"[selector] feature set {featname}\n")
                            self._select(builder, featname)
                    builder.ret_void()
                swt.add_case(i, bb)

        print(builder.function)


def parse_features(feature_mask: int) -> set[str]:
    return {k for k, mask in cpu_dispatchable.__members__.items()
            if mask & feature_mask}


CPUSelector = arm64CPUSelector



# def codegen_cpu_feat():
