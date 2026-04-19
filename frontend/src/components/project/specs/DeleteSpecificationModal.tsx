import { Button, Modal } from "../../ui";

interface DeleteSpecificationModalProps {
  open: boolean;
  title: string;
  description: string;
  deleting: boolean;
  onClose: () => void;
  onConfirm: () => void;
}

export default function DeleteSpecificationModal({
  open,
  title,
  description,
  deleting,
  onClose,
  onConfirm,
}: DeleteSpecificationModalProps) {
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      size="md"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="danger" onClick={onConfirm} isLoading={deleting}>
            Delete
          </Button>
        </>
      }
    >
      <p className="text-sm leading-6 text-slate-600">{description}</p>
    </Modal>
  );
}
