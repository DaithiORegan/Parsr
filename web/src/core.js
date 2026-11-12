export const localJob = (j) =>
  /\b(cork|kerry|tralee|killarney|kenmare|listowel|dingle|killorglin|castleisland|cahersiveen|ballybunion|ballyheigue|bandon|kinsale|youghal|macroom|dunmanway|millstreet|mitchelstown|mallow|midleton|cobh|fermoy|clonakilty|bantry|skibbereen|little island|ballincollig|carrigaline)\b/i.test(
    j.location || "",
  );
export function validateAnalysis(a) {
  if (
    !a ||
    !Number.isInteger(a.score) ||
    a.score < 0 ||
    a.score > 100 ||
    typeof a.summary !== "string"
  )
    return false;
  return ["strengths", "gaps", "suggestions", "limitations"].every(
    (k) =>
      Array.isArray(a[k]) &&
      a[k].length <= 15 &&
      a[k].every((v) => typeof v === "string" && v.length <= 3000),
  );
}
export const analysisSchema = {
  type: "object",
  additionalProperties: false,
  properties: {
    score: { type: "integer", minimum: 0, maximum: 100 },
    summary: { type: "string" },
    ...Object.fromEntries(
      ["strengths", "gaps", "suggestions", "limitations"].map((k) => [
        k,
        { type: "array", items: { type: "string" } },
      ]),
    ),
  },
  required: [
    "score",
    "summary",
    "strengths",
    "gaps",
    "suggestions",
    "limitations",
  ],
};
export async function cacheKey(cv, job) {
  const bytes = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(
      JSON.stringify([
        cv.id,
        cv.text,
        job.id,
        job.description,
        job.title,
        job.description_complete,
        "v1",
      ]),
    ),
  );
  return Array.from(new Uint8Array(bytes), (x) =>
    x.toString(16).padStart(2, "0"),
  ).join("");
}
