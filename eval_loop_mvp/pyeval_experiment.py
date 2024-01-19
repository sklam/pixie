from __future__ import annotations
import dis
import types
import inspect
import operator
from pprint import pprint
from dataclasses import dataclass, field
import typing as tp

from pixie.eval_hook import create_custom_hook


def frame_evaluator(frame_info, co_extra):
    print("frame_evaluator cache on entry", co_extra)
    if "cache" in co_extra:
        co_extra["cache"] += 1
    else:
        co_extra["cache"] = 1
    print("frame_evaluator cache on exit", co_extra)

    # Do not attempt to run `__exit__` functions
    ok = "__exit__" not in frame_info["f_code"].co_name
    print(
        f"Overridden interpreter running: '{frame_info['f_code'].co_name}', "
        f"accepted exec = {ok}"
    )
    if ok:
        func = frame_info["f_func"]
        args = frame_info["localsplus"]
        print("frame_info", frame_info.keys())
        assert frame_info["f_locals"] is None
        co: types.CodeType = func.__code__
        print("co_varnames", co.co_varnames)
        f_locals = dict(zip(co.co_varnames, args))
        f_globals = frame_info["f_globals"]
        f_builtins = frame_info["f_builtins"]
        print("   func", func)
        print("   args", args)
        result = py_eval(func, f_locals, f_globals, f_builtins, args)
        print("result?", result)
        return True, result
    else:
        return False, None


def py_eval(func, f_locals, f_globals, f_builtins, args):
    bytecode = dis.Bytecode(func)
    print(bytecode.dis())

    instlist = list(bytecode)
    evalloop = PyEvalLoop(func, instlist, f_locals, f_globals, f_builtins, args)
    return evalloop.eval_loop()


@dataclass
class Frame:
    func: tp.Callable
    args: tuple
    pc: int
    locals: dict[str, tp.Any]
    globals: dict[str, tp.Any]
    builtins: dict[str, tp.Any]

    def get_global(self, name: str) -> tp.Any:
        try:
            return self.globals[name]
        except KeyError:
            return self.builtins[name]


@dataclass(frozen=True)
class EvalStatus:
    status: str
    value: tp.Any = None

    @classmethod
    def advance(cls) -> EvalStatus:
        return EvalStatus("advance")

    @classmethod
    def ret(cls, value: tp.Any) -> EvalStatus:
        return EvalStatus("done", value)

    @property
    def is_done(self) -> bool:
        return self.status == "done"

    @property
    def is_advance(self) -> bool:
        return self.status == "advance"


@dataclass(frozen=True)
class Stack:
    stk: list = field(default_factory=list)

    def push(self, val: tp.Any) -> None:
        self.stk.append(val)

    def pop(self) -> tp.Any:
        return self.stk.pop()

    def stack_repr(self) -> str:
        return list(map(lambda x: type(x).__name__, self.stk))


_OPMAP = {
    "*": operator.mul,
}


