import { describe, expect, it } from 'vitest';

import { allLessonPaths, assignmentById, assignmentIdsFor, lessonPaths, notebooks } from './content';

const DEEP_DIVE = 'notebooks/lessons/associate/S2/04_optional_auto_loader_deep_dive';

describe('optional lessons', () => {
  it('are listed with the section but do not hold its assignment back', () => {
    expect(allLessonPaths('ASSOC-S2')).toContain(DEEP_DIVE);
    expect(lessonPaths('ASSOC-S2')).not.toContain(DEEP_DIVE);
    expect(lessonPaths('ASSOC-S2')).toHaveLength(3);
    expect(notebooks['ASSOC-S2'].lessons.find((l) => l.path === DEEP_DIVE)?.optional).toBe(true);
  });
});

describe('assignmentById', () => {
  it("resolves a section's own assignment, gated on its required lessons", () => {
    const a = assignmentById('ASSOC-S2');
    expect(a).toMatchObject({ id: 'ASSOC-S2', sectionId: 'ASSOC-S2', extra: null });
    expect(a?.gate).toEqual(lessonPaths('ASSOC-S2'));
  });

  it('resolves an extra under its own id, gated on every lesson including the optional one', () => {
    const a = assignmentById('ASSOC-S2-AUTO-LOADER');
    expect(a?.sectionId).toBe('ASSOC-S2');
    expect(a?.gate).toEqual(allLessonPaths('ASSOC-S2'));
    // The key server/lib/grading.ts gradeJobKey derives from the id.
    expect(a?.extra?.grade_job).toBe('grade_assoc_s2_auto_loader');
  });

  it('knows nothing it was not built with', () => {
    expect(assignmentById('ASSOC-S2-NOPE')).toBeUndefined();
    expect(assignmentById('ASSOC-S9')).toBeUndefined();
  });

  it("lists a section's assignment first, then its extras", () => {
    expect(assignmentIdsFor('ASSOC-S2')).toEqual(['ASSOC-S2', 'ASSOC-S2-AUTO-LOADER']);
    expect(assignmentIdsFor('ASSOC-S3')).toEqual(['ASSOC-S3']);
  });
});
