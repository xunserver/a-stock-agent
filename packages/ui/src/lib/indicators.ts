export type PricePoint = {
  time: string
  close: number
}

export type IndicatorPoint = {
  time: string
  value?: number
}

export function smaSeries(rows: PricePoint[], period: number): IndicatorPoint[] {
  const points: IndicatorPoint[] = []
  let sum = 0
  for (let i = 0; i < rows.length; i += 1) {
    sum += rows[i].close
    if (i >= period) {
      sum -= rows[i - period].close
    }
    if (i >= period - 1) {
      points.push({ time: rows[i].time, value: sum / period })
    } else {
      points.push({ time: rows[i].time })
    }
  }
  return points
}

export function emaSeries(rows: PricePoint[], period: number): IndicatorPoint[] {
  const points: IndicatorPoint[] = []
  const smoothing = 2 / (period + 1)
  let previous: number | null = null
  let seed = 0
  for (let i = 0; i < rows.length; i += 1) {
    const close = rows[i].close
    if (i < period - 1) {
      seed += close
      points.push({ time: rows[i].time })
      continue
    }
    if (previous == null) {
      seed += close
      previous = seed / period
    } else {
      previous = close * smoothing + previous * (1 - smoothing)
    }
    points.push({ time: rows[i].time, value: previous })
  }
  return points
}
