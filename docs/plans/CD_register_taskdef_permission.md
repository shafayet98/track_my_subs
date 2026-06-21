# CD: grant ecs:RegisterTaskDefinition to the deploy role (#26 follow-up)

## Goal

Unblock CD. The migrate-before-rollout step added in #26 registers a one-off ECS
task-def revision (cloned from the live one, image swapped to the new SHA) so
`alembic upgrade head` runs on the new image before rollout — but the
`github-actions-deploy` role lacks `ecs:RegisterTaskDefinition`, so the step fails
with `AccessDeniedException`.

## Scope

- Add `ecs:RegisterTaskDefinition` to the deploy role's ECS policy statement in
  `infra/stacks/cicd_stack.py`. The required `iam:PassRole` (scoped to
  `ecs-tasks.amazonaws.com`) is already granted.

## Out of scope

- Any change to the CD workflow itself (the #26 logic is correct; it was only
  missing the permission).

## Note on rollout

`TrackMySubs-Cicd` is intentionally **not** deployed by CD, so this change only
takes effect after a one-time manual `cdk deploy TrackMySubs-Cicd`. That deploy
was done out-of-band to unblock the pipeline; this commit makes the stack source
match the deployed permission.

## Acceptance criteria
- `cdk synth TrackMySubs-Cicd` includes `ecs:RegisterTaskDefinition`.
- The CD migration step (register task def → run migration) succeeds end-to-end.
