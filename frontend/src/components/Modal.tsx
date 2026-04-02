/** Compatibility wrapper around the branded modal surface. */
import type { ReactNode } from "react";
import { Modal as UiModal } from "./ui";

type ModalSize = "sm" | "md" | "lg" | "xl";

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  size?: ModalSize;
  footer?: ReactNode;
  actions?: ReactNode;
}

export function Modal({
  isOpen,
  onClose,
  title,
  children,
  size = "md",
  footer,
  actions,
}: Readonly<ModalProps>) {
  return (
    <UiModal
      isOpen={isOpen}
      onClose={onClose}
      title={title}
      size={size}
      footer={footer}
      actions={actions}
    >
      {children}
    </UiModal>
  );
}
