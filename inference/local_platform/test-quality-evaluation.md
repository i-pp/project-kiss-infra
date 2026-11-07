# Evaluate correct test design before speed

The user's primary criterion is the ability to create **correct tests**. Task
completion and independent correctness come first; time is a supporting metric.
Passing the supplied12 tests in the current repair task does **not** measure this
ability. That task kept tests immutable to prevent weakening the acceptance gate.

This is a follow-up evaluation design, not an expansion of P0 permissions or an
implementation of a compiler/test-authoring agent. Track it with Issue #4. Keep
the existing read-only test boundary and reviewed execution profile unchanged.

## First small evaluation: specification to declarative cases

1. Freeze a small set of explicit API/task specifications before exposing them to
   models. Include normal behavior, valid input bounds, invalid inputs, errors and
   what remains undefined. Resolve ambiguities instead of inventing requirements.
2. Give each test-author model only the specification and public interface, not
   the implementation, reference source, hidden tests or mutant identities.
3. Request bounded data records: case ID, specification clause, input, expected
   output/error and a short rationale. Start with declarative JSON, not executable
   generated tests, arbitrary assertion code, eval or shell commands.
4. Validate the schema, bounds and semantic duplicates. An independent trusted
   adapter evaluates those cases against a separately validated correct reference
   and a frozen hidden set of incorrect implementations/mutations.
5. Independently review expected results and coverage. Model agreement or a
   confident rationale is not an oracle. The reference itself needs independent
   validation, such as a second implementation, mathematical properties, known
   controls and human review appropriate to the task.

Separate the test-proposal workspace from the grader's workspace. No model tools
or inference calls receive grader/reference source. The grader constructs a new
private evaluation snapshot and runs its trusted adapter inside the accepted
container boundary; proposed data cannot choose commands, paths, implementations
or mutations. Native/ELF/ABI cases need their separately reviewed profile before
execution. No project or generated code runs on the host.

## What to cover

Require a specification-to-case matrix, not just a list of happy-path examples:

- Normal inputs from different equivalence classes and relevant combinations.
- Boundaries: minimum/maximum, zero/empty, adjacent inside/outside values, lengths,
  overflow/rounding or encoding only where the specification defines behavior.
- Invalid inputs and malformed structure, types, missing/extra fields and required
  error identity. Do not assert undefined behavior as though it were required.
- State/sequence behavior: repeated operation, interrupted work, cancellation,
  uncertain outcomes and forbidden replay when the specification covers them.
- Independent properties/metamorphic relations only when justified by the
  specification. Fix random seeds and retain failing counterexamples.

Coverage claims must link to a real clause and valid expected behavior. More
cases, higher line coverage or more assertions do not by themselves mean better
or correct testing.

## Accuracy gates and defect detection

Report these separately, with fixed denominators:

1. **Test validity / false positives:** Does the known-correct reference satisfy
   every proposed requirement? Count wrong expected values, assertions outside the
   specification, missing assertions and vacuous/skipped cases. Tests that reject
   correct behavior do not earn credit for killing a mutant.
2. **Required behavior coverage:** Which predefined normal/boundary/error/state
   partitions have at least one valid distinguishing case? Deduplicate semantic
   repeats instead of rewarding inflated test count.
3. **Mutation/bug detection:** Of the predefined non-equivalent mutants, how many
   do the valid tests reject? Classify equivalent mutants independently, keep them
   out of that denominator, and retain a held-out mutation/bug set to reduce
   overfitting. Distinguish an assertion detecting the specified bug from a harness
   import failure, unrelated crash or environment timeout.
4. **Independent task completion:** Did test generation, validation, execution and
   review finish without weakening tests or changing the reference? Record the
   final artifacts and actual process results, not a model-written PASS claim.
5. **Supporting cost:** Only after accuracy, record time/tokens/resources, cold or
   warm load, model/runtime versions and failures. Do not trade correct coverage
   for a faster response or infer a general model rank from one small task.

A staged decision is preferable to invented numeric weights: first establish
valid tests with no false-positive requirement, then compare defect/coverage
results and completion. Select thresholds and task mix before model runs. Do not
change the rubric after seeing which model wins.

## Roles and fair comparison

Coder Next and120B can alternate as test author/reviewer, but consensus is only
supporting evidence. The deterministic reference, hidden controls and independent
review remain authoritative. Use the same frozen specification, output schema,
execution limits and grader for each author, and counterbalance review roles if
studying that effect. Keep implementation repair and test authoring as separate
phases; a model must not repair its tests to agree with its own faulty code.

For all planned tasks report success/failed/blocked/unexecuted and the complete
run history. Blocked means a prerequisite prevented starting; after-start model,
tool, transport or execution failures are not silently moved into blocked.
Separate model-quality errors from infrastructure failures without removing the
latter from execution-completion accounting.

## Bounded next step

Prepare two or three small frozen specifications, independent reference controls,
normal/boundary/error partitions and hidden non-equivalent mutants. Review that
package before running models. Then evaluate declarative case proposals in a new
explicit task, rather than adding test-write rights to the current P0 repair
client or broadening it indefinitely. Compiler body implementation remains outside
this evaluation-design document.
