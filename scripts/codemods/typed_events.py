# SPDX-License-Identifier: MIT

from __future__ import annotations

import types
from typing import List, Optional, cast

import libcst as cst
import libcst.matchers as m

from disnake import Event
from disnake._event_data import EVENT_DATA, EventData

from .base import BaseCodemodCommand


def get_param(func: cst.FunctionDef, name: str) -> cst.Param:
    results = m.findall(func.params, m.Param(m.Name(name)))
    assert len(results) == 1
    return cast(cst.Param, results[0])


class EventTypings(BaseCodemodCommand):
    DESCRIPTION: str = "Adds overloads for library events."
    CHECK_MARKER: str = "@_overload_with_events"

    flag_classes: List[str]
    imported_module: types.ModuleType

    def visit_FunctionDef(self, node: cst.FunctionDef) -> Optional[bool]:
        # don't recurse into the body of a function
        return False

    def leave_FunctionDef(self, _: cst.FunctionDef, node: cst.FunctionDef):
        decorators = [
            deco.decorator.value
            for deco in node.decorators
            if not isinstance(deco.decorator, cst.Call)
        ]
        if "_generated" in decorators:
            # remove generated methods
            return cst.RemovalSentinel.REMOVE
        if "_overload_with_events" not in decorators:
            # ignore
            return node

        if node.name.value == "wait_for":
            generator = self.generate_wait_for_overload
        else:
            raise RuntimeError(
                f"unknown method '{node.name.value}' with @_overload_with_events decorator"
            )

        # if we're here, we found a @_overload_with_events decorator
        new_overloads: List[cst.FunctionDef] = []
        for event in Event:
            if not (event_data := EVENT_DATA.get(event)):
                raise RuntimeError(f"{event} is missing an EVENT_DATA definition")
            if event_data.event_only:
                continue
            new_overloads.append(generator(node, event, event_data))

        return cst.FlattenSentinel([*new_overloads, node])

    def create_empty_overload(self, func: cst.FunctionDef) -> cst.FunctionDef:
        return func.with_changes(
            body=cst.IndentedBlock([cst.SimpleStatementLine([cst.Expr(cst.Ellipsis())])]),
            decorators=[
                cst.Decorator(cst.Name("overload")),
                cst.Decorator(cst.Name("_generated")),
            ],
            leading_lines=(),
        )

    def create_literal(self, event: Event) -> cst.BaseExpression:
        return cst.parse_expression(
            f'Literal[Event.{event.name}, "{event.value}"]',
            config=self.module.config_for_parsing,
        )

    def create_args_list(self, event_data: EventData) -> cst.BaseExpression:
        return cst.parse_expression(
            f'[{",".join(event_data.arg_types)}]',
            config=self.module.config_for_parsing,
        )

    def generate_wait_for_overload(
        self, func: cst.FunctionDef, event: Event, event_data: EventData
    ) -> cst.FunctionDef:
        args = event_data.arg_types

        new_overload = self.create_empty_overload(func)

        # set `event` annotation
        new_overload = new_overload.with_deep_changes(
            get_param(new_overload, "event"),
            annotation=cst.Annotation(self.create_literal(event)),
        )

        # set `check` annotation
        callable_annotation = m.findall(
            get_param(new_overload, "check"), m.Subscript(m.Name("Callable"))
        )[0]
        callable_params = m.findall(callable_annotation, m.Ellipsis())[0]
        new_overload = cast(
            cst.FunctionDef,
            new_overload.deep_replace(callable_params, self.create_args_list(event_data)),
        )

        # set return annotation
        if len(args) == 0:
            new_annotation_str = "None"
        elif len(args) == 1:
            new_annotation_str = args[0]
        else:
            new_annotation_str = f'Tuple[{",".join(args)}]'
        new_annotation = cst.parse_expression(
            f"Coroutine[Any, Any, {new_annotation_str}]",
            config=self.module.config_for_parsing,
        )
        new_overload = new_overload.with_changes(returns=cst.Annotation(new_annotation))

        # set `self` annotation as a workaround for overloads in subclasses
        if event_data.self_type:
            new_overload = new_overload.with_deep_changes(
                get_param(new_overload, "self"),
                annotation=cst.Annotation(cst.Name(event_data.self_type)),
            )

        return new_overload
