/** Organisation management workspace refreshed to match the branded admin surfaces. */
import { useEffect, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import {
  createOrganization,
  deleteOrganization,
  getOrganizations,
  updateOrganization,
} from "../api/accounts/organizations";
import { Button } from "../components/Button";
import { ErrorMessage } from "../components/ErrorMessage";
import { FormInput } from "../components/FormInput";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { Modal } from "../components/Modal";
import { Badge } from "../components/ui";
import type { Organization, OrganizationFormData } from "../types/accounts";

function getErrorMessage(error: unknown, fallback: string): string {
  if (
    typeof error === "object" &&
    error !== null &&
    "response" in error &&
    typeof (error as { response?: unknown }).response === "object"
  ) {
    const response = (error as {
      response?: { data?: { detail?: string; error?: string } };
    }).response;

    return response?.data?.detail || response?.data?.error || fallback;
  }

  return fallback;
}

const initialForm: OrganizationFormData = {
  name: "",
  domain: "",
};

export default function OrganisationsPage() {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingOrganization, setEditingOrganization] =
    useState<Organization | null>(null);
  const [deletingOrganizationId, setDeletingOrganizationId] = useState<
    string | null
  >(null);

  const [form, setForm] = useState<OrganizationFormData>(initialForm);

  const loadOrganizations = async (): Promise<void> => {
    try {
      setIsLoading(true);
      setErrorMessage("");

      const organizationsData = await getOrganizations();
      setOrganizations(organizationsData);
    } catch (error: unknown) {
      setErrorMessage(
        getErrorMessage(error, "Failed to load organisations.")
      );
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void loadOrganizations();
  }, []);

  const openCreateModal = (): void => {
    setEditingOrganization(null);
    setForm(initialForm);
    setErrorMessage("");
    setSuccessMessage("");
    setIsModalOpen(true);
  };

  const openEditModal = (organization: Organization): void => {
    setEditingOrganization(organization);
    setForm({
      name: organization.name,
      domain: organization.domain,
    });
    setErrorMessage("");
    setSuccessMessage("");
    setIsModalOpen(true);
  };

  const closeModal = (): void => {
    setIsModalOpen(false);
    setEditingOrganization(null);
    setForm(initialForm);
  };

  const handleSubmit = async (
    event: FormEvent<HTMLFormElement>
  ): Promise<void> => {
    event.preventDefault();

    try {
      setIsSaving(true);
      setErrorMessage("");
      setSuccessMessage("");

      if (editingOrganization) {
        await updateOrganization(editingOrganization.id, {
          name: form.name,
          domain: form.domain,
        });
        setSuccessMessage("Organisation updated successfully.");
      } else {
        await createOrganization({
          name: form.name,
          domain: form.domain,
        });
        setSuccessMessage("Organisation created successfully.");
      }

      await loadOrganizations();
      closeModal();
    } catch (error: unknown) {
      setErrorMessage(
        getErrorMessage(error, "Failed to save organisation.")
      );
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async (organizationId: string): Promise<void> => {
    const confirmed = globalThis.confirm(
      "Are you sure you want to delete this organisation?"
    );

    if (!confirmed) {
      return;
    }

    try {
      setDeletingOrganizationId(organizationId);
      setErrorMessage("");
      setSuccessMessage("");

      await deleteOrganization(organizationId);
      setSuccessMessage("Organisation deleted successfully.");
      await loadOrganizations();
    } catch (error: unknown) {
      setErrorMessage(
        getErrorMessage(error, "Failed to delete organisation.")
      );
    } finally {
      setDeletingOrganizationId(null);
    }
  };

  let organizationsContent: ReactNode;

  if (isLoading) {
    organizationsContent = (
      <div className="flex min-h-[220px] items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    );
  } else if (organizations.length === 0) {
    organizationsContent = (
      <div className="p-6 text-sm text-muted">No organisations found.</div>
    );
  } else {
    organizationsContent = (
      <table className="min-w-full divide-y divide-border">
        <thead className="bg-bg">
          <tr>
            <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-[0.18em] text-muted">
              Name
            </th>
            <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-[0.18em] text-muted">
              Domain
            </th>
            <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-[0.18em] text-muted">
              Created
            </th>
            <th className="px-6 py-4 text-right text-xs font-semibold uppercase tracking-[0.18em] text-muted">
              Actions
            </th>
          </tr>
        </thead>

        <tbody className="divide-y divide-border">
          {organizations.map((organization) => {
            const isDeletingThisOrganization =
              deletingOrganizationId === organization.id;

            return (
              <tr key={organization.id} className="transition hover:bg-bg">
                <td className="px-6 py-4 text-sm font-medium text-text">
                  {organization.name}
                </td>
                <td className="px-6 py-4 text-sm text-muted">
                  {organization.domain}
                </td>
                <td className="px-6 py-4 text-sm text-muted">
                  {new Date(organization.created_at).toLocaleDateString()}
                </td>
                <td className="px-6 py-4 text-right text-sm">
                  <div className="flex justify-end gap-2">
                    <Button
                      variant="secondary"
                      size="md"
                      onClick={() => openEditModal(organization)}
                    >
                      Edit
                    </Button>

                    <Button
                      variant="danger"
                      size="md"
                      onClick={() => handleDelete(organization.id)}
                      isLoading={isDeletingThisOrganization}
                      loadingText="Deleting..."
                    >
                      Delete
                    </Button>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    );
  }

  const modalTitle = editingOrganization
    ? "Edit Organisation"
    : "Create Organisation";

  const submitLabel = editingOrganization ? "Update" : "Create";

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <Badge variant="tag">Administration</Badge>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight text-text">
            Organisations
          </h1>
          <p className="mt-2 text-sm leading-6 text-muted">
            Manage platform organisations.
          </p>
        </div>

        <Button onClick={openCreateModal}>New Organisation</Button>
      </div>

      {successMessage ? (
        <div className="rounded-2xl border border-status-verified-text/15 bg-status-verified-bg px-4 py-3 text-sm text-status-verified-text shadow-sm">
          {successMessage}
        </div>
      ) : null}

      {errorMessage ? (
        <ErrorMessage
          message={errorMessage}
          onDismiss={() => setErrorMessage("")}
          className="mb-4"
        />
      ) : null}

      <div className="overflow-hidden rounded-[28px] border border-border bg-surface shadow-panel">
        {organizationsContent}
      </div>

      <Modal
        isOpen={isModalOpen}
        onClose={closeModal}
        title={modalTitle}
        size="md"
      >
        <form onSubmit={handleSubmit} className="space-y-4">
          <FormInput
            id="organisation-name"
            label="Name"
            type="text"
            value={form.name}
            onChange={(event) =>
              setForm((previousForm) => ({
                ...previousForm,
                name: event.target.value,
              }))
            }
            required
          />

          <FormInput
            id="organisation-domain"
            label="Domain"
            type="text"
            value={form.domain}
            onChange={(event) =>
              setForm((previousForm) => ({
                ...previousForm,
                domain: event.target.value,
              }))
            }
            placeholder="biat-it.tn"
            required
          />

          <div className="flex justify-end gap-3">
            <Button type="button" variant="secondary" onClick={closeModal}>
              Cancel
            </Button>

            <Button
              type="submit"
              isLoading={isSaving}
              loadingText="Saving..."
            >
              {submitLabel}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
