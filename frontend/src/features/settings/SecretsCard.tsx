import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Check, KeyRound, Terminal, Trash2, TriangleAlert } from 'lucide-react'
import { useEffect, useId, useState, type FormEvent } from 'react'
import { ConfirmDialog } from '../../design/ConfirmDialog'
import { deleteSecret, saveSecret, type Secret } from '../../lib/api'
import { useLanguage, type MessageKey } from '../../lib/i18n'

/**
 * API keys used by the configuration. A value only ever exists in the input while
 * it is typed: it is sent once, then cleared. The API never sends one back.
 */
export function SecretsCard({ secrets }: { secrets: Secret[] }) {
  const { t } = useLanguage()
  return (
    <section aria-labelledby="keys-title" className="rounded-card bg-surface p-5 shadow-card sm:p-7">
      <h2 id="keys-title" className="flex items-center gap-2 text-[17px] font-bold">
        <KeyRound size={17} aria-hidden className="text-accent" />
        {t('settings.keys')}
      </h2>
      <p className="mt-1.5 text-[13.5px] leading-relaxed text-muted">{t('settings.keysHint')}</p>
      {secrets.length === 0 ? (
        <p className="mt-4 text-[14px] text-muted">{t('settings.key.none')}</p>
      ) : (
        <ul className="mt-5 divide-y divide-line">
          {secrets.map((secret) => (
            <SecretRow key={secret.name} secret={secret} />
          ))}
        </ul>
      )}
    </section>
  )
}

function usedByLabel(entry: string, t: (key: MessageKey, params?: Record<string, string>) => string) {
  const [kind, name] = entry.split(':')
  return t(`settings.usedBy.${kind}` as MessageKey, { name: name ?? '' })
}

function SecretRow({ secret }: { secret: Secret }) {
  const { t } = useLanguage()
  const queryClient = useQueryClient()
  const inputId = useId()
  const [editing, setEditing] = useState(false)
  const [value, setValue] = useState('')
  const [notice, setNotice] = useState<'done' | 'removed' | null>(null)

  useEffect(() => {
    if (!notice) return
    const timer = window.setTimeout(() => setNotice(null), 3000)
    return () => window.clearTimeout(timer)
  }, [notice])

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['secrets'] })
  const save = useMutation({
    mutationFn: (key: string) => saveSecret(secret.name, key),
    onSuccess: async () => {
      setEditing(false)
      setNotice('done')
      await refresh()
    },
    // Whatever happens, the typed value does not stay in memory.
    onSettled: () => setValue(''),
  })
  const remove = useMutation({
    mutationFn: () => deleteSecret(secret.name),
    onSuccess: async () => {
      setNotice('removed')
      await refresh()
    },
  })

  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (value.trim()) save.mutate(value)
  }
  const cancel = () => {
    setValue('')
    setEditing(false)
  }

  const status = secret.in_environment
    ? { label: t('settings.key.env'), icon: Terminal, tone: 'bg-reliable/10 text-reliable ring-reliable/20' }
    : secret.in_file
      ? { label: t('settings.key.saved'), icon: Check, tone: 'bg-confirmed/10 text-confirmed ring-confirmed/20' }
      : { label: t('settings.key.missing'), icon: TriangleAlert, tone: 'bg-unverified/10 text-unverified ring-unverified/25' }
  const StatusIcon = status.icon

  return (
    <li className="py-4 first:pt-0 last:pb-0">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <div className="min-w-0 flex-1">
          <p className="truncate font-mono text-[13.5px] font-semibold">{secret.name}</p>
          <p className="text-[12.5px] text-muted">{secret.used_by.map((entry) => usedByLabel(entry, t)).join(' · ')}</p>
        </div>
        <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[12px] font-semibold ring-1 ring-inset ${status.tone}`}>
          <StatusIcon size={13} aria-hidden />
          {status.label}
        </span>
      </div>

      {secret.in_environment && <p className="mt-2 text-[12.5px] text-muted">{t('settings.key.envHint')}</p>}

      {editing ? (
        <form onSubmit={submit} className="mt-3 flex flex-wrap gap-2">
          <label htmlFor={inputId} className="sr-only">
            {t('settings.key.label', { name: secret.name })}
          </label>
          <input
            id={inputId}
            type="password"
            autoComplete="off"
            spellCheck={false}
            autoFocus
            value={value}
            onChange={(event) => setValue(event.target.value)}
            placeholder={t('settings.key.placeholder')}
            className="min-w-0 flex-1 rounded-control bg-canvas px-3.5 py-2.5 font-mono text-[13.5px] ring-1 ring-ink/10 outline-none transition-shadow duration-150 focus:ring-2 focus:ring-accent/50"
          />
          <button
            type="submit"
            disabled={!value.trim() || save.isPending}
            className="rounded-control bg-accent px-4 py-2.5 text-[13.5px] font-semibold text-white transition-all duration-150 ease-soft hover:bg-accent-deep disabled:opacity-50"
          >
            {t('settings.key.save')}
          </button>
          <button
            type="button"
            onClick={cancel}
            className="rounded-control px-3 py-2.5 text-[13.5px] font-semibold text-ink/70 transition-colors duration-150 hover:bg-canvas"
          >
            {t('settings.key.cancel')}
          </button>
          {save.isError && (
            <p role="alert" className="w-full text-[13px] text-rumor">
              {t('error.save')}
            </p>
          )}
        </form>
      ) : (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => setEditing(true)}
            className="rounded-full bg-accent-soft px-3.5 py-1.5 text-[13px] font-semibold text-accent transition-all duration-150 ease-soft hover:bg-accent hover:text-white"
          >
            {t(secret.in_file ? 'settings.key.replace' : 'settings.key.enter')}
          </button>
          {secret.in_file && (
            <ConfirmDialog
              trigger={
                <button
                  type="button"
                  className="flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[13px] font-semibold text-ink/60 transition-colors duration-150 hover:bg-rumor/10 hover:text-rumor"
                >
                  <Trash2 size={13} aria-hidden />
                  {t('settings.key.delete')}
                </button>
              }
              title={t('settings.key.deleteTitle', { name: secret.name })}
              description={t('settings.key.deleteBody')}
              cancel={t('settings.key.cancel')}
              confirm={t('settings.key.delete')}
              onConfirm={() => remove.mutate()}
            />
          )}
          <span role="status" aria-live="polite" className="text-[12.5px] text-confirmed">
            {notice === 'done' ? t('settings.key.done') : notice === 'removed' ? t('settings.key.removed') : ''}
          </span>
        </div>
      )}
    </li>
  )
}
