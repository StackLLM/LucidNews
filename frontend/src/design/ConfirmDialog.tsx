import { AlertDialog } from 'radix-ui'
import type { ReactNode } from 'react'

/** Confirmation for irreversible actions (Radix AlertDialog: focus trap, Esc, labelled). */
export function ConfirmDialog({
  trigger,
  title,
  description,
  cancel,
  confirm,
  onConfirm,
}: {
  trigger: ReactNode
  title: string
  description: string
  cancel: string
  confirm: string
  onConfirm: () => void
}) {
  return (
    <AlertDialog.Root>
      <AlertDialog.Trigger asChild>{trigger}</AlertDialog.Trigger>
      <AlertDialog.Portal>
        <AlertDialog.Overlay className="fixed inset-0 z-40 bg-ink/25 backdrop-blur-sm data-[state=open]:animate-[fade-in_200ms_ease-out]" />
        <AlertDialog.Content className="glass fixed top-1/2 left-1/2 z-50 w-[min(92vw,420px)] -translate-x-1/2 -translate-y-1/2 rounded-card p-7 data-[state=open]:animate-[pop-in_220ms_var(--ease-soft)]">
          <AlertDialog.Title className="text-[18px] font-bold">{title}</AlertDialog.Title>
          <AlertDialog.Description className="mt-2 text-[14px] leading-relaxed text-muted">
            {description}
          </AlertDialog.Description>
          <div className="mt-6 flex justify-end gap-3">
            <AlertDialog.Cancel className="rounded-control px-4 py-2.5 text-[14px] font-semibold text-ink/70 transition-colors duration-150 hover:bg-white">
              {cancel}
            </AlertDialog.Cancel>
            <AlertDialog.Action
              onClick={onConfirm}
              className="rounded-control bg-rumor px-4 py-2.5 text-[14px] font-semibold text-white transition-all duration-150 ease-soft hover:-translate-y-0.5 hover:brightness-110 active:translate-y-0"
            >
              {confirm}
            </AlertDialog.Action>
          </div>
        </AlertDialog.Content>
      </AlertDialog.Portal>
    </AlertDialog.Root>
  )
}
