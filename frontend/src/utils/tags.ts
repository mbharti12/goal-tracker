export const DEFAULT_TAG_CATEGORIES = [
  "Exercise",
  "Nutrition",
  "Sleep",
  "Mind",
  "Work",
  "Personal",
  "Social",
  "Other",
] as const;

export const normalizeTagCategory = (value?: string | null) => {
  const trimmed = value?.trim();
  if (!trimmed) {
    return "Other";
  }
  const match = DEFAULT_TAG_CATEGORIES.find(
    (category) => category.toLowerCase() === trimmed.toLowerCase(),
  );
  return match ?? trimmed;
};

export const buildTagCategoryTabs = (tags: Array<{ category?: string | null }>) => {
  const customCategories = new Set<string>();
  tags.forEach((tag) => {
    const normalized = normalizeTagCategory(tag.category);
    if (!DEFAULT_TAG_CATEGORIES.includes(normalized)) {
      customCategories.add(normalized);
    }
  });
  return [
    ...DEFAULT_TAG_CATEGORIES,
    ...Array.from(customCategories).sort((a, b) => a.localeCompare(b)),
  ];
};
