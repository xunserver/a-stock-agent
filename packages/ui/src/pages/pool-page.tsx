import { PoolAddDialog } from "@/components/pool/pool-add-dialog"
import { PoolConfirmDialogs } from "@/components/pool/pool-confirm-dialogs"
import { PoolCreateDialog } from "@/components/pool/pool-create-dialog"
import { PoolDetailPane } from "@/components/pool/pool-detail-pane"
import { PoolMemberList } from "@/components/pool/pool-member-list"
import { PoolToolbar } from "@/components/pool/pool-toolbar"
import { usePoolPageController } from "@/hooks/use-pool-page-controller"
import { cn } from "@/lib/utils"

export function PoolPage() {
  const state = usePoolPageController()
  return (
    <div className="flex flex-col gap-4 lg:h-[calc(100dvh-5.25rem)]">
      <PoolToolbar
        items={state.poolItems}
        poolId={state.poolId}
        busy={state.busy}
        canDelete={state.pools.length > 1 && state.poolId !== null}
        hasMembers={Boolean(state.members?.length)}
        onSelectPool={(next) => void state.onSelectPool(next)}
        onCreate={() => state.setCreateOpen(true)}
        onAdd={() => {
          state.setAddMode("codes")
          state.setAddOpen(true)
        }}
        onSync={() => void state.onSyncAll()}
        onRefresh={() => void state.onRefresh()}
        onDelete={() => state.setDeleteOpen(true)}
      />
      <div
        className={cn(
          "grid min-h-0 flex-1 gap-4",
          state.showDetailPane &&
            "lg:grid-cols-[minmax(16rem,22rem)_minmax(0,1fr)]"
        )}
      >
        <PoolMemberList
          status={state.status}
          loading={state.loading}
          quoteFilter={state.quoteFilter}
          memberQuery={state.memberQuery}
          editing={state.editing}
          checkedCount={state.checkedCodes.size}
          busy={state.busy}
          hasMembers={Boolean(state.members?.length)}
          onQuoteFilterChange={state.setFilter}
          onMemberQueryChange={state.setMemberQuery}
          onRemoveSelected={() => state.setRemoveCodes([...state.checkedCodes])}
          onEditingChange={state.setEdit}
          members={state.members}
          poolId={state.poolId}
          selectedCode={state.selectedCode}
          checkedCodes={state.checkedCodes}
          visibleActiveCodes={state.visibleActiveCodes}
          allVisibleChecked={state.allVisibleChecked}
          someVisibleChecked={state.someVisibleChecked}
          onSelect={state.selectMember}
          onToggleOne={state.toggleOne}
          onToggleAll={state.toggleAll}
          onMoveUp={(code) => void state.onMoveUp(code)}
          onMoveDown={(code) => void state.onMoveDown(code)}
          onMoveToFirst={(code) => void state.onMoveToFirst(code)}
          onRemove={state.setRemoveCodes}
          onAddCodes={() => {
            state.setAddMode("codes")
            state.setAddOpen(true)
          }}
          onAddIndex={() => {
            state.setAddMode("index")
            state.setAddOpen(true)
          }}
        />
        {state.showDetailPane ? (
          <PoolDetailPane
            loading={state.loading}
            membersPending={state.members === null}
            selectedCode={state.selectedCode}
          />
        ) : null}
      </div>
      <PoolCreateDialog
        open={state.createOpen}
        busy={state.busy}
        id={state.createId}
        name={state.createName}
        onOpenChange={state.setCreateOpen}
        onIdChange={state.setCreateId}
        onNameChange={state.setCreateName}
        onSubmit={(event) => void state.onCreate(event)}
      />
      <PoolAddDialog
        open={state.addOpen}
        busy={state.busy}
        poolId={state.poolId}
        mode={state.addMode}
        codes={state.addCodes}
        index={state.addIndex}
        replaceIndex={state.replaceIndex}
        onOpenChange={state.setAddOpen}
        onModeChange={state.setAddMode}
        onCodesChange={state.setAddCodes}
        onIndexChange={state.setAddIndex}
        onReplaceIndexChange={state.setReplaceIndex}
        onSubmit={(event) => void state.onAdd(event)}
      />
      <PoolConfirmDialogs
        poolId={state.poolId}
        busy={state.busy}
        deleteOpen={state.deleteOpen}
        removeCodes={state.removeCodes}
        onDeleteOpenChange={state.setDeleteOpen}
        onRemoveCodesChange={state.setRemoveCodes}
        onDelete={() => void state.onDelete()}
        onRemove={(codes) => void state.onRemove(codes)}
      />
    </div>
  )
}
