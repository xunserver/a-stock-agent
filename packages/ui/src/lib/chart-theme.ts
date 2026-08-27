import {
  ColorType,
  CrosshairMode,
  type CustomColorParser,
  type DeepPartial,
  type Rgba,
  type Time,
  type TimeChartOptions,
} from "lightweight-charts"

export type ChartPalette = {
  background: string
  foreground: string
  muted: string
  border: string
  grid: string
  gain: string
  loss: string
  gainSoft: string
  lossSoft: string
  font: string
}

const colorProbe =
  typeof document === "undefined" ? null : document.createElement("canvas").getContext("2d")

function clamp01(value: number): number {
  return Math.min(1, Math.max(0, value))
}

function srgbByte(channel: number): number {
  const x = clamp01(channel)
  const encoded = x <= 0.0031308 ? 12.92 * x : 1.055 * x ** (1 / 2.4) - 0.055
  return Math.round(clamp01(encoded) * 255)
}

function oklabToRgba(L: number, a: number, b: number, alpha: number): [number, number, number, number] {
  const l_ = L + 0.3963377774 * a + 0.2158037573 * b
  const m_ = L - 0.1055613458 * a - 0.0638541728 * b
  const s_ = L - 0.0894841775 * a - 1.2914855480 * b
  const l = l_ ** 3
  const m = m_ ** 3
  const s = s_ ** 3
  const r = 4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
  const g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
  const blue = -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s
  return [srgbByte(r), srgbByte(g), srgbByte(blue), clamp01(alpha)]
}

function parseAlpha(token: string | undefined): number {
  if (!token) {
    return 1
  }
  const value = token.trim()
  if (value.endsWith("%")) {
    return clamp01(Number(value.slice(0, -1)) / 100)
  }
  return clamp01(Number(value))
}

function parseOklch(color: string): [number, number, number, number] | null {
  const match = color
    .trim()
    .match(
      /^oklch\(\s*([-\d.]+%?)\s+([-\d.]+)\s+([-\d.]+)(?:deg)?(?:\s*\/\s*([-\d.]+%?))?\s*\)$/i
    )
  if (!match) {
    return null
  }
  let lightness = Number(match[1].replace("%", ""))
  if (match[1].includes("%")) {
    lightness /= 100
  }
  const chroma = Number(match[2])
  const hue = (Number(match[3]) * Math.PI) / 180
  return oklabToRgba(lightness, Math.cos(hue) * chroma, Math.sin(hue) * chroma, parseAlpha(match[4]))
}

function formatRgba(channels: [number, number, number, number]): string {
  const [r, g, b, a] = channels
  if (a < 1) {
    return `rgba(${r}, ${g}, ${b}, ${a})`
  }
  return `rgb(${r}, ${g}, ${b})`
}

export function parseCssColorToRgba(color: string): Rgba | null {
  const oklch = parseOklch(color)
  if (!oklch) {
    return null
  }
  return oklch as unknown as Rgba
}

export const oklchColorParser: CustomColorParser = (color) => parseCssColorToRgba(color)

export function toCanvasColor(color: string, fallback = "#111"): string {
  if (!color) {
    return fallback
  }
  const oklch = parseOklch(color)
  if (oklch) {
    return formatRgba(oklch)
  }
  if (!colorProbe) {
    return fallback
  }
  colorProbe.fillStyle = "#000000"
  try {
    colorProbe.fillStyle = color
  } catch {
    return fallback
  }
  const next = colorProbe.fillStyle
  if (typeof next !== "string" || next.length === 0) {
    return fallback
  }
  const converted = parseOklch(next)
  return converted ? formatRgba(converted) : next
}

