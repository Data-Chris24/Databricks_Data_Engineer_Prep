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
experiments cannot collide with anyone else's or with production.

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
