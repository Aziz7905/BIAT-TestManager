import { useEffect, useState } from "react";
import { getScenarioOverview, updateScenario } from "../../../api/testing";
import type {
  BusinessPriority,
  Priority,
  ScenarioPolarity,
  ScenarioType,
} from "../../../types/testing";
import { Button, Modal, Spinner } from "../../ui";

interface ScenarioEditModalProps {
  open: boolean;
  scenarioId: string | null;
  sectionId: string | null;
  onClose: () => void;
  onSaved: () => void;
}

const SCENARIO_TYPES: ScenarioType[] = [
  "happy_path",
  "alternative_flow",
  "edge_case",
  "security",
  "performance",
  "accessibility",
];

const PRIORITIES: Priority[] = ["low", "medium", "high", "critical"];
const BUSINESS_PRIORITIES: BusinessPriority[] = ["must_have", "should_have", "could_have", "wont_have"];

export default function ScenarioEditModal({
  open,
  scenarioId,
  sectionId,
  onClose,
  onSaved,
}: ScenarioEditModalProps) {
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [scenarioType, setScenarioType] = useState<ScenarioType>("happy_path");
  const [priority, setPriority] = useState<Priority>("medium");
  const [businessPriority, setBusinessPriority] = useState<BusinessPriority | "">("");
  const [polarity, setPolarity] = useState<ScenarioPolarity>("positive");

  useEffect(() => {
    if (!open || !scenarioId) return;
    let cancelled = false;
    setLoading(true);
    getScenarioOverview(scenarioId)
      .then((s) => {
        if (cancelled) return;
        setTitle(s.title);
        setDescription(s.description ?? "");
        setScenarioType(s.scenario_type);
        setPriority(s.priority);
        setBusinessPriority(s.business_priority ?? "");
        setPolarity(s.polarity);
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [open, scenarioId]);

  async function handleSave() {
    if (!scenarioId || !sectionId) return;
    setSaving(true);
    try {
      await updateScenario(sectionId, scenarioId, {
        title,
        description,
        scenario_type: scenarioType,
        priority,
        business_priority: businessPriority || null,
        polarity,
      });
      onSaved();
      onClose();
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Edit scenario"
      size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={() => void handleSave()} isLoading={saving} disabled={!title.trim()}>
            Save
          </Button>
        </>
      }
    >
      {loading ? (
        <div className="flex h-32 items-center justify-center">
          <Spinner />
        </div>
      ) : (
        <div className="space-y-4">
          <Field label="Title" required>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className={inputClass}
            />
          </Field>

          <div className="grid grid-cols-2 gap-4">
            <Field label="Type">
              <select
                value={scenarioType}
                onChange={(e) => setScenarioType(e.target.value as ScenarioType)}
                className={inputClass}
              >
                {SCENARIO_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {formatLabel(t)}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Priority">
              <select
                value={priority}
                onChange={(e) => setPriority(e.target.value as Priority)}
                className={inputClass}
              >
                {PRIORITIES.map((p) => (
                  <option key={p} value={p}>
                    {formatLabel(p)}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Business priority">
              <select
                value={businessPriority}
                onChange={(e) => setBusinessPriority(e.target.value as BusinessPriority | "")}
                className={inputClass}
              >
                <option value="">—</option>
                {BUSINESS_PRIORITIES.map((p) => (
                  <option key={p} value={p}>
                    {formatLabel(p)}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Polarity">
              <select
                value={polarity}
                onChange={(e) => setPolarity(e.target.value as ScenarioPolarity)}
                className={inputClass}
              >
                <option value="positive">Positive</option>
                <option value="negative">Negative</option>
              </select>
            </Field>
          </div>

          <Field label="Description">
            <textarea
              rows={4}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className={inputClass}
            />
          </Field>
        </div>
      )}
    </Modal>
  );
}

const inputClass =
  "w-full rounded-md border border-slate-200 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100";

function Field({ label, required, children }: { label: string; required?: boolean; children: React.ReactNode }) {
  return (
    <div>
      <label className="mb-1 block text-sm font-medium text-slate-700">
        {label} {required && <span className="text-red-500">*</span>}
      </label>
      {children}
    </div>
  );
}

function formatLabel(value: string) {
  return value.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
