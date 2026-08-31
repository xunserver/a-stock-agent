import { Link } from "react-router"
import { FolderIcon } from "lucide-react"

import { PoolMemberToolbar } from "@/components/pool/pool-member-toolbar"
import { PoolMembersTable } from "@/components/pool/pool-members-table"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import { Skeleton } from "@/components/ui/skeleton"
import type { PoolMember } from "@/lib/api"

type PoolMemberListProps = React.ComponentProps<typeof PoolMemberToolbar> &
  Omit<React.ComponentProps<typeof PoolMembersTable>, "members"> & {
    members: PoolMember[] | null
    poolId: string | null
    onAddCodes: () => void
    onAddIndex: () => void
  }

export function PoolMemberList({
  members,
  poolId,
  onAddCodes,
  onAddIndex,
  ...props
}: PoolMemberListProps) {
  return (
    <Card className="h-full max-h-80 min-h-0 lg:max-h-none">
      <PoolMemberToolbar {...props} />
      <CardContent className="min-h-0 flex-1 overflow-auto">
        {props.loading && members === null ? (
          <LoadingRows />
        ) : members && members.length > 0 ? (
          <PoolMembersTable {...props} members={members} />
        ) : (
          <EmptyPool
            poolId={poolId}
            busy={props.busy}
            onAddCodes={onAddCodes}
            onAddIndex={onAddIndex}
          />
        )}
      </CardContent>
    </Card>
  )
}

function LoadingRows() {
  return (
    <div className="flex flex-col gap-2">
      <Skeleton className="h-8 w-full" />
      <Skeleton className="h-8 w-full" />
      <Skeleton className="h-8 w-full" />
    </div>
  )
}

function EmptyPool({
  poolId,
  busy,
  onAddCodes,
  onAddIndex,
}: {
  poolId: string | null
  busy: boolean
  onAddCodes: () => void
  onAddIndex: () => void
}) {
  return (
    <Empty>
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <FolderIcon />
        </EmptyMedia>
        <EmptyTitle>股票池是空的</EmptyTitle>
        <EmptyDescription>
          成员必须先在「股票」里。可以按代码加入，或按指数并入系统里已有的成分。移出不会删已入库的日线。
        </EmptyDescription>
      </EmptyHeader>
      <EmptyContent>
        <div className="flex flex-wrap justify-center gap-2">
          <Button size="sm" render={<Link to="/stocks" />}>
            去股票管理
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={!poolId || busy}
            onClick={onAddCodes}
          >
            添加代码
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={!poolId || busy}
            onClick={onAddIndex}
          >
            按指数添加
          </Button>
        </div>
      </EmptyContent>
    </Empty>
  )
}
