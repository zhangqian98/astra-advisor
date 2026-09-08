# Adaptive routing examples

These files are schema examples only. Replace every ID, runtime capability list, and evidence filename with observations from the current task. Do not use the example model or effort as runtime confirmation.

- `feedback-task.example.json`: bounded task/risk input for `plan`.
- `feedback-runtime.example.json`: observed runtime capability input. The referenced evidence file must exist in the private Astra Advisor evidence directory.
- `feedback-outcome.example.json`: successful outcome shape.
- `feedback-capability-failure.example.json`: capability attribution only after specification, context, and environment have been explicitly checked.
- `feedback-process-failure.example.json`: non-model failure; this should add a corrective action without teaching the router that the requested model was incapable.
