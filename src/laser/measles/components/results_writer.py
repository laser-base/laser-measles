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
from laser.measles.components.base_tracker_state import BaseStateTracker


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
            attack_rate_global:         float | None  (fraction of initial
                                        susceptibles globally that left the
                                        S compartment; in [0, 1]; null when
                                        ``S`` isn't in model.params.states)
            attack_rate_per_group:      list[float] | None  (per-group
                                        version of attack_rate_global; in
                                        [0, 1] per entry)
            final_state_global:         dict[str, int]
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
        # Fail fast: the model must already have a StateTracker. We do this
        # at construction time rather than at finalize() so the error surfaces
        # immediately on `add_component(ResultsWriter)` instead of after a
        # full tick loop has run. Constraint: add a StateTracker (any model
        # variant's subclass of BaseStateTracker) BEFORE adding ResultsWriter.
        if not any(isinstance(i, BaseStateTracker) for i in model.instances):
            raise RuntimeError(
                "ResultsWriter requires a StateTracker component to already be in "
                "model.components. Add a StateTracker before adding ResultsWriter."
            )

    # No __call__ on purpose. BaseLaserModel only adds components with a
    # __call__ method to ``self.phases`` (the per-tick dispatch loop); a
    # no-op __call__ would still get dispatched every tick. ResultsWriter
    # only needs to act at end-of-run, so we stay out of ``phases`` by
    # not defining __call__ at all. ``self.instances`` (which the
    # finalize() hook iterates) gets the component either way.

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

        Walks ``model.instances`` for any ``BaseStateTracker`` (each
        model variant — ABM, biweekly, compartmental — registers its
        own ``StateTracker`` subclass of that base). When multiple are
        present (the "hello-world" pattern adds both a default global
        tracker and a per-patch one with ``aggregation_level=0``), pick
        the most granular — the largest ``aggregation_level``.
        """
        trackers = [instance for instance in model.instances if isinstance(instance, BaseStateTracker)]
        if not trackers:
            raise RuntimeError(
                "ResultsWriter requires a StateTracker component. Add StateTracker to your components list before model.run()."
            )
        tracker = max(trackers, key=lambda t: int(getattr(t.params, "aggregation_level", -1)))

        arr = np.asarray(tracker.state_tracker)  # (num_states, num_ticks, num_groups)
        _, num_ticks, _num_groups = arr.shape
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

        # Attack rate = "fraction of initial susceptibles in this group that
        # ever left S during the run". Depends only on S, which avoids two
        # problems with an R-based definition under spatial migration:
        #   1. Migrating agents who recover in a destination patch inflate
        #      R[-1] for that patch beyond its initial population, producing
        #      attack rates > 1.0.
        #   2. Per-patch state counters in patches.states are known to
        #      underflow when migration shuffles agents across patches
        #      faster than the tracker can reconcile (laser-measles issue:
        #      per-patch state underflow under migration). The S channel is
        #      more robust because it only decreases under transmission and
        #      increases under births — both conserved end-to-end.
        # int64 math defuses any uint32 underflow already baked into the
        # tracker; the final fraction is clamped to [0, 1].
        if S is not None:
            S0_signed = S[0].astype(np.int64)
            S_final_signed = S[-1].astype(np.int64)
            new_infections = np.maximum(S0_signed - S_final_signed, 0)
            attack_per_group = np.clip(new_infections / np.maximum(S0_signed, 1), 0.0, 1.0).astype(float).tolist()
            attack_global = float(new_infections.sum() / max(int(S0_signed.sum()), 1))
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
