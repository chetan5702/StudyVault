import type { ReactNode, SVGProps } from 'react'

export type IconName =
  | 'arrow-left'
  | 'arrow-right'
  | 'bell'
  | 'book'
  | 'calendar'
  | 'check'
  | 'clock'
  | 'dashboard'
  | 'download'
  | 'edit'
  | 'file'
  | 'file-image'
  | 'file-pdf'
  | 'file-word'
  | 'files'
  | 'lock'
  | 'menu'
  | 'plus'
  | 'settings'
  | 'trash'
  | 'upload'
  | 'user'
  | 'vault'

const paths: Record<IconName, ReactNode> = {
  'arrow-left': <><path d="m15 18-6-6 6-6" /><path d="M9 12h10" /></>,
  'arrow-right': <><path d="m9 18 6-6-6-6" /><path d="M5 12h10" /></>,
  bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9Z" /><path d="M9 21h6" /></>,
  book: <><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" /><path d="M4 4.5A2.5 2.5 0 0 1 6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5Z" /></>,
  calendar: <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M16 3v4M8 3v4M3 10h18" /></>,
  check: <path d="m5 12 4 4L19 6" />,
  clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  dashboard: <><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></>,
  download: <><path d="M12 3v12" /><path d="m7 10 5 5 5-5" /><path d="M5 21h14" /></>,
  edit: <><path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4Z" /></>,
  file: <><path d="M6 2h8l4 4v16H6Z" /><path d="M14 2v5h5" /></>,
  'file-image': <><path d="M6 2h8l4 4v16H6Z" /><path d="M14 2v5h5" /><circle cx="10" cy="11" r="1.4" /><path d="m8 18 3-3 2 2 2-2 2 3" /></>,
  'file-pdf': <><path d="M6 2h8l4 4v16H6Z" /><path d="M14 2v5h5" /><path d="M9 17v-5h2a1.5 1.5 0 0 1 0 3H9M14 12v5h1.2a2 2 0 0 0 0-4H14" /></>,
  'file-word': <><path d="M6 2h8l4 4v16H6Z" /><path d="M14 2v5h5" /><path d="m8.5 12 1 5 1.5-3 1.5 3 1-5" /></>,
  files: <><path d="M6 2h8l4 4v16H6Z" /><path d="M14 2v5h5" /><path d="M3 6v15h11" /></>,
  lock: <><rect x="5" y="10" width="14" height="11" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3" /></>,
  menu: <><path d="M4 7h16M4 12h16M4 17h16" /></>,
  plus: <path d="M12 5v14M5 12h14" />,
  settings: <><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1A1.7 1.7 0 0 0 9 4.6 1.7 1.7 0 0 0 10 3V2.8h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z" /></>,
  trash: <><path d="M4 7h16M9 7V4h6v3M7 7l1 14h8l1-14M10 11v6M14 11v6" /></>,
  upload: <><path d="M12 16V4" /><path d="m7 9 5-5 5 5" /><path d="M5 21h14" /></>,
  user: <><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></>,
  vault: <><rect x="3" y="3" width="18" height="18" rx="4" /><path d="M8 8h8v8H8zM12 8v8M8 12h8" /></>,
}

export function Icon({ name, size = 20, ...props }: SVGProps<SVGSVGElement> & { name: IconName; size?: number }) {
  return <svg viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false" {...props}>{paths[name]}</svg>
}

export function FileTypeIcon({ fileName, mimeType }: { fileName: string; mimeType?: string }) {
  const extension = fileName.split('.').pop()?.toLowerCase()
  const kind = mimeType === 'application/pdf' || extension === 'pdf'
    ? 'pdf'
    : mimeType?.startsWith('image/') || ['png', 'jpg', 'jpeg'].includes(extension || '')
      ? 'image'
      : mimeType === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' || extension === 'docx'
        ? 'word'
        : 'file'
  const labels = { pdf: 'PDF', image: 'IMG', word: 'DOCX', file: 'FILE' }
  const iconNames = { pdf: 'file-pdf', image: 'file-image', word: 'file-word', file: 'file' } as const
  return <span className={`file-type file-type-${kind}`} aria-label={`${labels[kind]} file`} title={`${labels[kind]} file`}><Icon name={iconNames[kind]} size={22} /><span>{labels[kind]}</span></span>
}
