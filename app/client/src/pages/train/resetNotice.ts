/** The banner shown while a start-over reset runs, and once it has finished. */
export function resetNoticeText(count: number, done: boolean): string {
  const n = `${count} assignment${count === 1 ? '' : 's'}`;
  return done
    ? `${n} reset: notebooks are back to their starters and the output tables are gone.`
    : `Resetting ${n}: notebooks back to their starters, output tables being dropped (about a minute).`;
}
