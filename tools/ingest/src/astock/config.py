DEFAULT_ADJUST = "qfq"
HISTORY_START = "20050101"
QUOTE_PERIODS = ("daily", "weekly", "monthly")
DEFAULT_YEARS = 5
HS300_SYMBOL = "000300"
HS300_INDEX_CODE = "sh000300"
REQUEST_SLEEP_SECONDS = 0.35
REQUEST_RETRIES = 3

MAJOR_INDEXES = (
    ("sh000001", "上证指数"),
    ("sz399001", "深证成指"),
    ("sz399006", "创业板指"),
    ("sh000300", "沪深300"),
    ("sh000905", "中证500"),
    ("sh000852", "中证1000"),
    ("sh000688", "科创50"),
)

# 别名 -> 中证/指数代码。pool add --index 用这个快速填池。
INDEX_ALIASES = {
    "hs300": "000300",
    "zz500": "000905",
    "zz1000": "000852",
    "sz50": "000016",
    "kc50": "000688",
    "cyb": "399006",  # 创业板指
}
