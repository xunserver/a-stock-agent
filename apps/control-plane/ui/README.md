# 浏览端薄宿主

页面和组件在 `packages/ui`。这里只挂 `BrowserRouter`，并把 `/api` 代理到 core。

```bash
# 仓库根
pnpm --filter ui dev

# 另开终端
uv --directory apps/control-plane/core run python -m astock_control
```
