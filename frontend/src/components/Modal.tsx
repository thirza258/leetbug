import { useEffect, useRef } from 'react';
import type { ReactNode } from 'react';

export default function Modal({ label, onDismiss, children }: { label: string; onDismiss: () => void; children: ReactNode }) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const element = dialog.current;
    element?.showModal();
    return () => element?.close();
  }, []);
  return <dialog ref={dialog} className="modal hint-modal" aria-label={label}
    onCancel={event => { event.preventDefault(); onDismiss(); }}
    onClick={event => { if (event.target === event.currentTarget) onDismiss(); }}>
    <div>{children}</div>
  </dialog>;
}