class PyEvalLoop:
    _instlist: list[dis.Instruction]
    _instmap: dict[str, dis.Instruction]

    def __init__(self, func, instlist, locals, globals, builtins, args):
        self._frame = Frame(
            func=func,
            args=tuple(args),
            pc=0,
            locals=locals,
            globals=globals,
            builtins=builtins,
        )
        self._stack = Stack()
        self._instlist = instlist
        self._instmap = {inst.offset: inst for inst in instlist}

    def eval_loop(self):
        while True:
            status = self.eval_next()
            if status.is_done:
                return status.value

    def eval_next(self) -> EvalStatus:
        inst = self.get_next_inst()
        print(
            f"PC {self._frame.pc:3} | Running {inst.opname:20}({inst.argrepr})\n\tStack {self._stack.stack_repr()}"
        )
        fn = getattr(self, f"op_{inst.opname}")
        status: EvalStatus = fn(inst)
        if status.is_advance:
            self.advance_inst()
        return status

    def advance_inst(self):
        f = self._frame
        inst = self.get_next_inst()
        inst1 = self._instlist[self._instlist.index(inst) + 1]
        f.pc = inst1.offset

    def get_next_inst(self):
        return self._instmap[self._frame.pc]

    def op_RESUME(self, inst: dis.Instruction) -> EvalStatus:
        return EvalStatus.advance()

    def op_LOAD_FAST(self, inst: dis.Instruction) -> EvalStatus:
        vname = inst.argval
        val = self._frame.locals[vname]
        self._stack.push(val)
        return EvalStatus.advance()

    def op_STORE_FAST(self, inst: dis.Instruction) -> EvalStatus:
        vname = inst.argval
        val = self._stack.pop()
        self._frame.locals[vname] = val
        return EvalStatus.advance()

    def op_LOAD_CONST(self, inst: dis.Instruction) -> EvalStatus:
        const = inst.argval
        self._stack.push(const)
        return EvalStatus.advance()

    def op_LOAD_GLOBAL(self, inst: dis.Instruction) -> EvalStatus:
        items = tuple(map(lambda x: x.strip(), inst.argrepr.split("+")))
        todos = []
        stk = self._stack
        f = self._frame

        def pushnull():
            stk.push(Null)

        def pushgv():
            return stk.push(f.get_global(gvname))

        if len(items) > 1:
            # normalize push null and gvname
            if items[0] == "NULL":
                # push NULL first
                todos.append(pushnull)
                todos.append(pushgv)
                gvname = items[1]
            else:
                assert items[1] == "NULL"
                todos.append(pushgv)
                todos.append(pushnull)
                gvname = items[0]
        else:
            todos.append(pushgv)

        for do in todos:
            do()

        return EvalStatus.advance()

    def op_PRECALL(self, inst: dis.Instruction) -> EvalStatus:
        return EvalStatus.advance()

    def op_CALL(self, inst: dis.Instruction) -> EvalStatus:
        narg = inst.argval
        args = list(reversed([self._stack.pop() for _ in range(narg)]))
        callable_or_firstarg = self._stack.pop()
        null_or_callable = self._stack.pop()
        if null_or_callable is Null:
            callable = callable_or_firstarg
        else:
            callable = null_or_callable
            args = [callable_or_firstarg, *args]

        # TODO: handle kw_names
        with myhook():
            result = callable(*args)
        self._stack.push(result)
        return EvalStatus.advance()

    def op_RETURN_VALUE(self, inst: dis.Instruction) -> EvalStatus:
        ret = self._stack.pop()
        return EvalStatus.ret(ret)

    def op_POP_TOP(self, inst: dis.Instruction) -> EvalStatus:
        self._stack.pop()
        return EvalStatus.advance()

    def op_BINARY_OP(self, inst: dis.Instruction) -> EvalStatus:
        rhs = self._stack.pop()
        lhs = self._stack.pop()
        fn = _OPMAP[inst.argrepr]
        res = fn(lhs, rhs)
        self._stack.push(res)
        return EvalStatus.advance()

    def op_BUILD_TUPLE(self, inst: dis.Instruction) -> EvalStatus:
        count = inst.argval
        items = list(reversed([self._stack.pop() for _ in range(count)]))
        res = tuple(items)
        self._stack.push(res)
        return EvalStatus.advance()


class Null:
    def __new__(cls):
        raise TypeError("do not instantiate")


# -----------------------------------------------------------------------------


def bar(x):
    print("Ha")


def foo(x, a=11):
    # Test function
    bar(x)
    b = 10 * x, a
    return b



def demo():
    global myhook
    # Generate a frame evaluation hook, called `my_custom_hook`, that will use
    # the above frame_evaluator function to evaluate frames when the hook is
    # enabled.
    myhook, enable, disable, query = create_custom_hook(
        hook_name="my_custom_hook", frame_evaluator=frame_evaluator
    )

    # Run in the standard interpreter.
    query()
    print(foo(1))

    # Execute this region with the replacement frame evaluator.
    print("-" * 80)
    with myhook():
        query()
        print(foo(4), "\n\n")
    print("=" * 80)
    # Run in the standard interpreter.
    query()


if __name__ == "__main__":
    demo()
