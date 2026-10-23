import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { CohortChart } from './AnalyticsPage'

const sample = [{ group: 'Ăn chay', participants: 4, sessions: 9, avg_npi: 67.3, avg_tbr: 0.456 }]

describe('AnalyticsPage cohort comparisons', () => {
  it('shows session-level TBR with the cohort sample counts', () => {
    const html = renderToStaticMarkup(<CohortChart title="Theo chế độ ăn" rows={sample} metric="avg_tbr" />)
    expect(html).toContain('Ăn chay')
    expect(html).toContain('0.456')
    expect(html).toContain('4 hồ sơ · 9 phiên hoàn tất')
    expect(html).toContain('không phải phép so sánh hay kết luận lâm sàng')
  })

  it('renders a clear empty state when the selected metric has no observations', () => {
    const html = renderToStaticMarkup(<CohortChart title="Theo chế độ ăn" rows={sample.map((row) => ({ ...row, avg_tbr: null }))} metric="avg_tbr" />)
    expect(html).toContain('Chưa có dữ liệu lưu phù hợp để so sánh.')
    expect(html).not.toContain('progressbar')
  })
})