export function withAlpha(color: string, alpha: number): string {
  const rgb = toCanvasColor(color)
  const match = rgb.match(/^rgba?\((\d+)[,\s]+(\d+)[,\s]+(\d+)/)
  if (!match) {
    return rgb
  }
  return `rgba(${match[1]}, ${match[2]}, ${match[3]}, ${alpha})`
}

function cssVar(el: HTMLElement, name: string): string {
  return getComputedStyle(el).getPropertyValue(name).trim()
}

export function readChartPalette(el: HTMLElement): ChartPalette {
  const gain = toCanvasColor(cssVar(el, "--gain"))
  const loss = toCanvasColor(cssVar(el, "--loss"))
  const border = toCanvasColor(cssVar(el, "--border"))
  return {
    background: toCanvasColor(cssVar(el, "--popover") || cssVar(el, "--background"), "#fff"),
    foreground: toCanvasColor(cssVar(el, "--foreground")),
    muted: toCanvasColor(cssVar(el, "--muted-foreground")),
    border,
    grid: withAlpha(border, 0.6),
    gain,
    loss,
    gainSoft: withAlpha(gain, 0.55),
    lossSoft: withAlpha(loss, 0.55),
    font: getComputedStyle(el).fontFamily,
  }
}

export function chartOptions(
  palette: ChartPalette,
  extras?: { includeParsers?: boolean }
): DeepPartial<TimeChartOptions> {
  return {
    autoSize: true,
    layout: {
      background: { type: ColorType.Solid, color: palette.background },
      textColor: palette.muted,
      fontFamily: palette.font,
      fontSize: 11,
      panes: {
        separatorColor: palette.border,
        separatorHoverColor: withAlpha(palette.foreground, 0.12),
      },
      attributionLogo: true,
      ...(extras?.includeParsers ? { colorParsers: [oklchColorParser] } : {}),
    },
    grid: {
      vertLines: { color: palette.grid },
      horzLines: { color: palette.grid },
    },
    crosshair: {
      mode: CrosshairMode.Magnet,
      vertLine: {
        color: withAlpha(palette.foreground, 0.35),
        labelBackgroundColor: palette.foreground,
      },
      horzLine: {
        color: withAlpha(palette.foreground, 0.35),
        labelBackgroundColor: palette.foreground,
      },
    },
    rightPriceScale: {
      borderColor: palette.border,
      scaleMargins: { top: 0.08, bottom: 0.06 },
    },
    timeScale: {
      borderColor: palette.border,
      rightOffset: 4,
      minBarSpacing: 0.5,
      timeVisible: false,
    },
    localization: {
      locale: "zh-CN",
      dateFormat: "yyyy-MM-dd",
    },
    handleScroll: {
      vertTouchDrag: false,
    },
    kineticScroll: {
      mouse: false,
      touch: true,
    },
  }
}

export function candleSeriesOptions(palette: ChartPalette) {
  return {
    upColor: palette.gain,
    downColor: palette.loss,
    borderVisible: false,
    wickUpColor: palette.gain,
    wickDownColor: palette.loss,
    borderUpColor: palette.gain,
    borderDownColor: palette.loss,
    priceLineVisible: true,
    lastValueVisible: true,
  }
}

export function volumeSeriesOptions(palette: ChartPalette) {
  return {
    priceFormat: {
      type: "custom" as const,
      minMove: 1,
      formatter: (value: number) => formatCompactNumber(value),
    },
    priceLineVisible: false,
    lastValueVisible: false,
    color: palette.gainSoft,
  }
}

export function overlaySeriesOptions(color: string, lineWidth = 2, visible = true) {
  const width = Math.min(4, Math.max(1, Math.round(lineWidth))) as 1 | 2 | 3 | 4
  return {
    color: toCanvasColor(color),
    lineWidth: width,
    visible,
    priceLineVisible: false,
    lastValueVisible: false,
    crosshairMarkerVisible: true,
  }
}

export function timeToDateKey(time: Time): string {
  if (typeof time === "string") {
    return time.slice(0, 10)
  }
  if (typeof time === "number") {
    const date = new Date(time * 1000)
    const month = String(date.getUTCMonth() + 1).padStart(2, "0")
    const day = String(date.getUTCDate()).padStart(2, "0")
    return `${date.getUTCFullYear()}-${month}-${day}`
  }
  return `${time.year}-${String(time.month).padStart(2, "0")}-${String(time.day).padStart(2, "0")}`
}

export function formatCompactNumber(value: number): string {
  if (!Number.isFinite(value)) {
    return "—"
  }
  const abs = Math.abs(value)
  if (abs >= 1e8) {
    return `${(value / 1e8).toFixed(2)}亿`
  }
  if (abs >= 1e4) {
    return `${(value / 1e4).toFixed(2)}万`
  }
  if (abs >= 1) {
    return value.toFixed(0)
  }
  return value.toFixed(2)
}
