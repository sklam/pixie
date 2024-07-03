import importlib
import subprocess
import inspect
import sys
import re
import textwrap
from enum import Enum, IntEnum
from functools import cached_property
from llvmlite import binding as llvm


class CPUEnum(Enum):

    def __str__(self):
        return f'{self.name}'.replace('_', '-')


class FeaturesEnum(IntEnum):

    def as_feature_str(self):
        # implement this to deal with things like feature sse4.2 not being a
        # valid enum field, it allows a mapping between a field "sse42" and
        # the feature string "sse4.2".
        raise NotImplementedError

    def __str__(self):
        return f'{self.name}'


def create_cpu_enum_for_target(triple_str):
    # TODO: in LLVM 17 this can be queried directly instead of having to scrape
    # strings, adjust once move to LLVM 17+ is made.

    def get_target(triple_str):
        from llvmlite import binding as llvm
        llvm.initialize()
        llvm.initialize_all_targets()
        # this writes to stderr
        llvm.Target.from_triple(triple_str).create_target_machine(cpu="help")

    src = ''.join((textwrap.dedent(inspect.getsource(get_target)),
                   f"\nget_target('{triple_str}')"))
    cmd = (sys.executable, "-c", src)
    result = subprocess.run(cmd, capture_output=True, encoding="utf-8",
                            check=True)
    target_info_str = result.stderr

    def parse_target_info_str(data):
        # fetch the CPUs, the list is broken by strings:
        "Available CPUs for this target:"
        "Available features for this target:"
        pattern = (r"Available CPUs for this target:(.*)Available features for "
                   "this target:")
        matched = re.match(pattern, data, flags=re.S)
        all_cpus = matched.groups()[0]
        cpu_matcher = re.compile("(.*)- Select the.*")
        cpus = []
        for line in all_cpus.splitlines():
            if cpu_line := line.strip():
                cpus.append(cpu_matcher.match(cpu_line).groups()[0].strip())
        return cpus

    all_cpus = parse_target_info_str(target_info_str)

    def fix_dash(x):
        # Should this really be here?
        return x.replace('-', '_')

    return CPUEnum('cpus', list(map(fix_dash, all_cpus)))


def display_cpu_names():
    triple = llvm.get_process_triple()
    print(f"Valid CPU names based on the current process LLVM triple: {triple}")
    for x in create_cpu_enum_for_target(triple):
        print(f" - {x}")


class Features():

    def __init__(self, features):
        if not isinstance(features, tuple):
            self.features = (features,)
        else:
            self.features = features

    def _host_cpu_features(self):
        return llvm.get_host_cpu_features()

    @cached_property
    def as_feature_flags(self):
        # get host features
        known_features = self._host_cpu_features()
        # set all to False
        for k in known_features.keys():
            known_features[k] = False
        # set these features to True
        for x in self.features:
            known_features[str(x)] = True
        return known_features.flatten()

    @cached_property
    def as_selected_feature_flags(self):
        # get host features
        known_features = self._host_cpu_features()
        # set all to False
        for k in known_features.keys():
            known_features[k] = False
        # set these features to True
        for x in self.features:
            known_features[x.as_feature_str()] = True
        ret = ','.join(f'+{k}' for k, v in sorted(known_features.items()) if v)
        return ret

    def __str__(self):
        return self.as_selected_feature_flags

    def __repr__(self):
        return str(self)


class CPUDescription():
    def __init__(self, cpu, features):
        assert isinstance(cpu, CPUEnum)
        assert isinstance(features, tuple)
        for f in features:
            assert isinstance(f, FeaturesEnum)
        self.cpu = cpu
        self.features = features

    def __str__(self):
        return f"CPUDescription<{self.cpu}, {self.features}>"

    def __hash__(self):
        return hash((self.cpu, *self.features))

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return False
        if self.cpu != other.cpu:
            return False
        if self.features != other.features:
            return False
        return True


