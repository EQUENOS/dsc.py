# SPDX-License-Identifier: MIT

import itertools
from typing import Optional

import libcst as cst
import libcst.codemod.visitors as codevisitors
import libcst.matchers as m
from libcst import codemod

from disnake import Permissions

ALL_PERMISSIONS = sorted(Permissions.VALID_FLAGS.keys())

PERMISSION_MATCHERS = m.OneOf(*map(m.Name, ALL_PERMISSIONS))


def get_perm_kwargs(annotation: cst.Annotation):
    return [
        cst.Param(
            cst.Name(perm),
            annotation,
            default=cst.Ellipsis(),
        )
        for perm in ALL_PERMISSIONS
    ]


def remove_existing_permissions(params: cst.Parameters, *, is_overload: bool) -> cst.Parameters:
    """Remove all of the existing permissions from the kwargs of the provided cst.Parameters."""
    for param in params.params:
        if m.matches(param, PERMISSION_MATCHERS):
            raise RuntimeError(
                f"an existing permission '{param.name.value}' is defined as a "
                "non-keyword argument in a permission overloaded method."
            )

    # unlike params, these may contain generated objects
    # we only have to do this for overloads, as we only change overloads directly
    def is_not_permission(p: cst.Param) -> bool:
        return not m.matches(p.name, PERMISSION_MATCHERS)

    # n.b. this has a small implementation detail that if the first permission in ALL_PERMISSIONS
    # changed or was renamed, then this *may not* remove all permissions from the overloads.
    # this is only true when is_overload is true, but it is unlikely the first permission will change much
    # as such, this is fine for our usecase, IMO.
    if is_overload:
        filter_func = itertools.takewhile
    else:
        filter_func = filter
    existing_kwonly_params = list(
        filter_func(
            is_not_permission,
            params.kwonly_params,
        )
    )

    star_arg = params.star_arg if existing_kwonly_params else cst.MaybeSentinel.DEFAULT
    return params.with_changes(
        kwonly_params=existing_kwonly_params,
        star_arg=star_arg,
    )


class PermissionTypings(codemod.VisitorBasedCodemodCommand):
    DESCRIPTION: str = "Adds overloads for all permissions."

    def transform_module(self, tree: cst.Module) -> cst.Module:
        if "@_overload_with_permissions" not in tree.code:
            raise codemod.SkipFile(
                "this module does not contain the required decorator: `@_overload_with_permissions`."
            )
        return super().transform_module(tree)

    def leave_ClassDef(self, _: cst.ClassDef, node: cst.ClassDef):
        # this method manages where PermissionOverwrite defines the typed augmented permissions.
        # in order to type these properly, we destroy that node and recreate it with the proper permissions.
        if not m.matches(node.name, m.Name("PermissionOverwrite")):
            return node

        # we're in the defintion of PermissionOverwrite
        body = node.body
        for b in body.children:
            if m.matches(b, m.If(test=m.Name("TYPE_CHECKING"))):
                break
        else:
            raise RuntimeError("could not find TYPE_CHECKING block in PermissionOverwrite.")

        og_type_check: cst.If = b  # type: ignore

        body = [
            cst.SimpleStatementLine(
                [
                    cst.AnnAssign(
                        cst.Name(perm),
                        cst.Annotation(
                            cst.Subscript(
                                cst.Name("Optional"),
                                [cst.SubscriptElement(cst.Index(cst.Name("bool")))],
                            )
                        ),
                    )
                ]
            )
            for perm in ALL_PERMISSIONS
        ]

        new_type_check = og_type_check.with_deep_changes(og_type_check.body, body=body)

        return node.deep_replace(og_type_check, new_type_check)

    def visit_FunctionDef(self, node: cst.FunctionDef) -> Optional[bool]:
        # don't recurse into the body of a function
        return False

    def leave_FunctionDef(self, _: cst.FunctionDef, node: cst.FunctionDef):
        # we don't care about the original node
        has_overload_deco = False
        is_overload = False
        previously_generated = False
        for deco in node.decorators:
            if isinstance(deco.decorator, cst.Call):
                continue
            name = deco.decorator.value
            if name == "_overload_with_permissions":
                has_overload_deco = True
            elif name == "overload":
                is_overload = True
            elif name == "_generated":
                previously_generated = True

        if previously_generated:
            return cst.RemovalSentinel.REMOVE

        if not has_overload_deco:
            return node

        if not node.params.star_kwarg and not is_overload:
            raise RuntimeError(
                'a function cannot be decorated with "_overload_with_permissions" and not take any kwargs unless it is an overload.'
            )
        # always true if this isn't an overload
        if node.params.star_kwarg:
            # use the existing annotation if one exists
            annotation = node.params.star_kwarg.annotation
            if annotation is None:
                raise RuntimeError(
                    f"parameter {node.params.star_kwarg.name.value} must be annotated."
                )
        # only possible in the case of an overload
        else:
            # use the first permission annotation if it exists, otherwise default to `bool`
            # make a matcher instance of all valid permission names
            for kw_param in node.params.kwonly_params:
                if kw_param.annotation and m.matches(kw_param.name, PERMISSION_MATCHERS):
                    annotation = kw_param.annotation
                    break
            else:
                annotation = cst.Annotation(cst.Name("bool"))

        # get a Params with all of the new params that we should have
        params = remove_existing_permissions(node.params, is_overload=is_overload)
        params = params.with_changes(star_kwarg=None)
        empty_overload_params = params.deep_clone()

        # add the permissions to the kw_only params
        kwonly_params = list(params.kwonly_params)
        kwonly_params.extend(get_perm_kwargs(annotation))
        params = params.with_changes(kwonly_params=kwonly_params)

        if is_overload:
            node = node.with_changes(params=params)
            return node

        # make an overload before permissions
        empty_overload = node.deep_clone().with_changes(params=empty_overload_params)
        empty_overload = empty_overload.with_changes(
            body=cst.IndentedBlock([cst.SimpleStatementLine([cst.Expr(cst.Ellipsis())])]),
            decorators=[
                cst.Decorator(cst.Name("overload")),
                cst.Decorator(cst.Name("_generated")),
            ],
        )
        # if the decorated method is an overload we make an in-place change and don't add overloads

        overload = empty_overload.deep_clone().with_changes(params=params)

        codevisitors.AddImportsVisitor.add_needed_import(self.context, "typing", "overload")
        codevisitors.AddImportsVisitor.add_needed_import(
            self.context, "disnake.utils", "_generated"
        )

        return cst.FlattenSentinel([overload, empty_overload, node])
