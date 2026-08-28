export function activeMemberCodes(
  members: Array<{ code: string; status: string }> | null
): string[] {
  return (members ?? [])
    .filter((member) => member.status === "active")
    .map((member) => member.code)
}

function moveBefore(
  full: string[],
  code: string,
  target: string
): string[] | null {
  if (code === target || !full.includes(code) || !full.includes(target)) {
    return null
  }
  const next = full.filter((item) => item !== code)
  const index = next.indexOf(target)
  if (index < 0) {
    return null
  }
  next.splice(index, 0, code)
  return next
}

function moveAfter(
  full: string[],
  code: string,
  target: string
): string[] | null {
  if (code === target || !full.includes(code) || !full.includes(target)) {
    return null
  }
  const next = full.filter((item) => item !== code)
  const index = next.indexOf(target)
  if (index < 0) {
    return null
  }
  next.splice(index + 1, 0, code)
  return next
}

export function moveMemberUp(
  full: string[],
  visible: string[],
  code: string
): string[] | null {
  const index = visible.indexOf(code)
  if (index <= 0) {
    return null
  }
  return moveBefore(full, code, visible[index - 1])
}

export function moveMemberDown(
  full: string[],
  visible: string[],
  code: string
): string[] | null {
  const index = visible.indexOf(code)
  if (index < 0 || index >= visible.length - 1) {
    return null
  }
  return moveAfter(full, code, visible[index + 1])
}

export function moveMemberToFirst(
  full: string[],
  visible: string[],
  code: string
): string[] | null {
  const index = visible.indexOf(code)
  if (index <= 0) {
    return null
  }
  return moveBefore(full, code, visible[0])
}
