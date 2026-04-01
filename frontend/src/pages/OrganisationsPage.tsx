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
      <div className="p-6 text-sm text-gray-500">No organisations found.</div>
    );
  } else {
    organizationsContent = (
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
              Name
            </th>
            <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
              Domain
            </th>
            <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
              Created
            </th>
            <th className="px-6 py-4 text-right text-xs font-semibold uppercase tracking-wide text-gray-500">
              Actions
            </th>
          </tr>
        </thead>

        <tbody className="divide-y divide-gray-100">
          {organizations.map((organization) => {
            const isDeletingThisOrganization =
              deletingOrganizationId === organization.id;

            return (
              <tr key={organization.id}>
                <td className="px-6 py-4 text-sm text-gray-900">
                  {organization.name}
                </td>
                <td className="px-6 py-4 text-sm text-gray-600">
                  {organization.domain}
                </td>
                <td className="px-6 py-4 text-sm text-gray-600">
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
    <div className="min-h-screen bg-gray-50">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">
            Organisations
          </h1>
          <p className="mt-1 text-sm text-gray-600">
            Manage platform organisations.
          </p>
        </div>

        <Button onClick={openCreateModal}>New Organisation</Button>
      </div>

      {successMessage ? (
        <div className="mb-4 rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">
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

      <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm">
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