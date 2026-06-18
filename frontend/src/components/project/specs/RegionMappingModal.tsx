import { useEffect, useMemo, useState } from "react";
import { Button, Modal } from "../../ui";
import { applyRegionMapping } from "../../../api/specs";
import {
  BIAT_MAPPING_FIELDS,
  REGION_RECORD_TYPE_OPTIONS,
} from "../../../types/specs";
import type { RegionRecordType, SpecRegionMappingTarget } from "../../../types/specs";

interface RegionMappingModalProps {
  open: boolean;
  sourceId: string | null;
  region: SpecRegionMappingTarget | null;
  onClose: () => void;
  onSaved: () => void;
}

const MAPPED_TYPES: RegionRecordType[] = ["requirement", "test_case"];

function normalize(label: string): string {
  return label
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

// Conservative, non-authoritative prefill: only an exact identity match between
// the column label and a target field. The user can change every suggestion.
function prefillMapping(
  columns: string[],
  existing: Record<string, string>
): Record<string, string> {
  if (existing && Object.keys(existing).length > 0) {
    return { ...existing };
  }
  const fieldValues = new Set(BIAT_MAPPING_FIELDS.map((field) => field.value).filter(Boolean));
  const mapping: Record<string, string> = {};
  for (const column of columns) {
    const slug = normalize(column);
    if (fieldValues.has(slug)) {
      mapping[column] = slug;
    }
  }
  return mapping;
}

export default function RegionMappingModal({
  open,
  sourceId,
  region,
  onClose,
  onSaved,
}: RegionMappingModalProps) {
  const [recordType, setRecordType] = useState<RegionRecordType>("requirement");
  const [columnMapping, setColumnMapping] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open && region) {
      setRecordType(region.record_type ?? "requirement");
      setColumnMapping(prefillMapping(region.columns, region.column_mapping));
      setError(null);
    }
  }, [open, region]);

  const showColumnMapping = useMemo(() => MAPPED_TYPES.includes(recordType), [recordType]);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!sourceId || !region) return;
    setSaving(true);
    setError(null);
    try {
      await applyRegionMapping(sourceId, {
        region_id: region.region_id,
        record_type: recordType,
        column_mapping: showColumnMapping ? columnMapping : {},
      });
      onSaved();
    } catch {
      setError("Could not apply this mapping.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={region ? `Map region ${region.source_range}` : "Map region"}
      size="xl"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button form="region-mapping-form" type="submit" isLoading={saving}>
            Apply mapping
          </Button>
        </>
      }
    >
      {!region ? null : (
        <form id="region-mapping-form" onSubmit={handleSubmit} className="space-y-4">
          <p className="text-xs text-slate-500">
            {region.container} • {region.source_range} • {region.columns.length} columns
          </p>

          <div className="space-y-1.5">
            <label className="text-sm font-medium text-slate-700">This region is</label>
            <select
              value={recordType}
              onChange={(event) => setRecordType(event.target.value as RegionRecordType)}
              className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-900 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-blue-600"
            >
              {REGION_RECORD_TYPE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          {showColumnMapping ? (
            <div className="space-y-2">
              <p className="text-sm font-medium text-slate-700">Column mapping</p>
              <p className="text-xs text-slate-500">
                Map each column to a BIAT field. Unmapped columns are kept as extra fields.
              </p>
              <div className="overflow-hidden rounded-lg border border-slate-200">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                    <tr>
                      <th className="px-4 py-2.5">Column</th>
                      <th className="px-4 py-2.5">BIAT field</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 bg-white">
                    {region.columns.map((column) => (
                      <tr key={column}>
                        <td className="px-4 py-2.5 font-medium text-slate-800">{column}</td>
                        <td className="px-4 py-2.5">
                          <select
                            value={columnMapping[column] ?? ""}
                            onChange={(event) =>
                              setColumnMapping((current) => ({
                                ...current,
                                [column]: event.target.value,
                              }))
                            }
                            className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-blue-600"
                          >
                            {BIAT_MAPPING_FIELDS.map((field) => (
                              <option key={field.value || "__extra__"} value={field.value}>
                                {field.label}
                              </option>
                            ))}
                          </select>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <p className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm text-slate-600">
              {recordType === "ignore"
                ? "Rows in this region will be excluded from import."
                : "Rows will be imported as-is, preserving their original columns."}
            </p>
          )}

          {error && <p className="text-sm text-red-600">{error}</p>}
        </form>
      )}
    </Modal>
  );
}
