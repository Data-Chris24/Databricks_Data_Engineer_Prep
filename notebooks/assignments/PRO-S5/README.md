# Assignment — `PRO-S5` Monitoring and Alerting

**Objectives:** `PRO-S5-O1`, `O2`, `O5`, `O6`

## Before you start

Work the two lessons in `notebooks/lessons/professional/S5/`, and generate the data
(`databricks bundle run generate_datasets_pro_s5 -t free`).

> **The lesson's fixed threshold cannot work here, and you can prove it.** The
> weekend range and the degraded weekday range do not overlap the way a single number
> could separate them: any threshold above the weekend maximum fires every weekend,
> and any threshold below the weekend minimum never fires at all.

## The task

`workspace.de_prep.pro_s5_assess_metrics` holds 90 days of daily pipeline metrics.
Somewhere in there a gradual degradation begins. There is also one day of legitimately
high volume — a campaign — which must **not** alert.

Design an alert and evaluate it against the whole history.

## The output contract

**`workspace.de_prep.pro_s5_alert_evaluation`** — one row per evaluated day.

| Column | Type | Meaning |
|---|---|---|
| `run_date` | `DATE` | |
| `day_type` | `STRING` | `weekday` or `weekend` |
| `rows_processed` | `INT` | the observed metric |
| `baseline` | `DOUBLE` | what you expected for this day |
| `pct_of_baseline` | `DOUBLE` | observed as a percentage of baseline |
| `should_alert` | `BOOLEAN` | whether your alert fires |

Days without enough history to form a baseline are excluded.

### Requirements

1. **The baseline must respect the weekly cycle.** Comparing a Saturday to a Friday is
   comparing a weekend to a weekday.
2. **No alerts before the degradation begins.** A single false positive in the healthy
   period fails this — an alert that cries wolf is worse than none.
3. **The campaign spike must not alert.** Alert on direction, not on deviation.
4. **The degradation must be detected**, and reasonably promptly once it is
   established.
5. Column order matters — the tests compare the whole schema.

## Grading

In the study app, open **Learn → PRO-S5** and press **Grade my assignment**: it
runs this section's checks against the tables you produced and shows what
passed and what didn't. The same job from a terminal:

```bash
databricks bundle run grade_pro_s5 -t free --profile FREE
```

## Hints

<details><summary>How do I build a seasonal baseline?</summary>

Partition by day of week, then average the previous few occurrences of that same
weekday. Offset the window so today does not contribute to its own baseline.
</details>

<details><summary>My alert fires every weekend</summary>

Requirement 1. The baseline is comparing across day types.
</details>

<details><summary>My alert fires on the campaign day</summary>

Requirement 3. That day is *above* baseline. Alert on drops.
</details>

<details><summary>I get scattered single-day alerts</summary>

Require persistence — several consecutive low days. You trade a day of detection
latency for an alert people believe.
</details>