class TargetDescription():
    # this normalizes the target. It's also where to edit to start to support
    # cross compilation, key a target off the baseline_cpu.
    def __init__(self, target_triple, baseline_cpu, baseline_features,
                 targets_features):

        self._validate_target(target_triple, baseline_cpu, baseline_features,
                              targets_features)

    def _canonicalize_cpu(self, cpu, kwarg):
        msg = (f"Target '{self.target_triple.Arch}' has no CPU named "
               f"'{cpu}' (offending argument supplied to "
               f"{kwarg})")
        if isinstance(cpu, str):
            # check predefined target first
            if (ret := getattr(self.arch.predefined, cpu, None)) is not None:
                return ret.cpu
            # check check specific cpus
            if not hasattr(self.arch.cpus, cpu):
                raise ValueError(msg)
            return getattr(self.arch.cpus, cpu)
        elif isinstance(cpu, CPUEnum):
            # check the cpu instance belongs to the target class, prevent
            # things like using an x86 CPU name against an aarch64 target.
            if cpu not in self.arch.cpus:
                raise ValueError(msg)
            return cpu
        else:
            raise TypeError("Unknown type given to internal check.")

    def _canonicalize_feature(self, feat, kwarg):
        msg = (f"Feature '{feat}' is not a known feature for "
               f"target '{self.target_triple.Arch}' (offending argument "
               f"supplied to {kwarg})")
        ret = None
        if isinstance(feat, str):
            # check predefined target first
            if hasattr(self.arch.predefined, feat):
                ret = getattr(self.arch.predefined, feat).features
            else:
                resolved_feat = getattr(self.arch.features, feat, None)
                if resolved_feat is None:
                    raise ValueError(msg)
                ret = resolved_feat
        elif isinstance(feat, FeaturesEnum):
            # check the feature instance belongs to the target class, prevent
            # things like using an x86 feature being used against an aarch64
            # target.
            if feat not in self.arch.features:
                raise ValueError(msg)
            ret = feat
        else:
            raise TypeError("Unknown type given to internal check.")
        return ret

    def _canonicalize_features(self, features, kwarg):
        # if features is a single thing, canonicalize and return as a tuple
        # if features is a tuple, walk it and canonicalize, return as a tuple
        if isinstance(features, tuple):
            tmp = []
            for f in features:
                tmp.append(self._canonicalize_feature(f, kwarg))
            ret = tuple(tmp)
        elif isinstance(features, (str, FeaturesEnum)):
            # check predefined target first
            ret = None
            if isinstance(features, str):
                if hasattr(self.arch.predefined, features):
                    ret = getattr(self.arch.predefined, features).features
            if ret is None:
                ret = (self._canonicalize_feature(features, kwarg),)
        else:
            msg = (f"{kwarg} should be a string, FeatureEnum, or a tuple "
                   "comprising any combination of strings and FeatureEnum")
            raise TypeError(msg)
        assert isinstance(ret, tuple)
        return ret

    def _get_targets_features(self, targets_features, baseline_cpu):
        # targets_features can be
        # a string
        # a tuple of strings,
        # a tuple of 2-tuple of strings
        # it will be converted into a tuple of 2-tuple of (cpu, features)
        ret = None
        if isinstance(targets_features, (str, FeaturesEnum)):
            if targets_features == "":
                ret = ()
            else:
                feature = self._canonicalize_feature(targets_features,
                                                     "targets_features")
                features = (feature,)
                ret = (CPUDescription(baseline_cpu, features),)
        elif isinstance(targets_features, tuple):
            tmp_features = []
            for feature in targets_features:
                msg = ("Unknown cpu/feature representation found "
                       "in kwarg targets_features: "
                       f"{type(feature)}:{feature}")
                if isinstance(feature, tuple):
                    if len(feature) == 2:
                        # This is a pair of (cpu, features)
                        target_cpu, target_features = feature
                        tcpu = self._canonicalize_cpu(target_cpu,
                                                      "targets_features")
                        tfeatures = self._canonicalize_features(
                            target_features, "targets_features")
                        cpu_feat_pair = CPUDescription(tcpu, tfeatures)
                        tmp_features.append(cpu_feat_pair)
                    elif len(feature) == 1:
                        # This is singleton (features)
                        feat = self._canonicalize_feature(feature,
                                                          "targets_features")
                        tmp_features.append(CPUDescription(baseline_cpu, feat))
                    elif isinstance(feature, CPUDescription):
                        # This is an already resolved CPUDescription
                        tmp_features.append(feature)
                    else:
                        raise TypeError(msg)
                elif isinstance(feature, (str, FeaturesEnum)):
                    feat = None
                    if isinstance(feature, str):
                        if hasattr(self.arch.predefined, feature):
                            feat = getattr(self.arch.predefined,
                                           feature).features
                            tmp_features.append(CPUDescription(baseline_cpu,
                                                               feat))
                    if feat is None:
                        feat = self._canonicalize_feature(feature,
                                                          "targets_features")
                        tmp_features.append(CPUDescription(baseline_cpu,
                                                           (feat,)))
                elif isinstance(feature, CPUDescription):
                    tmp_features.append(feature)
                else:
                    raise TypeError(msg)
            ret = tuple(tmp_features)
        else:
            msg = ("Unknown cpu/feature representation found in kwarg "
                   "targets_features (should be a tuple or a string).")
            raise TypeError(msg)
        assert isinstance(ret, tuple), ret
        return ret

    def _validate_target(self, target_triple, baseline_cpu, baseline_features,
                         targets_features):
        self.target_triple = _get_triple_parts(target_triple)
        arch_mod = f"pixie.targets.{self.target_triple.Arch}"
        self.arch = importlib.import_module(arch_mod)

        # check baseline cpu
        canon_baseline_cpu = self._canonicalize_cpu(baseline_cpu,
                                                    "baseline_cpu")
        canon_baseline_features =\
            self._canonicalize_features(baseline_features, "baseline_features")
        self.baseline_target = CPUDescription(canon_baseline_cpu,
                                              canon_baseline_features)

        self.additional_targets =\
            self._get_targets_features(targets_features,
                                       self.baseline_target.cpu)

    def __str__(self):
        buf = []
        buf.append("Target Description:")
        buf.append(f"arch: {self.target_triple.Arch}")
        buf.append(f"arch class: {self.arch}")
        buf.append(f"baseline CPU: {self.baseline_target.cpu}")
        baseline_features = [str(x) for x in self.baseline_target.features]
        buf.append(f"baseline features: {baseline_features}")
        buf.append("Additional targets:")
        if self.additional_targets:
            for tf in self.additional_targets:
                features = [str(x) for x in tf.features]
                buf.append(f" - {tf.cpu} | {features}")
        else:
            buf.append(" - None")
        return "\n".join(buf)


def get_default_configuration(triple=None):
    """Gets the default configuration for a triple, if not supplied the
       current process triple will be used."""
    if triple is None:
        _triple = llvm.get_process_triple()
    else:
        _triple = triple

    target_triple = _get_triple_parts(_triple)
    arch_mod_name = f"pixie.targets.{target_triple.Arch}"
    arch_mod = importlib.import_module(arch_mod_name)
    return arch_mod.default_configuration


def _get_triple_parts(triple_str):
    parts = llvm.get_triple_parts(triple_str)
    if parts.Arch == 'aarch64' and  parts.Vendor == 'apple':
       return parts._replace(Arch='arm64')
    return parts
