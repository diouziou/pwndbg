#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Allows describing functions, specifically enumerating arguments which
may be passed in a combination of registers and stack values.
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import gdb
from capstone import CS_GRP_CALL
from capstone import CS_GRP_INT

import pwndbg.abi
import pwndbg.arch
import pwndbg.constants
import pwndbg.disasm
import pwndbg.funcparser
import pwndbg.functions
import pwndbg.ida
import pwndbg.memory
import pwndbg.regs
import pwndbg.symbol
import pwndbg.typeinfo

ida_replacements = {
    '__int64': 'signed long long int',
    '__int32': 'signed int',
    '__int16': 'signed short',
    '__int8': 'signed char',
    '__uint64': 'unsigned long long int',
    '__uint32': 'unsigned int',
    '__uint16': 'unsigned short',
    '__uint8': 'unsigned char',
    '_BOOL_1': 'unsigned char',
    '_BOOL_2': 'unsigned short',
    '_BOOL_4': 'unsigned int',
    '_BYTE': 'unsigned char',
    '_WORD': 'unsigned short',
    '_DWORD': 'unsigned int',
    '_QWORD': 'unsigned long long',
    '__pure': '',
    '__hidden': '',
    '__return_ptr': '',
    '__struct_ptr': '',
    '__array_ptr': '',
    '__fastcall': '',
    '__cdecl': '',
    '__thiscall': '',
    '__userpurge': '',
}

def get_syscall_name(instruction):
    if not CS_GRP_INT in instruction.groups:
        return None

    try:
        abi     = pwndbg.abi.ABI.syscall()
        syscall = getattr(pwndbg.regs, abi.syscall_register)
        name    = pwndbg.constants.syscall(syscall)

        return 'SYS_' + name
    except:
        return None

def get(instruction):
    """
    Returns an array containing the arguments to the current function,
    if $pc is a 'call' or 'bl' type instruction.

    Otherwise, returns None.
    """
    n_args_default = 4

    if instruction.address != pwndbg.regs.pc:
        return []

    abi = pwndbg.abi.ABI.default()

    if CS_GRP_CALL in instruction.groups:
        # Not sure of any OS which allows multiple operands on
        # a call instruction.
        assert len(instruction.operands) == 1

        target = instruction.operands[0].int

        if not target:
            return []

        name = pwndbg.symbol.get(target)
        if not name:
            return []
    elif CS_GRP_INT in instruction.groups:
        # Get the syscall number and name
        abi = pwndbg.abi.ABI.syscall()

        # print(abi)
        # print(abi.register_arguments)

        target  = None
        syscall = getattr(pwndbg.regs, abi.syscall_register)
        name    = pwndbg.constants.syscall(syscall)
    else:
        return []

    result = []
    args = []
    name = name or ''

    sym   = gdb.lookup_symbol(name)
    name  = name.strip().lstrip('_')    # _malloc
    name  = name.replace('isoc99_', '') # __isoc99_sscanf
    name  = name.replace('@plt', '')    # getpwiod@plt
    name  = name.replace('_chk', '')    # __printf_chk
    func = pwndbg.functions.functions.get(name, None)

    # Try to extract the data from GDB.
    # Note that this is currently broken, pending acceptance of
    # my patch: https://sourceware.org/ml/gdb-patches/2015-06/msg00268.html
    if sym and sym[0]:
        try:
            n_args_default = len(sym[0].type.fields())
        except TypeError:
            pass


    # Try to grab the data out of IDA
    if not func and target:
        typename = pwndbg.ida.GetType(target)

        if typename:
            typename += ';'

            # GetType() does not include the name.
            typename = typename.replace('(', ' function_name(', 1)

            for k,v in ida_replacements.items():
                typename = typename.replace(k,v)

            func     = pwndbg.funcparser.ExtractFuncDeclFromSource(typename + ';')

    if func:
        args = func.args
    else:
        args = [pwndbg.functions.Argument('int',0,argname(i, abi)) for i in range(n_args_default)]

    for i,arg in enumerate(args):
        result.append((arg, argument(i, abi)))

    return result


def argname(n, abi=None):
    abi  = abi or pwndbg.abi.ABI.default()
    regs = abi.register_arguments

    if n < len(regs):
        return regs[n]

    return 'arg[%i]' % n

def argument(n, abi=None):
    """
    Returns the nth argument, as if $pc were a 'call' or 'bl' type
    instruction.
    """
    abi  = abi or pwndbg.abi.ABI.default()
    regs = abi.register_arguments

    if n < len(regs):
        return getattr(pwndbg.regs, regs[n])

    n -= len(regs)

    sp = pwndbg.regs.sp + (n * pwndbg.arch.ptrsize)

    return int(pwndbg.memory.poi(pwndbg.typeinfo.ppvoid, sp))
