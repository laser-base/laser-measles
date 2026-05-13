"""ResultsWriter component — opt-in JSON results dump at end of run.

Adding ``ResultsWriter`` to ``model.components`` causes the model to invoke
``write_results()`` at end of run, producing the canonical JSON summary.
Calibration loops and other contexts that don't want a per-run JSON file
on disk simply omit this component.

This is the recommended way to get a results file. The bare
``model.write_results()`` method is still available for callers who want
to invoke it manually (e.g. once after a calibration loop), but adding
``ResultsWriter`` is the path the docs and prompts will steer toward.
"""

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

    Requires a ``StateTracker`` somewhere in ``model.components`` — that's
    where the underlying ``write_results()`` reads the time-series from.

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
        model.write_results(self.params.path)
