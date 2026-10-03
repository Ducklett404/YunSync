import type { TraceableData } from '../types/domain'

export interface ContentOptions { allowDemoContent?: boolean }

export function isContentAvailable(content: TraceableData, options: ContentOptions = {}): boolean {
  return (content.reviewStatus === 'approved' && !content.isDemo)
    || Boolean(options.allowDemoContent && content.reviewStatus === 'demo' && content.isDemo)
}

export function contentUnavailableReason(content?: TraceableData): string {
  if (!content) return '内容已移除或链接无效'
  if (content.reviewStatus === 'disabled') return '内容已停用'
  if (content.reviewStatus === 'draft') return '内容待审核'
  return '内容尚未通过当前模式的审核要求'
}
