# SPDX-License-Identifier: MIT

import functools

import libcst as cst
from libcst import codemod

from . import overloads_no_missing, typed_events, typed_flags, typed_permissions
from .base import NoMetadataWrapperMixin

CODEMODS = [
    overloads_no_missing.EllipsisOverloads,
    typed_events.EventTypings,
    typed_flags.FlagTypings,
    typed_permissions.PermissionTypings,
]


# translate `codemod.SkipFile` into a graceful return
def wrap_translate_skipfile(func):
    @functools.wraps(func)
    def wrap(self: codemod.Codemod, tree: cst.Module) -> cst.Module:
        try:
            return func(self, tree)
        except codemod.SkipFile:
            return tree

    return wrap


class CombinedCodemod(NoMetadataWrapperMixin, codemod.MagicArgsCodemodCommand):
    DESCRIPTION = "Runs all custom codemods from this repo."

    def get_transforms(self):
        # yield codemods to be run, while monkeypatching `transform_module`
        for codemod_type in CODEMODS:
            yield type(
                f"{codemod_type.__name__}__Wrapped",
                (codemod_type,),
                {"transform_module": wrap_translate_skipfile(codemod_type.transform_module)},
            )
