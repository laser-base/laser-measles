"""ResultsWriter component — opt-in JSON results dump at end of run.

Adding ``ResultsWriter`` to ``model.components`` produces the canonical
JSON summary file at end of run. The component owns both the dict-
building logic and the file write, so nothing on the model class needs
to know about results output. Calibration loops and other contexts
that don't want a per-run JSON file on disk simply omit this component.
"""

import json
from pathlib import Path

import numpy as np
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from laser.measles.base import BaseComponent
from laser.measles.base import BaseLaserModel


class ResultsWriterParams(BaseModel):
    """Parameters for ``ResultsWriter``.

    Attributes:
        path: Destination file. Defaults to ``"results.json"`` in cwd.
    """

    model_config = ConfigDict(extra="forbid")

    path: str = Field(
        default="results.json",
        description="Destination file for the JSON results dump.",
    )


class ResultsWriter(BaseComponent):
    """Write standard JSON results at end of run.

    Requires a ``StateTracker`` somewhere in ``model.components`` —
    that's where the per-tick state arrays come from.

    Schema (top-level keys):
        model_type:               class name of the model (e.g. "ABMModel")
        num_ticks:                int
        num_groups:               int (group count from the tracker; 1 if global)
        group_ids:                list[str] (matches tracker.group_ids; may be
                                  scenario row IDs at leaf aggregation, or
                                  higher-level keys like "cluster_1" when
                                  ``aggregation_level`` rolls up)
        group_aggregation_level:  int (the tracker's aggregation_level: -1 means
                                  global, 0+ means grouped at that hierarchy
                                  depth — consumers branch on this to know
                                  whether the _per_group arrays are at patch
                                  granularity or rolled up)
        states:                   list[str] (e.g. ["S","E","I","R"])
        summary:
            peak_infectious_global:     int
            peak_tick:                  int (tick index of global peak;
                                        consumers convert to calendar time
                                        using the model's tick→day mapping)
            attack_rate_global:         float
            final_state_global:         dict[str, int]
            attack_rate_per_group:      list[float] | None
            peak_infectious_per_group:  list[int]   | None
            final_state_per_group:      dict[str, list[int]] | None

    Example::

        from laser.measles.components import ResultsWriter, ResultsWriterParams
        from laser.measles.components import create_component

        model.components = [
            ...
            StateTracker,                         # collects time-series
            ResultsWriter,                        # writes results.json at end
            # or with a custom path:
            create_component(
                ResultsWriter,
                params=ResultsWriterParams(path="run_42.json"),
            ),
        ]
    """

    def __init__(self, model: BaseLaserModel, params: ResultsWriterParams | None = None) -> None:
        super().__init__(model)
        self.params = params or ResultsWriterParams()

    def __call__(self, model: BaseLaserModel, tick: int) -> None:
        # No per-tick work; the dump happens in finalize().
        pass

    def finalize(self, model: BaseLaserModel) -> None:
        """Called by BaseLaserModel.run() after the tick loop completes."""
        out = self._build(model)
        with Path(self.params.path).open("w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o))

    def _build(self, model: BaseLaserModel) -> dict:
        """Construct the results dict from the model's StateTracker.

        Internal helper for :meth:`finalize`. Private by convention —
        external callers should add ``ResultsWriter`` to
        ``model.components`` rather than calling this directly.
        """
        tracker = None
        for instance in model.instances:
            if getattr(instance, "name", None) == "StateTracker":
                tracker = instance
                break
        if tracker is None:
            raise RuntimeError(
                "ResultsWriter requires a StateTracker component. Add StateTracker to your components list before model.run()."
            )

        arr = np.asarray(tracker.state_tracker)  # (num_states, num_ticks, num_groups)
        _, num_ticks, num_groups = arr.shape
        state_names = list(model.params.states)
        state_idx = {s: i for i, s in enumerate(state_names)}
        group_ids = list(tracker.group_ids)
        per_group = group_ids != ["all_patches"]
        # The tracker's aggregation_level is the contract for what each row of
        # the _per_group arrays represents (-1 = global, 0 = top hierarchy
        # segment, depth-1 = leaf / true per-patch).
        agg_level = int(getattr(tracker.params, "aggregation_level", -1))

        def _series(name):
            return arr[state_idx[name]] if name in state_idx else None  # (num_ticks, num_groups)

        S, E, I, R = (_series(s) for s in ("S", "E", "I", "R"))  # noqa: E741 — SEIR convention

        if I is None:
            raise RuntimeError(f"ResultsWriter requires an 'I' state in model.params.states; got {state_names!r}")

        # Global infectious time series (sum over patches/groups)
        I_global = I.sum(axis=1)
        peak_global = int(I_global.max())
        peak_tick = int(I_global.argmax())

        # Initial population per group (sum over states at tick 0). Used as the
        # attack-rate denominator. Falls back to 1 to avoid div-by-zero on
        # malformed inputs.
        pop_per_group = sum(
            (x[0] for x in (S, E, I, R) if x is not None),
            start=np.zeros(num_groups, dtype=arr.dtype),
        )

        if R is not None:
            attack_global = float(R[-1].sum() / max(int(pop_per_group.sum()), 1))
            attack_per_group = (R[-1] / np.maximum(pop_per_group, 1)).astype(float).tolist()
        else:
            attack_global = None
            attack_per_group = None

        peak_per_group = I.max(axis=0).astype(int).tolist() if per_group else None
        final_per_group = None
        if per_group:
            final_per_group = {name: x[-1].astype(int).tolist() for name, x in (("S", S), ("E", E), ("I", I), ("R", R)) if x is not None}

        # Global final compartment counts — always produced, by summing the
        # final tick across patches/groups. Available even when only a global
        # StateTracker is attached (no per-group breakdown required).
        final_global = {name: int(x[-1].sum()) for name, x in (("S", S), ("E", E), ("I", I), ("R", R)) if x is not None}

        return {
            "model_type": model.__class__.__name__,
            "num_ticks": int(num_ticks),
            "num_groups": len(group_ids),
            "group_ids": group_ids,
            "group_aggregation_level": agg_level,
            "states": state_names,
            "summary": {
                "peak_infectious_global": peak_global,
                "peak_tick": peak_tick,
                "attack_rate_global": attack_global,
                "final_state_global": final_global,
                "attack_rate_per_group": attack_per_group if per_group else None,
                "peak_infectious_per_group": peak_per_group,
                "final_state_per_group": final_per_group,
            },
        }
