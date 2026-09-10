# Implementing CI/CD — 10%

Getting the same code into dev, test and prod without editing it on the way.

## Git folders — `ASSOC-S5-O1`

Databricks Git folders put notebooks under normal version control: branch, commit,
push, open a pull request, all from the workspace.

Work on a **branch per change** and integrate through pull requests. Beyond avoiding
collisions, that gives every change a review point and a revert path — the things you
want on the day something breaks in production.

## Bundles — `ASSOC-S5-O2`, `ASSOC-S5-O3`

Declarative Automation Bundles (formerly Databricks Asset Bundles) package jobs,
pipelines and their configuration as version-controlled code.

```yaml
bundle:
  name: my-project

variables:
  catalog:
    default: dev_catalog

targets:
  dev:
    default: true
    mode: development
  prod:
    mode: production
    variables:
      catalog: prod_catalog          # same definition, different value
```

**One definition, promoted across environments, with only configuration differing.**
That is the whole point — and it is what makes a dev deployment genuinely predict
prod. Two copies of a bundle diverge, and the moment they do, dev stops telling you
anything.

`mode: development` prefixes deployed resources with your username, so your
experiments cannot collide with anyone else's or with production. It also pauses every
schedule and trigger, caps concurrent runs at one and disables the deployment lock, so
a development deploy never fires on its own. `mode: production` drops the prefix,
keeps schedules live and expects a service-principal `run_as`.

## The CLI in automation — `ASSOC-S5-O4`

```bash
databricks bundle validate --strict -t prod
databricks bundle deploy -t prod
databricks bundle run my_job -t prod
```

**`validate` is a configuration check, not a test run.** It catches malformed YAML,
unresolved variables and bad references before anything is uploaded. It never executes
your code — so a bundle can validate cleanly and still fail at runtime, which is why a
pipeline runs tests as well.

In CI, authenticate as a **service principal** using OAuth machine-to-machine
(`DATABRICKS_CLIENT_ID` / `DATABRICKS_CLIENT_SECRET`), never as a person. Deploys are
then attributable to the pipeline and scoped to what it needs.

> Worth knowing: `DATABRICKS_CONFIG_PROFILE`, if set, overrides those M2M variables and
> the CLI silently authenticates as *you* instead. A local test of CI auth can appear to
> succeed while proving nothing.

## Further reading

Official documentation for what this section tests, one link per topic:

- [Git folders](https://docs.databricks.com/aws/en/repos/) — clone, branch, commit and pull inside the workspace.
- [Git operations in Git folders](https://docs.databricks.com/aws/en/repos/git-operations-with-repos) — the dialog step by step, including conflicts.
- [Declarative Automation Bundles](https://docs.databricks.com/aws/en/dev-tools/bundles/) — the bundles documentation home.
- [Bundle configuration](https://docs.databricks.com/aws/en/dev-tools/bundles/settings) — every top-level key in `databricks.yml`.
- [Bundle variables](https://docs.databricks.com/aws/en/dev-tools/bundles/variables) — defaults, lookups and overrides.
- [Deployment modes](https://docs.databricks.com/aws/en/dev-tools/bundles/deployment-modes) — what development and production modes change.
- [Develop a job with bundles](https://docs.databricks.com/aws/en/dev-tools/bundles/jobs-tutorial) — the end-to-end tutorial.
- [CI/CD on Databricks](https://docs.databricks.com/aws/en/dev-tools/ci-cd/) — the recommended pipeline shape.
- [GitHub Actions](https://docs.databricks.com/aws/en/dev-tools/ci-cd/github) — the `setup-cli` action and a deploy workflow.

Videos for another angle on the hard parts (channel, length):

- [Deploy Faster: Databricks Asset Bundles + Git Explained](https://www.youtube.com/watch?v=FZpgwclX88Q) — Databricks Skill Builder, 23 min. Bundles and Git folders from the source.
- [Databricks CI/CD: Intro to Databricks Asset Bundles](https://www.youtube.com/watch?v=uG0dTF5mmvc) — Dustin Vannoy, 20 min. A practitioner's first bundle, validate to deploy.
