# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import weakref
from typing import TYPE_CHECKING, Any

from marimo._ast.cell import CellId_t, CellImpl
from marimo._config.config import DEFAULT_CONFIG
from marimo._runtime.app.common import RunOutput
from marimo._runtime.context.types import get_context
from marimo._runtime.patches import create_main_module
from marimo._runtime.requests import (
    AppMetadata,
    ExecutionRequest,
    SetUIElementValueRequest,
)
from marimo._runtime.runner import cell_runner

if TYPE_CHECKING:
    from marimo._ast.app import InternalApp


class AppKernelRunner:
    """Runs an app in a kernel context; used for composition."""

    def __init__(self, app: InternalApp) -> None:
        from marimo._runtime.context.kernel_context import (
            KernelRuntimeContext,
            create_kernel_context,
        )
        from marimo._runtime.runner.hooks_post_execution import (
            _reset_matplotlib_context,
        )
        from marimo._runtime.runtime import Kernel

        self.app = app
        self._outputs: dict[str, Any] = {}

        ctx = get_context()
        if not isinstance(ctx, KernelRuntimeContext):
            raise RuntimeError("AppKernelRunner requires a kernel context.")

        def cache_output(
            cell: CellImpl,
            runner: cell_runner.Runner,
            run_result: cell_runner.RunResult,
        ) -> None:
            """Update the app's cached outputs."""
            from marimo._plugins.stateless.flex import vstack

            del runner
            if (
                run_result.output is None
                and run_result.accumulated_output is not None
            ):
                self.outputs[cell.cell_id] = vstack(
                    run_result.accumulated_output
                )
            else:
                self.outputs[cell.cell_id] = run_result.output

        filename = "<unknown>"
        self._kernel = Kernel(
            cell_configs={},
            app_metadata=AppMetadata({}, {}, filename),
            stream=ctx.stream,
            stdout=None,
            stderr=None,
            stdin=None,
            module=create_main_module(filename, None),
            user_config=DEFAULT_CONFIG,
            enqueue_control_request=lambda _: None,
            post_execution_hooks=[cache_output, _reset_matplotlib_context],
        )

        # We push a new runtime context onto the "stack", corresponding to this
        # app. The context is removed when the app object is destroyed.
        self._runtime_context = create_kernel_context(
            kernel=self._kernel,
            app=app,
            stream=ctx.stream,
            stdout=None,
            stderr=None,
            virtual_files_supported=True,
            parent=ctx,
        )
        ctx.add_child(self._runtime_context)
        finalizer = weakref.finalize(
            self, ctx.remove_child, self._runtime_context
        )
        finalizer.atexit = False

    @property
    def outputs(self) -> dict[CellId_t, Any]:
        return self._outputs

    @property
    def globals(self) -> dict[CellId_t, Any]:
        return self._kernel.globals

    async def run(self, cells_to_run: set[CellId_t]) -> RunOutput:
        execution_requests = [
            ExecutionRequest(cell_id=cid, code=cell._cell.code)
            for cid in cells_to_run
            if (cell := self.app.cell_manager.cell_data_at(cid).cell)
            is not None
        ]

        with self._runtime_context.install():
            await self._kernel.run(execution_requests)
        return self.outputs, self._kernel.globals

    async def set_ui_element_value(
        self, request: SetUIElementValueRequest
    ) -> bool:
        with self._runtime_context.install():
            return await self._kernel.set_ui_element_value(request)
