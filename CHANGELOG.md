# Changelog

## Unreleased

* Replace polars/list-comprehension run-length expansion of `patch_id` with
  `np.repeat` in five ABM components: `process_no_births`, `process_constant_pop`,
  `process_initialize_equilibrium_states`, `process_wpp_vital_dynamics`,
  and per-tick newborn assignment in `process_vital_dynamics`.
* Add `patch_id` distribution regression tests for `NoBirthsProcess`,
  `ConstantPopProcess`, and `VitalDynamicsProcess` births.

## 0.0.1 (2024-10-18)

* First release on PyPI.
