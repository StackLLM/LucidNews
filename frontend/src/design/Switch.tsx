import { Switch as RadixSwitch } from 'radix-ui'

/** Accessible on/off switch (Radix), styled with the design tokens. */
export function Switch({
  id,
  checked,
  onCheckedChange,
  labelledBy,
  describedBy,
}: {
  id?: string
  checked: boolean
  onCheckedChange: (checked: boolean) => void
  labelledBy?: string
  describedBy?: string
}) {
  return (
    <RadixSwitch.Root
      id={id}
      checked={checked}
      onCheckedChange={onCheckedChange}
      aria-labelledby={labelledBy}
      aria-describedby={describedBy}
      className="relative h-7 w-12 shrink-0 rounded-full bg-ink/15 transition-colors duration-200 ease-soft data-[state=checked]:bg-accent"
    >
      <RadixSwitch.Thumb className="block h-5.5 w-5.5 translate-x-[3px] rounded-full bg-white shadow-[0_2px_6px_rgb(15_21_48/0.25)] transition-transform duration-200 ease-soft data-[state=checked]:translate-x-[23px]" />
    </RadixSwitch.Root>
  )
}
