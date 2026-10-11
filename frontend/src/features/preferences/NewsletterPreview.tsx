import { useQuery } from '@tanstack/react-query'
import { Eye, EyeOff, Mail, RefreshCw } from 'lucide-react'
import { useState } from 'react'
import { fetchNewsletterPreview, type NewsletterPreview as Preview, type Subscriber } from '../../lib/api'
import { formatEditionDate } from '../../lib/format'
import { translatePlural, useLanguage, type Language } from '../../lib/i18n'

/**
 * The e-mail as the pipeline would send it. The HTML is built by the same server code
 * as the real e-mail and shown in a sandboxed frame: no script runs, nothing can submit
 * a form, and links open in a new tab.
 */
export function NewsletterPreview({ subscriber }: { subscriber: Subscriber }) {
  const { language, t } = useLanguage()
  const [open, setOpen] = useState(false)
  // The saved preferences are part of the key: saving them rebuilds an open preview.
  const preview = useQuery({
    queryKey: ['newsletter-preview', subscriber.id, subscriber.preferences],
    queryFn: ({ signal }) => fetchNewsletterPreview(subscriber.id, signal),
    enabled: open,
    staleTime: 0,
  })

  return (
    <section aria-labelledby="preview-title" className="rounded-card bg-surface shadow-card">
      <header className="flex flex-wrap items-center gap-4 p-5 sm:p-7">
        <span aria-hidden className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-accent-soft text-accent">
          <Mail size={20} />
        </span>
        <div className="min-w-[13rem] flex-1">
          <h2 id="preview-title" className="text-[17px] font-bold">
            {t('preview.title')}
          </h2>
          <p className="text-[13px] text-muted">{t('preview.subtitle')}</p>
        </div>
        <button
          type="button"
          aria-expanded={open}
          onClick={() => setOpen((value) => !value)}
          className="flex items-center gap-1.5 rounded-control bg-ink px-4 py-2.5 text-[14px] font-semibold text-white transition-all duration-150 ease-soft hover:-translate-y-0.5 active:translate-y-0"
        >
          {open ? <EyeOff size={15} aria-hidden /> : <Eye size={15} aria-hidden />}
          {open ? t('preview.hide') : t('preview.show')}
        </button>
      </header>

      {open && (
        <div className="space-y-4 border-t border-line p-5 sm:p-7" aria-live="polite">
          {preview.isPending && <p className="text-[14px] text-muted">{t('preview.loading')}</p>}
          {preview.isError && (
            <div role="alert" className="flex flex-wrap items-center gap-3 text-[14px] text-rumor">
              {t('preview.error')}
              <button
                type="button"
                onClick={() => preview.refetch()}
                className="flex items-center gap-1.5 rounded-full px-3 py-1.5 font-semibold text-accent hover:bg-accent-soft"
              >
                <RefreshCw size={14} aria-hidden />
                {t('preview.retry')}
              </button>
            </div>
          )}
          {preview.data && <PreviewBody preview={preview.data} language={language} />}
        </div>
      )}
    </section>
  )
}

function PreviewBody({ preview, language }: { preview: Preview; language: Language }) {
  const { t } = useLanguage()
  if (preview.reason === 'no_edition') return <p className="text-[14px] text-muted">{t('preview.noEdition')}</p>

  const count = preview.item_count + preview.unanalyzed_count
  const origin =
    preview.frequency === 'weekly' && preview.since && preview.until
      ? t('preview.weekly', { since: formatEditionDate(preview.since, language), until: formatEditionDate(preview.until, language) })
      : t('preview.daily')
  return (
    <>
      <dl className="grid gap-x-6 gap-y-1 text-[13.5px] sm:grid-cols-[auto_1fr]">
        <dt className="font-semibold text-muted">{t('preview.subject')}</dt>
        <dd className="min-w-0 break-words font-semibold">{preview.subject}</dd>
        <dt className="font-semibold text-muted">{t(`freq.${preview.frequency}`)}</dt>
        <dd className="min-w-0">
          {origin} · {translatePlural(language, 'preview.items', count, { count })}
          {preview.unanalyzed_count > 0 && ` · ${t('preview.unanalyzed', { count: preview.unanalyzed_count })}`}
        </dd>
      </dl>
      {preview.language_fallback && (
        <p className="text-[13px] text-unverified">{t('preview.fallback', preview.language_fallback)}</p>
      )}
      {!preview.would_send || !preview.html ? (
        <p className="rounded-control bg-canvas p-4 text-[14px] text-muted">{t('preview.notSent')}</p>
      ) : (
        <iframe
          title={t('preview.frame')}
          sandbox="allow-popups allow-popups-to-escape-sandbox"
          srcDoc={preview.html.replace('<head>', '<head><base target="_blank">')}
          className="h-[620px] w-full rounded-control border border-line bg-white"
        />
      )}
    </>
  )
}
