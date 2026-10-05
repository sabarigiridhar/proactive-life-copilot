import JSZip from "jszip";
import type { DomainRecord, RecordDomain } from "@/lib/api/client";

const publicFields: Record<RecordDomain, string[]> = {
  wealth: [
    "id",
    "entry_date",
    "transaction_type",
    "amount",
    "currency",
    "category",
    "merchant",
    "notes",
    "source",
    "created_at",
    "updated_at",
  ],
  health: [
    "id",
    "entry_date",
    "sleep_hours",
    "workout_type",
    "calories_consumed",
    "notes",
    "source",
    "created_at",
    "updated_at",
  ],
  learning: [
    "id",
    "entry_date",
    "topic",
    "summary_text",
    "duration_minutes",
    "url_reference",
    "source",
    "created_at",
    "updated_at",
  ],
};

function csvCell(value: unknown): string {
  return `"${String(value ?? "").replaceAll('"', '""')}"`;
}

export function publicRecords(domain: RecordDomain, records: DomainRecord[]) {
  return records.map((record) =>
    Object.fromEntries(
      publicFields[domain].map((field) => [
        field,
        (record as unknown as Record<string, unknown>)[field] ?? null,
      ]),
    ),
  );
}

export async function createRecordsArchive(records: Record<RecordDomain, DomainRecord[]>) {
  const normalized = Object.fromEntries(
    (Object.keys(publicFields) as RecordDomain[]).map((domain) => [
      domain,
      publicRecords(domain, records[domain]),
    ]),
  );
  const archive = new JSZip();
  archive.file("life-copilot-records.json", JSON.stringify(normalized, null, 2));
  for (const domain of Object.keys(publicFields) as RecordDomain[]) {
    const fields = publicFields[domain];
    const rows = normalized[domain] ?? [];
    const csv = [
      fields.join(","),
      ...rows.map((row) => fields.map((field) => csvCell(row[field])).join(",")),
    ].join("\r\n");
    archive.file(`${domain}.csv`, csv);
  }
  return archive.generateAsync({ type: "blob", compression: "DEFLATE" });
}
